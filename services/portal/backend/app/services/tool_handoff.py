"""Hand an approved tool build to digitaltwins-api, as the approving user.

The built SPARC folder is uploaded through the API's resumable session protocol
(``/datasets/uploads``, ``commit_mode=on_finalize``). The API registers the tool
in SEEK and stores it in Postgres and MinIO (see
docs/decisions/2026-10-01-unified-tool-dataset-ingest.md).

Keycloak access tokens last minutes, so the job keeps no token of its own:
:data:`relay` holds the newest token for each build, and every status poll
from the portal page refreshes it. A 401 pauses the job (``awaiting_reauth``).
The next poll resumes it from the API's received-parts status. Tokens are only
ever held in memory.
"""
import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

import httpx

from app.models.db_model import Plugin, PluginBuild, SessionLocal

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0
TOOL_CATEGORY = "tools"
TOOL_TYPES = {"GUI": "gui", "Script": "script", "Notebook": "notebook"}
ACTIVE = ("uploading", "committing", "awaiting_reauth")


def make_http() -> httpx.Client:
    """digitaltwins-api over the internal network (same settings as app.client.digitaltwins_api)."""
    base = os.getenv("DIGITALTWINS_API_BASE_URL", "http://digitaltwins-api").rstrip("/")
    return httpx.Client(base_url=f"{base}:{os.getenv('DIGITALTWINS_API_PORT', '8000')}", timeout=httpx.Timeout(120.0))


class TokenRelay:
    """The newest user token per build (in memory only)."""

    def __init__(self):
        self._tokens: Dict[str, str] = {}
        self._lock = threading.Lock()

    def put(self, build_id: str, token: str) -> None:
        with self._lock:
            self._tokens[build_id] = token

    def get(self, build_id: str) -> Optional[str]:
        with self._lock:
            return self._tokens.get(build_id)

    def drop(self, build_id: str) -> None:
        with self._lock:
            self._tokens.pop(build_id, None)

    def clear(self) -> None:
        with self._lock:
            self._tokens.clear()


relay = TokenRelay()
progress: Dict[str, Tuple[int, int]] = {}  # build_id -> (parts sent, parts total)
_running: set = set()
_running_lock = threading.Lock()


class NeedsReauth(Exception):
    """The API rejected the token: wait for a fresh one from the next status poll."""


class ApiError(RuntimeError):
    pass


class Api:
    """digitaltwins-api calls, each made with the current token from ``token()``."""

    def __init__(self, http: httpx.Client, token: Callable[[], Optional[str]]):
        self.http, self.token = http, token

    def request(self, method: str, path: str, expect=(200, 202), **kwargs) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token()}", **kwargs.pop("headers", {})}
        r = self.http.request(method, path, headers=headers, **kwargs)
        if r.status_code == 401:
            raise NeedsReauth()
        if r.status_code not in expect:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise ApiError(f"{method} {path} -> {r.status_code}: {detail}")
        return r.json() if r.content else {}


def _files(root: Path) -> Iterator[Tuple[str, Path]]:
    """``(rel_path, local_path)`` pairs, rel paths prefixed with the folder name (as the API expects)."""
    for local in sorted(p for p in root.rglob("*") if p.is_file()):
        yield f"{root.name}/{local.relative_to(root).as_posix()}", local


# ── Annotation draft <-> workflow_tool descriptions ────────────────────


def fhir_descriptions(plugin: Plugin) -> Dict[str, Any]:
    """The tool's ``workflow_tool`` FHIR descriptions: its version plus the Annotation step's port draft."""
    tool: Dict[str, Any] = {"version": plugin.version}
    note = plugin.annotation.fhir_note if plugin.annotation else None
    draft = json.loads(note) if note else {}
    inputs = [{"id": p["name"], "resourceType": p["resource"]} for p in draft.get("inputs") or [] if p.get("resource")]
    outputs = [
        {"id": p["name"], "resourceType": p["resource"],
         **{k: p[k] for k in ("code", "system", "unit") if p.get(k)}}
        for p in draft.get("outputs") or [] if p.get("resource")
    ]
    if inputs:
        tool["input"] = inputs
    if outputs:
        tool["output"] = outputs
    return {"workflow_tool": tool}


def draft_from_descriptions(name: str, descriptions: Dict[str, Any]) -> Dict[str, Any]:
    """The Annotation step's draft shape, from the platform's ``workflow_tool`` descriptions."""
    tool = descriptions.get("workflow_tool") or {}
    return {
        "name": name,
        "inputs": [{"name": p["id"], "resource": p.get("resourceType", "")} for p in tool.get("input") or []],
        "outputs": [{"name": p["id"], "resource": p.get("resourceType", ""), "code": p.get("code", ""),
                     "system": p.get("system", ""), "unit": p.get("unit", "")} for p in tool.get("output") or []],
    }


# ── Handoff ────────────────────────────────────────────────────────────


def status_view(build: PluginBuild) -> Dict[str, Any]:
    sent, total = progress.get(build.build_id, (None, None))
    return {
        "build_id": build.build_id, "handoff_status": build.handoff_status, "upload_id": build.upload_id,
        "dataset_uuid": build.dataset_uuid, "seek_id": build.seek_id, "handoff_error": build.handoff_error,
        "parts_sent": sent, "parts_total": total,
    }


def relay_token(build: PluginBuild, user: Dict[str, Any]) -> bool:
    """Hand the approver's fresh token to the handoff; another user's is ignored (SEEK would register as them)."""
    if user.get("username") != build.handoff_user:
        return False
    relay.put(build.build_id, user["token"])
    return True


