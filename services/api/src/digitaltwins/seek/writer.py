"""Write to SEEK as the calling user: register tools as Workflows, delete them.

A tool is a SEEK Workflow tagged ``tool`` plus its tool type. It is registered
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


def build_tool_crate(cwl_path: Path, tool_type: str) -> bytes:
    """A zipped Workflow RO-Crate holding the CWL as its main workflow.

    Root ``name`` / ``description`` come from the CWL ``label`` / ``doc`` (the file
    stem when there is no label); root ``keywords`` become the SEEK tags.
    """
    cwl_path = Path(cwl_path)
    cwl = yaml.safe_load(cwl_path.read_text()) or {}
    title = cwl.get("label") or cwl_path.stem
    root = {
        "@id": "./",
        "@type": "Dataset",
        "name": title,
        "keywords": ["tool", tool_type],
        "hasPart": [{"@id": cwl_path.name}],
        "mainEntity": {"@id": cwl_path.name},
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
                "@id": cwl_path.name,
                "@type": ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
                "name": title,
                "programmingLanguage": {"@id": "#cwl"},
            },
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
        zf.write(cwl_path, cwl_path.name)
    return buf.getvalue()


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

    def register_tool(self, cwl_path: Path, tool_type: str, project_id: int) -> int:
        """Create the tool's SEEK Workflow in ``project_id``; return its id."""
        # Authorization only: with ``Accept: application/json`` SEEK treats the call
        # as JSON:API and rejects the multipart crate (422, no ``data`` record).
        headers = {"Authorization": "Bearer " + self._api_token}
        crate = build_tool_crate(cwl_path, tool_type)
        try:
            resp = requests.post(
                f"{self._base_url}/workflows",
                headers=headers,
                files={"ro_crate": (f"{Path(cwl_path).stem}.crate.zip", crate, "application/zip")},
                data={"workflow[project_ids][]": project_id},
                timeout=60,
            )
        except RequestException as exc:
            raise RuntimeError(f"SEEK tool registration failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK tool registration failed ({resp.status_code}): {_seek_error(resp)}")
        return int(resp.json()["data"]["id"])

    def delete_workflow(self, workflow_id: int) -> None:
        headers = {"Authorization": "Bearer " + self._api_token, "Accept": "application/json"}
        try:
            resp = requests.delete(f"{self._base_url}/workflows/{workflow_id}", headers=headers, timeout=30)
        except RequestException as exc:
            raise RuntimeError(f"SEEK workflow {workflow_id} delete failed: {exc}") from exc
        if resp.status_code >= 300:
            raise RuntimeError(f"SEEK workflow {workflow_id} delete failed ({resp.status_code}): {_seek_error(resp)}")
