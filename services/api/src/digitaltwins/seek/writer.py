"""Write to SEEK as the calling user: register tools and workflows as Workflows, delete them,
and manage the SOPs that link an assay to its workflow.

A tool is a SEEK Workflow tagged ``tool`` plus its tool type, a workflow one
tagged ``workflow`` plus its workflow type. Each is registered
with one RO-Crate POST so SEEK's own extractors set the title, tags and the
CWL ``internals`` (see docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md).
"""
import io
import json
import os
import zipfile
from pathlib import Path

import requests
import yaml
from requests import RequestException

from dotenv import load_dotenv

load_dotenv()


def _build_crate(main_cwl: Path, keywords, extra_cwls=()) -> bytes:
    """A zipped Workflow RO-Crate holding ``main_cwl`` as its main workflow.

    Root ``name`` / ``description`` come from the CWL ``label`` / ``doc`` (the file
    stem when there is no label); root ``keywords`` become the SEEK tags.
    ``extra_cwls`` (a workflow's tool CWLs) are packed beside it so that its
    steps' ``run: tool_x.cwl`` resolve.
    """
    main_cwl = Path(main_cwl)
    extra_cwls = [Path(p) for p in extra_cwls]
    cwl = yaml.safe_load(main_cwl.read_text()) or {}
    title = cwl.get("label") or main_cwl.stem
    root = {
        "@id": "./",
        "@type": "Dataset",
        "name": title,
        "keywords": list(keywords),
        "hasPart": [{"@id": p.name} for p in [main_cwl, *extra_cwls]],
        "mainEntity": {"@id": main_cwl.name},
    }
    if cwl.get("doc"):
        root["description"] = cwl["doc"]
    metadata = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": [
                    {"@id": "https://w3id.org/ro/crate/1.1"},
                    {"@id": "https://w3id.org/workflowhub/workflow-ro-crate/1.0"},
                ],
            },
            root,
            {
                "@id": main_cwl.name,
                "@type": ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
                "name": title,
                "programmingLanguage": {"@id": "#cwl"},
            },
            *({
                "@id": p.name,
                "@type": ["File", "SoftwareSourceCode"],
                "programmingLanguage": {"@id": "#cwl"},
            } for p in extra_cwls),
            {
                "@id": "#cwl",
                "@type": "ComputerLanguage",
                "name": "Common Workflow Language",
                "identifier": {"@id": "https://w3id.org/cwl/"},
                "url": {"@id": "https://www.commonwl.org/"},
            },
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ro-crate-metadata.json", json.dumps(metadata, indent=2))
        for path in [main_cwl, *extra_cwls]:
            zf.write(path, path.name)
    return buf.getvalue()


def build_tool_crate(cwl_path: Path, tool_type: str) -> bytes:
    """A tool's crate: its CWL, tagged ``tool`` + its tool type."""
    return _build_crate(cwl_path, ["tool", tool_type])


def build_workflow_crate(workflow_cwl: Path, tool_cwls, workflow_type: str) -> bytes:
    """A workflow's crate: its CWL plus its steps' tool CWLs, tagged ``workflow`` + its type."""
    return _build_crate(workflow_cwl, ["workflow", workflow_type], tool_cwls)


def _seek_error(resp) -> str:
    try:
        errors = resp.json().get("errors") or []
        return "; ".join(e.get("detail") or e.get("title") or "" for e in errors) or resp.text
    except ValueError:
        return resp.text