def is_running(build_id: str) -> bool:
    with _running_lock:
        return build_id in _running


def start(db, plugin: Plugin, build: PluginBuild, user: Dict[str, Any], seek_project_id: int, fhir: bool) -> None:
    """Open the API upload session for ``build`` as ``user`` (the caller then runs :func:`run` in the background)."""
    token = user["token"]
    api = Api(make_http(), lambda: token)
    if build.upload_id:  # an earlier, failed handoff of this build
        try:
            api.request("DELETE", f"/datasets/uploads/{build.upload_id}", expect=(200, 404, 409))
        except ApiError as exc:
            logger.warning("Could not cancel earlier upload session %s: %s", build.upload_id, exc)
    part_size = api.request("GET", "/datasets/uploads/config")["max_part_size"]
    manifest = [{"rel_path": rel, "size": local.stat().st_size,
                 "parts": max(1, math.ceil(local.stat().st_size / part_size))}
                for rel, local in _files(Path(build.dataset_path))]
    body = {
        "name": plugin.name, "description": plugin.description, "category": TOOL_CATEGORY,
        "source_kind": "folder", "manifest": manifest, "commit_mode": "on_finalize",
        "tool_type": TOOL_TYPES[plugin.label], "seek_project_id": seek_project_id,
    }
    if fhir:
        body["fhir_descriptions"] = fhir_descriptions(plugin)
    created = api.request("POST", "/datasets/uploads", json=body)
    build.upload_id, build.handoff_status, build.handoff_error = created["upload_id"], "uploading", None
    build.handoff_user = user["username"]
    plugin.seek_project_id = seek_project_id
    db.commit()
    relay.put(build.build_id, token)


def _send_parts(api: Api, build: PluginBuild, upload: Dict[str, Any]) -> None:
    part_size = api.request("GET", "/datasets/uploads/config")["max_part_size"]
    received = {f["rel_path"]: set(f["received_parts"]) for f in upload["files"]}
    parts_of = {f["rel_path"]: f["parts"] for f in upload["files"]}
    total = sum(parts_of.values())
    sent = sum(len(r) for r in received.values())
    progress[build.build_id] = (sent, total)
    for rel, local in _files(Path(build.dataset_path)):
        missing = [n for n in range(parts_of[rel]) if n not in received.get(rel, set())]
        if not missing:
            continue
        with open(local, "rb") as fh:
            for n in missing:
                fh.seek(n * part_size)
                api.request("PUT", f"/datasets/uploads/{build.upload_id}/parts/{rel}",
                            params={"n": n, "of": parts_of[rel]}, content=fh.read(part_size),
                            headers={"Content-Type": "application/octet-stream"})
                sent += 1
                progress[build.build_id] = (sent, total)


def _wait(api: Api, upload_id: str) -> Dict[str, Any]:
    while True:
        session = api.request("GET", f"/datasets/uploads/{upload_id}")
        if session["status"] in ("completed", "failed"):
            return session
        time.sleep(POLL_INTERVAL)


def _complete(db, api: Api, plugin: Plugin, build: PluginBuild, dataset_uuid: str) -> None:
    """Record the committed dataset; with re-approval, the previous one is deleted only now."""
    seek_id = api.request("GET", f"/datasets/{dataset_uuid}")["dataset"].get("seek_id")
    previous = plugin.uuid
    build.dataset_uuid, build.seek_id, build.handoff_status = dataset_uuid, seek_id, "completed"
    plugin.uuid = dataset_uuid
    db.commit()
    if previous and previous != dataset_uuid:
        try:
            api.request("DELETE", f"/datasets/{previous}", expect=(200, 404))
            db.query(PluginBuild).filter(PluginBuild.dataset_uuid == previous).update({"dataset_uuid": None})
        except Exception as exc:
            logger.warning("Previous dataset %s of plugin %s not deleted: %s", previous, plugin.id, exc)
            build.handoff_error = f"Approved, but the previous version {previous} could not be deleted: {exc}"
        db.commit()


def run(build_id: str) -> None:
    """Send the build's missing parts, finalize, wait for the commit. Never raises; state goes on the row."""
    with _running_lock:
        if build_id in _running:
            return
        _running.add(build_id)
    try:
        with SessionLocal() as db:
            build = db.query(PluginBuild).filter(PluginBuild.build_id == build_id).one()
            if build.handoff_status not in ACTIVE:
                return
            api = Api(make_http(), lambda: relay.get(build_id))
            try:
                session = api.request("GET", f"/datasets/uploads/{build.upload_id}")
                if session["status"] == "receiving":
                    build.handoff_status = "uploading"
                    db.commit()
                    _send_parts(api, build, session["upload"])
                    api.request("POST", f"/datasets/uploads/{build.upload_id}/finalize")
                build.handoff_status = "committing"
                db.commit()
                session = _wait(api, build.upload_id)
                if session["status"] == "failed":
                    build.handoff_status, build.handoff_error = "failed", session.get("failure_message")
                    db.commit()
                else:
                    _complete(db, api, build.plugin, build, session["dataset_uuid"])
                relay.drop(build_id)
            except NeedsReauth:
                build.handoff_status = "awaiting_reauth"
                db.commit()
            except Exception as exc:
                logger.exception("Tool handoff failed for build %s", build_id)
                build.handoff_status, build.handoff_error = "failed", str(exc)
                db.commit()
                relay.drop(build_id)
    finally:
        with _running_lock:
            _running.discard(build_id)