class Writer(object):
    def __init__(self, api_token: str):
        self._base_url = os.getenv("SEEK_BASE_URL")
        self._api_token = api_token

        if not self._base_url:
            raise ValueError("SEEK configuration is incomplete. SEEK_BASE_URL is not set.")

    def _post_crate(self, kind: str, stem: str, crate: bytes, project_id: int) -> int:
        """Create a SEEK Workflow from ``crate`` in ``project_id``; return its id."""
        # Authorization only: with ``Accept: application/json`` SEEK treats the call
        # as JSON:API and rejects the multipart crate (422, no ``data`` record).
        headers = {"Authorization": "Bearer " + self._api_token}
        try:
            resp = requests.post(
                f"{self._base_url}/workflows",
                headers=headers,
                files={"ro_crate": (f"{stem}.crate.zip", crate, "application/zip")},
                data={"workflow[project_ids][]": project_id},
                timeout=60,
            )
        except RequestException as exc:
            raise RuntimeError(f"SEEK {kind} registration failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK {kind} registration failed ({resp.status_code}): {_seek_error(resp)}")
        return int(resp.json()["data"]["id"])

    def register_tool(self, cwl_path: Path, tool_type: str, project_id: int) -> int:
        """Create the tool's SEEK Workflow in ``project_id``; return its id."""
        return self._post_crate("tool", Path(cwl_path).stem, build_tool_crate(cwl_path, tool_type), project_id)

    def register_workflow(self, workflow_cwl: Path, tool_cwls, workflow_type: str, project_id: int) -> int:
        """Create the workflow's SEEK Workflow (tagged ``workflow``) in ``project_id``; return its id."""
        crate = build_workflow_crate(workflow_cwl, tool_cwls, workflow_type)
        return self._post_crate("workflow", Path(workflow_cwl).stem, crate, project_id)

    def delete_workflow(self, workflow_id: int) -> None:
        headers = {"Authorization": "Bearer " + self._api_token, "Accept": "application/json"}
        try:
            resp = requests.delete(f"{self._base_url}/workflows/{workflow_id}", headers=headers, timeout=30)
        except RequestException as exc:
            raise RuntimeError(f"SEEK workflow {workflow_id} delete failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK workflow {workflow_id} delete failed ({resp.status_code}): {_seek_error(resp)}")

    def _jsonapi_headers(self) -> dict:
        return {"Authorization": "Bearer " + self._api_token, "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json"}

    def create_sop(self, title: str, description: str, project_ids, assay_id, workflow_id, content: str) -> int:
        """Create an SOP linking ``assay_id`` to ``workflow_id`` in ``project_ids``; return its id.

        Viewable by those projects' members. Its content is ``content`` as a markdown file:
        a remote-URL blob is checked anonymously by SEEK, so it fails for private workflows.
        """
        body = {"data": {"type": "sops", "attributes": {
            "title": title,
            "description": description,
            "content_blobs": [{"original_filename": "workflow-link.md", "content_type": "text/markdown"}],
            "policy": {"access": "no_access", "permissions": [
                {"resource": {"id": str(p), "type": "projects"}, "access": "view"} for p in project_ids]},
        }, "relationships": {
            "projects": {"data": [{"id": str(p), "type": "projects"} for p in project_ids]},
            "assays": {"data": [{"id": str(assay_id), "type": "assays"}]},
            "workflows": {"data": [{"id": str(workflow_id), "type": "workflows"}]},
        }}}
        try:
            resp = requests.post(f"{self._base_url}/sops", headers=self._jsonapi_headers(), json=body, timeout=60)
        except RequestException as exc:
            raise RuntimeError(f"SEEK SOP create failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK SOP create failed ({resp.status_code}): {_seek_error(resp)}")
        data = resp.json()["data"]
        sop_id = int(data["id"])

        # SEEK's blob link carries SEEK's own host, which may not be reachable from here.
        blob_id = data["attributes"]["content_blobs"][0]["link"].rstrip("/").rsplit("/", 1)[-1]
        headers = {"Authorization": "Bearer " + self._api_token, "Accept": "application/json",
                   "Content-Type": "application/octet-stream"}
        try:
            resp = requests.put(f"{self._base_url}/sops/{sop_id}/content_blobs/{blob_id}",
                                headers=headers, data=content.encode(), timeout=60)
            error = None if resp.status_code < 300 else f"({resp.status_code}): {_seek_error(resp)}"
        except RequestException as exc:
            error = str(exc)
        if error:
            self.delete_sop(sop_id)
            raise RuntimeError(f"SEEK SOP {sop_id} content upload failed {error}")
        return sop_id

    def set_sop_assays(self, sop_id, assay_ids) -> None:
        """Replace the assays SOP ``sop_id`` is linked to."""
        body = {"data": {"type": "sops", "id": str(sop_id), "relationships": {
            "assays": {"data": [{"id": str(a), "type": "assays"} for a in assay_ids]}}}}
        try:
            resp = requests.patch(f"{self._base_url}/sops/{sop_id}", headers=self._jsonapi_headers(),
                                  json=body, timeout=60)
        except RequestException as exc:
            raise RuntimeError(f"SEEK SOP {sop_id} update failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK SOP {sop_id} update failed ({resp.status_code}): {_seek_error(resp)}")

    def delete_sop(self, sop_id) -> None:
        headers = {"Authorization": "Bearer " + self._api_token, "Accept": "application/json"}
        try:
            resp = requests.delete(f"{self._base_url}/sops/{sop_id}", headers=headers, timeout=30)
        except RequestException as exc:
            raise RuntimeError(f"SEEK SOP {sop_id} delete failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK SOP {sop_id} delete failed ({resp.status_code}): {_seek_error(resp)}")
