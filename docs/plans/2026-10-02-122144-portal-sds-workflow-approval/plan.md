# Portal SDS Workflow Upload and Approval: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to carry out this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the portal's Workflow wizard accepts an SDS workflow package such as `tests/data/workflow_image_conversion`, from a local folder, a zip or a Git repo. It builds the package and annotates each step's ports. Approving it hands the package to digitaltwins-api as the approving user, which registers the workflow and its tools in SEEK, MinIO, Postgres and, optionally, FHIR. This is "the tool way".

**Architecture:**
- A new `app/builder/workflow_layout.py` recognises SDS workflow packages, alongside `tool_layout.py`.
- The workflow build copies the package through unchanged.
- A new `app/services/workflow_handoff.py` reuses `tool_handoff`'s session upload, token relay and resume. To allow that, `tool_handoff.run` is parameterised by build model and completion callback.
- On the frontend, the existing composables, the Registration step, the Annotation step, the approval dialog and the Workflow card each gain a workflow-SDS branch.
- Root-`.cwl` workflows keep their current flow.
- The workflow router's authentication matches the tool router and digitaltwins-api's measurement endpoints: every request needs a signed-in user, and writes need `admin` or `researcher`.

**Tech stack:**
- Portal backend: FastAPI, SQLAlchemy, httpx; tests use `unittest`.
- Portal frontend: Vue 3.5, Vuetify, vitest.
- digitaltwins-api: unchanged.

**Spec:**
- User decisions on 2026-10-02:
  - Option B, "the tool way".
  - SDS only; root `.cwl` unchanged.
  - Per-step port FHIR types.
  - Workflow type chosen in the Registration step.
  - Local and Git sources.
- ADR (draft): [docs/decisions/2026-10-02-portal-sds-workflow-approval.md](../../decisions/2026-10-02-portal-sds-workflow-approval.md).
- The API contract: [docs/decisions/2026-10-02-workflow-dataset-ingest.md](../../decisions/2026-10-02-workflow-dataset-ingest.md) and the "Uploading a workflow dataset" section of `services/api/README.md`.

## Root cause (for the record)

[BaseInformationStep.vue:296](../../../services/portal/frontend/src/views/upload-dataset/components/BaseInformationStep.vue#L296) calls `localFolder.refresh(source, true, props.type === 'tool')`, so SDS detection is switched off for workflows. A workflow therefore needs a root `.cwl`. `workflow_image_conversion` keeps its CWLs in `primary/`, so `useLocalFolderInfo.ts:202` reports "No CWL files found in the root of the selected folder".

Every later stage also assumes a root `.cwl`:
- the build (`build_workflow.py:58-73`);
- the Annotation step (it maps each step to an existing portal tool);
- approval (the `sparc-workflow-` stub, using the `fhir_cda` annotator that crashes on `run: tool_x.cwl`).

## Global constraints

- **Backend tests** must never run where `PORTAL_DB_HOST` is set, because the suite would drop the live portal tables. Run them only like this, from `services/portal/backend`:
  ```bash
  docker run --rm --network none -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-portal-backend -c '/app/.venv/bin/python -m unittest discover -s tests -t .'
  ```
  For a single module, use `... -c '/app/.venv/bin/python -m unittest tests.<module> -v'`.
- **Frontend tests and build** run in `node:20-alpine` with Yarn 1.22.22, from `services/portal/frontend`:
  ```bash
  docker run --rm -v $PWD:/app -w /app node:20-alpine sh -c "corepack enable && corepack prepare yarn@1.22.22 --activate && yarn install --frozen-lockfile && yarn test && yarn build"
  ```
  `vue-tsc --noEmit` must report no new errors; 12 already exist.
- **digitaltwins-api is not changed.** The portal uses the existing session contract: `category="workflows"`, `workflow_type`, `seek_project_id`, and `fhir_descriptions = {"workflow": {...}, "workflow_tools": {...}}`.
- **The marker** is `dataset_description.xlsx` (`SDS_MARKER`). An SDS workflow package needs exactly one `primary/workflow_*.cwl`. Every other rule is checked by the API's `load_workflow` at finalize.
- **Workflow types** are `script`, `notebook` and `gui`, the same values the API takes.
- **Root-`.cwl` workflows behave exactly as now**: build, the tool-mapping annotation, and `GET /api/workflow/{id}/approval`. The one difference is authentication (next item).
- **Authentication is consistent with tools and measurements** (user decision, 2026-10-02):
  - `/api/workflow` requires a valid Keycloak token on every endpoint, as `/api/tools` does (`workflow_tool_plugin.py:57`).
  - Writes need `admin` or `researcher` (`WRITER`, as `workflow_tool_plugin.py:58`). digitaltwins-api applies the same rule to measurements: `validate_credentials` for reads and `require_upload_role` for writes.
  - Reads need only a valid token. That includes `/metadata` and `/{expose}/primary/...`, as `/api/tools/metadata` and `/api/tools/get-file/...` do today.
- **Artifacts** use `<REDACTED>` for any secret. Re-sync `docs/artifacts/2026-10-02-122144-portal-sds-workflow-approval/` after every artifact edit.
- **No commits** unless the user asks. If asked, make one Conventional Commit per task.

## Review focus

These are inputs and conditions that no single task's tests naturally cover. Each one has a test added to the task that owns the code.

1. **The camelCase interceptor rewrites object keys.** The tool CWLs must come back as a list of `{cwl_file, content}`, not as a dict keyed by filename (`tool_dicom_to_nifti.cwl` would turn into `toolDicomToNifti.cwl`). Tests are in Task 2 (shape) and Task 7 (lookup by `cwlFile`).
2. **A zip with a wrapper folder** (`workflow_image_conversion/…` inside the zip) must still be recognised as SDS. Tests are in Task 1 (`resolve_project_root`) and Task 5 (a zip spec).
3. **The token expires mid-upload during a workflow approval.** The workflow's own status endpoint must relay a fresh token and resume. The test is in Task 4.
4. **CWL list form**, for `steps: [{id, run, …}]` and for tool `inputs: [{id, …}]`. The test is in Task 7.
5. **Two steps that run the same `tool_*.cwl`.** `workflow_tools` must name that tool only once, because the API rejects two different sections for one tool. The test is in Task 4.

## File map

**Backend (`services/portal/backend`)**

| File | Responsibility |
|---|---|
| `app/builder/workflow_layout.py` (new) | SDS-workflow detection, inspection and CWL reading. |
| `app/builder/source_acquirer.py` | `SourceSpec.workflow_layout`, so Git probes recognise SDS workflows. |
| `app/builder/build_workflow.py` | Copies an SDS package through; checks the type against the layout. |
| `app/models/db_model.py` | `Workflow.workflow_type` and `seek_project_id`; handoff columns on `WorkflowBuild`; the pydantic fields. |
| `app/services/tool_handoff.py` | Extract `open_session` and `tool_section`; parameterise `run`. |
| `app/services/workflow_handoff.py` (new) | Workflow `fhir_descriptions`, `start`, `_complete` and `run`. |
| `app/router/workflow_router.py` | Sign-in on the whole router, with `WRITER` on writes. Uses the layout in upload-source, `/cwl` and probe. New `POST /{id}/approval` and `GET /{id}/approval/status`. The legacy GET refuses SDS workflows; delete removes the platform dataset. |
| `tests/test_workflow_auth.py` (new) | The router's authentication rules, mirroring `tests/test_tools_auth.py`. |
| `tests/tool_app.py` | `make_workflow_client()`. |
| `tests/test_workflow_layout.py`, `tests/test_workflow_sds_source.py`, `tests/test_workflow_build_dataset.py`, `tests/test_workflow_handoff.py` (new) | Tests. |
| `tests/test_tool_handoff.py` | `FakeApi` also records the DELETE query. |

**Frontend (`services/portal/frontend/src`)**

| File | Responsibility |
|---|---|
| `views/upload-dataset/components/utils.ts` | `sdsWorkflowCwls`, `sdsWorkflowCwlResult`, `noWorkflowCwlMessage`. |
| `composables/useLocalFolderInfo.ts`, `composables/useGithubRepoInfo.ts` | `sds: 'tool' \| 'workflow' \| null` replaces `allowSds`; adds `isSds`. |
| `models/types.ts` | `WorkflowType`, `isSds`, and the workflow handoff and probe fields. |
| `views/upload-dataset/components/BaseInformationStep.vue` | The workflow type radio for SDS; the payload. |
| `views/upload-dataset/components/sds_workflow.ts` (new) | Pure helpers: the steps and the ports of each step's tool. |
| `views/upload-dataset/components/BaseAnnotateStep.vue` | The SDS-workflow annotation branch. |
| `bootstrap/workflow_api.ts` | Approval endpoints; `handoffStatus` enrichment. |
| `views/upload-dataset/components/ToolApprovalDialog.vue` | A `kind` prop; the `tool` prop is renamed `item`. |
| `views/upload-dataset/components/WorkflowCard.vue`, `views/upload-dataset/workflow/WorkflowsOverallView.vue`, `views/upload-dataset/workflow-tool/ToolsOverallView.vue` | Wiring. |
| `composables/__tests__/*.spec.ts`, `views/upload-dataset/components/__tests__/*.spec.ts` | Specs. |

---

### Task 1: Backend workflow layout

**Files:**
- Create: `services/portal/backend/app/builder/workflow_layout.py`
- Test: `services/portal/backend/tests/test_workflow_layout.py`

**Interfaces:**
- Consumes: `tool_layout.SDS_MARKER`, and `builder_utils.inspect_uploaded_source`, `read_root_cwl` and `resolve_project_root`.
- Produces:
  - `WorkflowLayout(root: Path, is_sds: bool)`
  - `sds_workflow_cwl(root: Path) -> Path`, which raises `RuntimeError`
  - `detect_workflow_layout(project_dir: Path) -> WorkflowLayout`
  - `inspect_workflow_source(staging_dir: Path, *, want_cwl: bool) -> Dict` (`inspect_uploaded_source` keys plus `is_sds`)
  - `read_workflow_cwl(project_dir: Path) -> Optional[Dict]`: `{cwl_file, content}` for a root workflow; for SDS, `{cwl_file, content, tool_cwls: [{cwl_file, content}]}`

- [ ] **Step 1: Write the failing test** `tests/test_workflow_layout.py`

```python
"""An SDS workflow package: dataset_description.xlsx, one primary/workflow_*.cwl and its tool CWLs.

Run from `backend/`:
    python -m unittest tests.test_workflow_layout
"""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.builder.workflow_layout import (  # noqa: E402
    detect_workflow_layout, inspect_workflow_source, read_workflow_cwl,
)

WORKFLOW = ("cwlVersion: v1.2\nclass: Workflow\ninputs: {src: Directory}\noutputs: {}\n"
            "steps:\n  convert:\n    run: tool_convert.cwl\n    in: {src: src}\n    out: [nifti]\n")
TOOL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: {src: Directory}\noutputs: {nifti: File}\n"


def make_sds_workflow(root: Path) -> Path:
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary" / "workflow_convert.cwl").write_text(WORKFLOW)
    (root / "primary" / "tool_convert.cwl").write_text(TOOL)
    (root / "code" / "tool_convert.py").write_text("print('x')\n")
    return root


class WorkflowLayoutTest(unittest.TestCase):
    def setUp(self):
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def test_an_sds_package_is_detected_through_a_wrapper_folder(self):
        layout = detect_workflow_layout(self.root.parent)
        self.assertTrue(layout.is_sds)
        self.assertEqual(layout.root, self.root)

    def test_an_sds_package_needs_exactly_one_workflow_cwl(self):
        (self.root / "primary" / "workflow_other.cwl").write_text(WORKFLOW)
        with self.assertRaisesRegex(RuntimeError, "exactly one primary/workflow_\\*.cwl"):
            detect_workflow_layout(self.root)

    def test_a_root_cwl_source_is_not_sds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        self.assertFalse(detect_workflow_layout(src).is_sds)

    def test_inspection_reports_the_package_and_its_cwl(self):
        meta = inspect_workflow_source(self.root, want_cwl=True)
        self.assertTrue(meta["is_sds"])
        self.assertTrue(meta["has_cwl"])

    def test_inspection_without_a_workflow_cwl_has_no_cwl(self):
        (self.root / "primary" / "workflow_convert.cwl").unlink()
        meta = inspect_workflow_source(self.root, want_cwl=True)
        self.assertTrue(meta["is_sds"])
        self.assertFalse(meta["has_cwl"])

    def test_reading_returns_the_workflow_and_its_tool_cwls_as_a_list(self):
        cwl = read_workflow_cwl(self.root)
        self.assertEqual(cwl["cwl_file"], "workflow_convert.cwl")
        self.assertEqual(cwl["content"], WORKFLOW)
        # A list, not a dict keyed by filename: the frontend interceptor camelCases object keys.
        self.assertEqual(cwl["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])

    def test_reading_a_root_cwl_source_is_unchanged(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        self.assertEqual(read_workflow_cwl(src), {"cwl_file": "flow.cwl", "content": WORKFLOW})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and check that it fails.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_layout -v'`. Expected: an ImportError (`No module named 'app.builder.workflow_layout'`).
- [ ] **Step 3: Write the minimal implementation** `app/builder/workflow_layout.py`

```python
"""Where a workflow upload keeps its CWL.

A workflow arrives either as source (a ``.cwl`` at the root, whose steps the
Annotation step maps onto portal tools) or as an SDS package
(``dataset_description.xlsx`` at the root, one ``primary/workflow_*.cwl`` and the
``primary/tool_*.cwl`` its steps run), which digitaltwins-api ingests as a
workflow dataset (see docs/decisions/2026-10-02-portal-sds-workflow-approval.md).
The API's ``load_workflow`` checks the rest of the package at finalize.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.builder.tool_layout import SDS_MARKER
from app.utils.builder_utils import inspect_uploaded_source, read_root_cwl, resolve_project_root


@dataclass(frozen=True)
class WorkflowLayout:
    root: Path
    is_sds: bool


def sds_workflow_cwl(root: Path) -> Path:
    cwls = sorted(p for p in (root / "primary").glob("workflow_*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise RuntimeError(f"An SDS workflow package must have exactly one primary/workflow_*.cwl (found: {found})")
    return cwls[0]


def detect_workflow_layout(project_dir: Path) -> WorkflowLayout:
    root = resolve_project_root(Path(project_dir))
    is_sds = (root / SDS_MARKER).is_file()
    if is_sds:
        sds_workflow_cwl(root)
    return WorkflowLayout(root=root, is_sds=is_sds)


def inspect_workflow_source(staging_dir: Path, *, want_cwl: bool) -> Dict[str, Any]:
    """``inspect_uploaded_source`` for workflows: an SDS package's CWL is its primary/workflow_*.cwl."""
    meta = inspect_uploaded_source(staging_dir, want_npm=False, want_cwl=want_cwl)
    root = Path(meta["root"])
    meta["is_sds"] = (root / SDS_MARKER).is_file()
    if meta["is_sds"]:
        meta["has_cwl"] = read_workflow_cwl(root) is not None
    return meta


def read_workflow_cwl(project_dir: Path) -> Optional[Dict[str, Any]]:
    """``read_root_cwl`` for workflows; an SDS package also returns its tool CWLs (a list: see the frontend's camelCasing)."""
    root = resolve_project_root(Path(project_dir))
    if not (root / SDS_MARKER).is_file():
        return read_root_cwl(root)
    try:
        cwl = sds_workflow_cwl(root)
    except RuntimeError:
        return None
    tools = sorted(p for p in (root / "primary").glob("tool_*.cwl") if p.is_file())
    return {
        "cwl_file": cwl.name,
        "content": cwl.read_text(encoding="utf-8"),
        "tool_cwls": [{"cwl_file": p.name, "content": p.read_text(encoding="utf-8")} for p in tools],
    }
```

- [ ] **Step 4: Run the test and check that it passes.** Same command. Expected: 7 tests OK.
- [ ] **Step 5: Commit** (only if the user has asked): `feat(portal): recognise SDS workflow packages`.

---

### Task 2: Use the layout in upload-source, `/cwl` and the Git probe

**Files:**
- Modify:
  - `services/portal/backend/app/router/workflow_router.py`: `upload_workflow_source` (`:67-111`), `get_workflow_cwl` (`:114-137`), `probe_source` (`:391-427`)
  - `services/portal/backend/app/builder/source_acquirer.py`: `SourceSpec` (`:72-74`), `_inspect_with_cwl_content` (`:257-277`), the two callers (`:463`, `:541`)
  - `services/portal/backend/tests/tool_app.py`
- Test: `services/portal/backend/tests/test_workflow_sds_source.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `POST /api/workflow/upload-source` → `{upload_id, folders_in_root, package_version, package_author, has_cwl, is_sds}`. It returns 400 when `has_cwl` is false.
  - `GET /api/workflow/{id}/cwl` → `read_workflow_cwl(...)`.
  - `POST /api/workflow/probe-source` → `data` gains `is_sds`, and `tool_cwls` when the source is SDS.
  - `tool_app.make_workflow_client() -> TestClient`.

- [ ] **Step 0: Check that the workflow router imports offline.** It builds a MinIO client and the FHIR adapter at import. Run `docker run --rm --network none ... -c '/app/.venv/bin/python -c "import tests.tool_app; from app.router import workflow_router"'`.
  - Expected: no error. `boto3` and `fhirpy` don't connect at construction.
  - If it fails, stop and report rather than patching the module.
- [ ] **Step 1: Add `make_workflow_client` to `tests/tool_app.py`**

```python
def make_workflow_client():
    """The /api/workflow router on the same SQLite tables and fake Keycloak."""
    from app.router import workflow_router  # imported late: it builds MinIO / FHIR clients at import

    auth.get_keycloak_client = lambda: FakeKeycloak()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(workflow_router.router)
    return TestClient(app)
```

- [ ] **Step 2: Write the failing test** `tests/test_workflow_sds_source.py`

```python
"""The workflow wizard accepts an SDS workflow package and reads its workflow and tool CWLs.

Run from `backend/`:
    python -m unittest tests.test_workflow_sds_source
"""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.tool_app import bearer, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder.source_acquirer import _inspect_with_cwl_content
from app.models.db_model import SessionLocal, Workflow
from tests.test_workflow_layout import TOOL, WORKFLOW, make_sds_workflow


def _zip(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, f"{root.name}/{p.relative_to(root).as_posix()}")  # with a wrapper folder
    return buf.getvalue()


class WorkflowSdsSourceTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def test_upload_source_accepts_an_sds_workflow_zip(self):
        r = self.client.post("/api/workflow/upload-source", headers=bearer("researcher"),
                             files={"file": ("w.zip", _zip(self.root), "application/zip")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["has_cwl"])
        self.assertTrue(r.json()["is_sds"])

    def test_upload_source_rejects_an_sds_package_without_a_workflow_cwl(self):
        (self.root / "primary" / "workflow_convert.cwl").unlink()
        r = self.client.post("/api/workflow/upload-source", headers=bearer("researcher"),
                             files={"file": ("w.zip", _zip(self.root), "application/zip")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("primary/workflow_*.cwl", r.json()["detail"])

    def test_cwl_returns_the_workflow_and_its_tool_cwls(self):
        with SessionLocal() as db:
            wf = Workflow(name="convert", version="1.0.0", repository_url="local://x", source_type="local",
                          local_archive_path=str(self.root), workflow_type="script")
            db.add(wf)
            db.commit()
            wf_id = wf.id
        r = self.client.get(f"/api/workflow/{wf_id}/cwl", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["cwl_file"], "workflow_convert.cwl")
        self.assertEqual(r.json()["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])

    def test_a_git_probe_inlines_the_tool_cwls(self):
        data = _inspect_with_cwl_content(self.root, workflow_layout=True)
        self.assertTrue(data["is_sds"])
        self.assertEqual((data["cwl_file"], data["cwl_content"]), ("workflow_convert.cwl", WORKFLOW))
        self.assertEqual(data["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])

    def test_a_root_cwl_probe_is_unchanged(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        data = _inspect_with_cwl_content(src, workflow_layout=True)
        self.assertFalse(data["is_sds"])
        self.assertNotIn("tool_cwls", data)


if __name__ == "__main__":
    unittest.main()
```

`Workflow(workflow_type=...)` only exists after Task 3, so **do Task 3 and Task 3b before Task 2**, as `task.md` orders them. The bearer headers are needed once Task 3b is in place.

- [ ] **Step 3: Run the test and check that it fails.** Expected: `upload_source` returns 400 ("No .cwl file found at the root…"), and `_inspect_with_cwl_content` raises a TypeError (unexpected keyword `workflow_layout`).
- [ ] **Step 4: Implement**
  - `source_acquirer.py`:

    ```python
    from app.builder.workflow_layout import inspect_workflow_source, read_workflow_cwl
    # SourceSpec, after tool_layout:
        # Workflow probes also recognise SDS workflow packages (see app.builder.workflow_layout).
        workflow_layout: bool = False

    def _inspect_with_cwl_content(project_dir: Path, tool_layout: bool = False,
                                  workflow_layout: bool = False) -> Dict[str, Any]:
        ...
        if tool_layout:
            result = inspect_tool_source(project_dir, want_cwl=True)
            read_cwl = read_tool_cwl
        elif workflow_layout:
            result = inspect_workflow_source(project_dir, want_cwl=True)
            read_cwl = read_workflow_cwl
        else:
            ...  # unchanged
        if result.get("has_cwl"):
            cwl = read_cwl(project_dir)
            if cwl:
                result["cwl_file"] = cwl["cwl_file"]
                result["cwl_content"] = cwl["content"]
                if "tool_cwls" in cwl:
                    result["tool_cwls"] = cwl["tool_cwls"]
        return result
    ```

    The two callers become `_inspect_with_cwl_content(project_dir, spec.tool_layout, spec.workflow_layout)`.
  - `workflow_router.py`:
    - import `inspect_workflow_source` and `read_workflow_cwl`, and drop the now-unused `inspect_uploaded_source` and `read_root_cwl` imports;
    - in `upload_workflow_source`, use `meta = inspect_workflow_source(staging, want_cwl=True)`; the 400 detail becomes `"No .cwl file found at the root of the uploaded folder, or as the one primary/workflow_*.cwl of an SDS package"`; add `"is_sds": meta["is_sds"]` to the response;
    - in `get_workflow_cwl`, use `result = read_workflow_cwl(staging)`, with the same 404 wording;
    - in `probe_source`, add `workflow_layout=True` to the `SourceSpec`;
    - update the docstrings to match.
- [ ] **Step 5: Run the test and check that it passes.** Also run `tests.test_tool_sds_source`. Its `test_workflow_inspection_ignores_sds_packages` still holds, because `inspect_uploaded_source` is unchanged.
- [ ] **Step 6: Commit:** `feat(portal): read SDS workflow packages in the workflow wizard endpoints`.

---

### Task 3: Model columns and SDS pass-through build

**Files:**
- Modify:
  - `services/portal/backend/app/models/db_model.py`: `Workflow` (`:159-180`), `WorkflowBuild` (`:183-198`), `WorkflowBase` (`:331-337`), `WorkflowResponse` (`:387-395`), `WorkflowBuildResponse` (`:398-408`)
  - `services/portal/backend/app/builder/build_workflow.py`: `create_sparc_dataset` and `build`
  - `services/portal/backend/app/router/workflow_router.py`: `_trigger_workflow_build`, adding `"workflow_type": workflow.workflow_type`
- Test: `services/portal/backend/tests/test_workflow_build_dataset.py`

**Interfaces:**
- Consumes: Task 1, `detect_workflow_layout`.
- Produces:
  - `Workflow.workflow_type: str | None` and `Workflow.seek_project_id: int | None`
  - `WorkflowBuild.handoff_status`, `upload_id`, `dataset_uuid`, `seek_id`, `handoff_error`, `handoff_user`
  - `WorkflowCreate.workflow_type: Optional[Literal["script","notebook","gui"]]`
  - `WorkflowResponse.workflow_type` and `seek_project_id`
  - `WorkflowBuildResponse.handoff_status`, `dataset_uuid`, `seek_id`, `handoff_error`

- [ ] **Step 1: Write the failing test** `tests/test_workflow_build_dataset.py`

```python
"""An SDS workflow package is built as it is; a root-.cwl workflow as before.

Run from `backend/`:
    python -m unittest tests.test_workflow_build_dataset
"""
import tempfile
import unittest
from pathlib import Path

from tests.tool_app import make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder import build_workflow
from app.builder.build_workflow import WorkflowBuilder
from tests.test_workflow_layout import WORKFLOW, make_sds_workflow


class FakeMinio:
    def upload_directory(self, path, name):
        return f"s3://workflows/{name}"


def _files(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


class WorkflowBuildDatasetTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        build_workflow.get_minio_client = lambda bucket: FakeMinio()
        self.builder = WorkflowBuilder(dataset_dir=tempfile.mkdtemp())
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def _build(self, source, workflow_type):
        return self.builder.build({"id": "w1", "name": "convert", "source_type": "local",
                                   "local_archive_path": str(source), "workflow_type": workflow_type})

    def test_an_sds_package_is_copied_as_it_is(self):
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref")
        out = self.builder.create_sparc_dataset(self.root, None, "convert_ab12")
        self.assertEqual(_files(out), [p for p in _files(self.root) if not p.startswith(".git/")])

    def test_a_root_cwl_source_is_built_as_before(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        out = self.builder.create_sparc_dataset(src, None, "flow_ab12")
        self.assertIn("primary/flow.cwl", _files(out))
        self.assertIn("code/flow.cwl", _files(out))

    def test_an_sds_build_succeeds_with_a_workflow_type(self):
        result = self._build(self.root, "script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertIn("primary/workflow_convert.cwl", _files(Path(result["dataset_path"])))

    def test_an_sds_package_needs_a_workflow_type(self):
        result = self._build(self.root, None)
        self.assertFalse(result["success"])
        self.assertIn("needs a workflow type", result["error_message"])

    def test_a_workflow_type_needs_an_sds_package(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        result = self._build(src, "script")
        self.assertFalse(result["success"])
        self.assertIn("not an SDS workflow package", result["error_message"])


if __name__ == "__main__":
    unittest.main()
```

Before Step 3, check that the `local` acquirer returns `Path(local_archive_path)` without copying (`SourceAcquirer.for_type("local", ...)` in `source_acquirer.py`). If it needs extra spec fields, add them to `_build`'s dict.

- [ ] **Step 2: Run the test and check that it fails.** Expected: the pass-through test fails (the files land under `code/`), and the type tests fail (the build succeeds).
- [ ] **Step 3a: Model.** In `db_model.py`:

```python
# Workflow, after local_archive_path:
    # Set (script|notebook|gui) for an SDS workflow package, which approval hands to digitaltwins-api.
    workflow_type = Column(String, nullable=True)
    seek_project_id = Column(Integer, nullable=True)

# WorkflowBuild, after dataset_path (same columns as PluginBuild):
    # Approval hands the build to digitaltwins-api (app/services/workflow_handoff.py).
    handoff_status = Column(String, nullable=True)  # uploading|awaiting_reauth|committing|completed|failed
    upload_id = Column(String, nullable=True)
    dataset_uuid = Column(String, nullable=True)
    seek_id = Column(String, nullable=True)
    handoff_error = Column(Text, nullable=True)
    handoff_user = Column(String, nullable=True)

# WorkflowBase:
    workflow_type: Optional[Literal["script", "notebook", "gui"]] = None
# WorkflowResponse:
    seek_project_id: Optional[int] = None
# WorkflowBuildResponse (mirror PluginBuildResponse :275-278):
    handoff_status: Optional[str] = None
    dataset_uuid: Optional[str] = None
    seek_id: Optional[str] = None
    handoff_error: Optional[str] = None
```

On existing Postgres, `init_db` → `migrate_add_missing_columns` adds these columns, so no hand-written migration is needed. If `tests/test_postgres_integration.py` runs in your environment, add `workflow_type` (in `workflows`) and `handoff_status` (in `workflow_builds`) to its column assertions.
- [ ] **Step 3b: Build.** In `build_workflow.py`:

```python
from app.builder.workflow_layout import detect_workflow_layout

# create_sparc_dataset, right after `dataset_dir.mkdir(...)` and the log line:
            layout = detect_workflow_layout(project_dir)
            if layout.is_sds:
                # digitaltwins-api ingests the package as it is (its metadata, primary/ CWLs and code/).
                for item in layout.root.iterdir():
                    copy_item(item, dataset_dir)  # skips .git, node_modules, dist, build
                logger.info(f"Copied SDS workflow package {layout.root} to {dataset_dir}")
                return dataset_dir

# build(), right after `tmp_source_dir = project_dir`:
            layout = detect_workflow_layout(project_dir)
            workflow_type = workflow.get("workflow_type")
            if layout.is_sds and not workflow_type:
                raise RuntimeError("An SDS workflow package needs a workflow type (script, notebook or gui)")
            if workflow_type and not layout.is_sds:
                raise RuntimeError("A workflow type is set, but the source is not an SDS workflow package "
                                   "(dataset_description.xlsx and one primary/workflow_*.cwl)")
```

  In `_trigger_workflow_build`'s `workflow_dict`, add `"workflow_type": workflow.workflow_type,`.
- [ ] **Step 4: Run the test and check that it passes.** Expected: 5 OK.
- [ ] **Step 5: Commit:** `feat(portal): build SDS workflow packages as they are`.

---

### Task 3b: Authenticate the workflow router (consistent with tools and measurements)

**Files:**
- Modify: `services/portal/backend/app/router/workflow_router.py`: the router (`:51`) and the write endpoints
- Test: `services/portal/backend/tests/test_workflow_auth.py`

**Interfaces:**
- Consumes: `app.utils.auth.get_current_user` and `require_any_role`, and `tests/tool_app.make_workflow_client` (Task 2, Step 1; add it here if Task 2 hasn't run yet).
- Produces:
  - `router = APIRouter(prefix="/api/workflow", dependencies=[Depends(get_current_user)])`
  - `WRITER = Depends(require_any_role("admin", "researcher"))`, which Task 4 uses.
- **Rules:**
  - Every `/api/workflow` endpoint returns 401 without a valid token.
  - These write endpoints return 403 unless the user is `admin` or `researcher`: `POST /create`, `POST /upload-source`, `POST /probe-source`, `POST /{id}/annotation`, `POST /{id}/build`, the deprecated `GET /{id}/build`, the legacy `GET /{id}/approval` (it writes `uuid` and pushes FHIR), and `DELETE /{id}`. Task 4 adds `POST /{id}/approval` with `WRITER`.
  - Every other endpoint needs only a valid token: `/check-name`, `/{id}/cwl`, `/`, `/metadata`, `/{expose}/primary/...`, `/builds…`, `/{id}/builds`, `GET /{id}/annotation` and `GET /{id}`.
- **Frontend:** no change. `http.ts` already sends the Bearer token on every portal request (`:74-82`). There is no other caller of `/api/workflow` in the repo, including `/metadata` and `/{expose}/primary`.

- [ ] **Step 1: Write the failing test** `tests/test_workflow_auth.py`

```python
"""Keycloak on /api/workflow: any valid token reads, admin|researcher write (as /api/tools).

Run from `backend/`:
    python -m unittest tests.test_workflow_auth
"""
import unittest

from tests.tool_app import bearer, make_workflow_client


class WorkflowAuthTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get("/api/workflow/").status_code, 401)
        self.assertEqual(self.client.get("/api/workflow/metadata").status_code, 401)
        self.assertEqual(self.client.post("/api/workflow/create", json={}).status_code, 401)

    def test_an_invalid_token_is_401(self):
        self.assertEqual(self.client.get("/api/workflow/", headers=bearer("expired")).status_code, 401)

    def test_any_valid_token_can_read(self):
        for path in ("/api/workflow/", "/api/workflow/metadata", "/api/workflow/builds"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=bearer("viewer")).status_code, 200)

    def test_writes_need_admin_or_researcher(self):
        writes = [
            ("post", "/api/workflow/create"), ("post", "/api/workflow/upload-source"),
            ("post", "/api/workflow/probe-source"), ("post", "/api/workflow/x/annotation"),
            ("post", "/api/workflow/x/build"), ("get", "/api/workflow/x/build"),
            ("get", "/api/workflow/x/approval"), ("delete", "/api/workflow/x"),
        ]
        for method, path in writes:
            with self.subTest(path=path, method=method):
                r = getattr(self.client, method)(path, headers=bearer("viewer"))
                self.assertEqual(r.status_code, 403, r.text)
                r = getattr(self.client, method)(path, headers=bearer("researcher"))
                self.assertNotIn(r.status_code, (401, 403), r.text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and check that it fails.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_auth -v'`. Expected: no-token requests return 200, 422 or 404 instead of 401, and viewer writes are not 403.
- [ ] **Step 3: Implement.** In `workflow_router.py`:

```python
from app.utils.auth import get_current_user, require_any_role

router = APIRouter(prefix="/api/workflow", dependencies=[Depends(get_current_user)])
WRITER = Depends(require_any_role("admin", "researcher"))
```

  Then add `dependencies=[WRITER]` to the decorators of `/upload-source`, `/create`, `/{workflow_id}/annotation` (POST), `/{workflow_id}/build` (both the GET and the POST), `/probe-source` and `/{workflow_id}/approval` (the legacy GET). `delete_plugin` takes `user: dict = WRITER`, so Task 4 can forward `user["token"]`. Update the router's docstrings where they describe access.
- [ ] **Step 4: Run the test and check that it passes.** Also run `tests.test_workflow_sds_source` if Task 2 is done; it uses bearer headers.
- [ ] **Step 5: Commit:** `feat(portal): require Keycloak on /api/workflow as on /api/tools`.

---

### Task 4: Workflow approval handoff

**Files:**
- Modify:
  - `services/portal/backend/app/services/tool_handoff.py`: `fhir_descriptions` (`:108-123`), `start` (`:162-187`), `run` (`:236-274`)
  - `services/portal/backend/app/router/workflow_router.py`: the legacy `get_workflow_approval` (`:451`), `delete_plugin` (`:523`), and new endpoints
  - `services/portal/backend/tests/test_tool_handoff.py`: `FakeApi` DELETE branch (`:95-97`)
- Create: `services/portal/backend/app/services/workflow_handoff.py`
- Test: `services/portal/backend/tests/test_workflow_handoff.py`

**Interfaces:**
- Consumes: Task 3's columns.
- Produces:
  - `tool_handoff.tool_section(version: str, draft: dict) -> dict`
  - `tool_handoff.open_session(api: Api, build, username: str, body: dict) -> None`, which sets `upload_id`, `handoff_status` and `handoff_user` without committing
  - `tool_handoff.run(build_id, build_cls=PluginBuild, complete=None)`
  - `workflow_handoff.in_platform(workflow) -> bool`
  - `workflow_handoff.fhir_descriptions(workflow) -> dict`
  - `workflow_handoff.start(db, workflow, build, user, seek_project_id, fhir)`
  - `workflow_handoff.run(build_id)`
  - Endpoints:
    - `POST /api/workflow/{id}/approval`: body `{seek_project_id?, fhir=true}`; returns 202 and the status view;
    - `GET /api/workflow/{id}/approval/status`: returns the status view, or `{"handoff_status": null}`;
    - `DELETE /api/workflow/{id}`: also deletes the platform dataset.
- The annotation draft (Task 7 writes it) is `fhir_note = {"steps": [{"step", "tool", "inputs": [{"name","resource"}], "outputs": [{"name","resource","code","system","unit"}]}]}`.

- [ ] **Step 1: Make `FakeApi` record the DELETE query.** This is a test helper only. In `__init__`, add `self.delete_params = []`. In the DELETE branch, before `self.deleted.append(...)`, add `self.delete_params.append(dict(request.url.params))`. Then run `tests.test_tool_handoff` and check that it is still green.
- [ ] **Step 2: Write the failing test** `tests/test_workflow_handoff.py`

```python
"""Approval hands an SDS workflow build to digitaltwins-api as the user; delete removes it there.

Run from `backend/`:
    python -m unittest tests.test_workflow_handoff
"""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import httpx

from tests.tool_app import bearer, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, SessionLocal, Workflow, WorkflowAnnotation, WorkflowBuild
from app.services import tool_handoff
from tests.test_tool_handoff import FakeApi
from tests.test_workflow_layout import make_sds_workflow

STEP = {"tool": "tool_convert.cwl", "inputs": [{"name": "src", "resource": "ImagingStudy"}],
        "outputs": [{"name": "nifti", "resource": "Observation", "code": "123", "system": "http://loinc.org",
                     "unit": ""}]}


class WorkflowHandoffTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()
        self.api = FakeApi()
        tool_handoff.POLL_INTERVAL = 0
        tool_handoff.make_http = lambda: httpx.Client(base_url="http://api.test",
                                                       transport=httpx.MockTransport(self.api))
        tool_handoff.relay.clear()
        with SessionLocal() as db:
            wf = Workflow(name="Convert", version="1.0.0", author="Ann", description="DICOM to NIfTI",
                          repository_url="local://x", source_type="local", workflow_type="script")
            db.add(wf)
            db.commit()
            self.wf_id = wf.id
        self.build_id = self._add_build()

    def _add_build(self):
        root = make_sds_workflow(Path(tempfile.mkdtemp()) / "convert_ab12cd34")
        with SessionLocal() as db:
            build = WorkflowBuild(workflow_id=self.wf_id, build_id=str(uuid.uuid4()),
                                  status=BuildStatus.COMPLETED.value, dataset_path=str(root))
            db.add(build)
            db.commit()
            return build.build_id

    def _annotate(self, steps):
        with SessionLocal() as db:
            db.add(WorkflowAnnotation(workflow_id=self.wf_id, annotation_id=str(uuid.uuid4()),
                                      fhir_note=json.dumps({"steps": steps}), sparc_note=""))
            db.commit()

    def _approve(self, token="researcher", **body):
        return self.client.post(f"/api/workflow/{self.wf_id}/approval",
                                json={"seek_project_id": 11, **body}, headers=bearer(token))

    def _status(self, token="researcher"):
        return self.client.get(f"/api/workflow/{self.wf_id}/approval/status", headers=bearer(token))

    def _workflow(self):
        with SessionLocal() as db:
            wf = db.get(Workflow, self.wf_id)
            db.expunge_all()
            return wf

    def test_approval_commits_the_package_as_a_workflow_dataset(self):
        r = self._approve()

        self.assertEqual(r.status_code, 202, r.text)
        status = self._status().json()
        self.assertEqual(status["handoff_status"], "completed", status)
        self.assertEqual((self._workflow().uuid, self._workflow().seek_project_id), (status["dataset_uuid"], 11))
        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual((session["category"], session["workflow_type"], session["seek_project_id"],
                          session["commit_mode"], session["name"]), ("workflows", "script", 11, "on_finalize", "Convert"))
        self.assertIn("convert_ab12cd34/primary/workflow_convert.cwl", {e["rel_path"] for e in session["manifest"]})

    def test_the_step_annotations_become_workflow_and_tool_descriptions(self):
        self._annotate([{"step": "convert", **STEP}])

        self._approve()

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual(session["fhir_descriptions"], {
            "workflow": {"version": "1.0.0", "author": "Ann", "description": "DICOM to NIfTI", "action": [{
                "step": "convert",
                "input": [{"id": "src", "resource_type": "ImagingStudy"}],
                "output": [{"id": "nifti", "resource_type": "Observation", "code": "123",
                            "system": "http://loinc.org"}]}]},
            "workflow_tools": {"convert": {
                "version": "1.0.0",
                "input": [{"id": "src", "resourceType": "ImagingStudy"}],
                "output": [{"id": "nifti", "resourceType": "Observation", "code": "123",
                            "system": "http://loinc.org"}]}},
        })

    def test_steps_sharing_a_tool_annotate_it_once(self):
        self._annotate([{"step": "a", **STEP}, {"step": "b", **STEP, "inputs": []}])

        self._approve()

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual(list(session["fhir_descriptions"]["workflow_tools"]), ["a"])
        self.assertEqual([a["step"] for a in session["fhir_descriptions"]["workflow"]["action"]], ["a", "b"])

    def test_fhir_can_be_left_out(self):
        self._approve(fhir=False)
        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertNotIn("fhir_descriptions", session)

    def test_an_expired_token_pauses_and_a_fresh_one_resumes(self):
        self.api.expire_after = 2
        self._approve()
        self.assertEqual(self._status().json()["handoff_status"], "awaiting_reauth")

        self.api.valid.add("researcher#2")
        self._status(token="researcher#2")  # relays the fresh token and resumes
        self.assertEqual(self._status(token="researcher#2").json()["handoff_status"], "completed")

    def test_reapproval_replaces_the_previous_dataset_and_its_tools(self):
        self._approve()
        first = self._workflow().uuid
        self.build_id = self._add_build()

        self._approve()

        self.assertNotEqual(self._workflow().uuid, first)
        self.assertEqual(self.api.deleted, [first])
        self.assertEqual(self.api.delete_params, [{"delete_tools": "true"}])

    def test_a_root_cwl_workflow_is_not_approved_to_the_platform(self):
        with SessionLocal() as db:
            db.get(Workflow, self.wf_id).workflow_type = None
            db.commit()
        self.assertEqual(self._approve().status_code, 409)

    def test_the_legacy_approval_refuses_sds_workflows(self):
        r = self.client.get(f"/api/workflow/{self.wf_id}/approval", headers=bearer("researcher"))
        self.assertEqual(r.status_code, 409)

    def test_a_viewer_cannot_approve(self):
        self.assertEqual(self._approve(token="viewer").status_code, 403)

    def test_deleting_an_approved_workflow_deletes_its_dataset_and_tools(self):
        self._approve()
        uuid_ = self._workflow().uuid

        r = self.client.delete(f"/api/workflow/{self.wf_id}", headers=bearer("researcher"))

        self.assertTrue(r.json()["status"], r.json())
        self.assertEqual((self.api.deleted, self.api.delete_params), ([uuid_], [{"delete_tools": "true"}]))
        self.assertIsNone(self._workflow())

    def test_a_failed_platform_delete_keeps_the_workflow(self):
        self._approve()
        self.api.fail_delete = True

        r = self.client.delete(f"/api/workflow/{self.wf_id}", headers=bearer("researcher"))

        self.assertFalse(r.json()["status"])
        self.assertIsNotNone(self._workflow())


if __name__ == "__main__":
    unittest.main()
```

`from tests.test_tool_handoff import FakeApi` imports only `FakeApi`, so the tool `HandoffTest` is not collected twice.

- [ ] **Step 3: Run the test and check that it fails.** Expected: 404 or 405 on `POST /approval`, and an ImportError on `app.services.workflow_handoff` once the router imports it.
- [ ] **Step 4a: Refactor `tool_handoff.py`.** Tool behaviour must not change.

```python
def tool_section(version: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    """A ``workflow_tool`` section: ``version`` plus a port draft's annotated ports."""
    tool: Dict[str, Any] = {"version": version}
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
    return tool


def fhir_descriptions(plugin: Plugin) -> Dict[str, Any]:
    """The tool's ``workflow_tool`` FHIR descriptions: its version plus the Annotation step's port draft."""
    note = plugin.annotation.fhir_note if plugin.annotation else None
    return {"workflow_tool": tool_section(plugin.version, json.loads(note) if note else {})}


def open_session(api: Api, build, username: str, body: Dict[str, Any]) -> None:
    """Open an on-finalize upload session for ``build``'s folder (``body`` without manifest); the caller commits."""
    if build.upload_id:  # an earlier, failed handoff of this build
        try:
            api.request("DELETE", f"/datasets/uploads/{build.upload_id}", expect=(200, 404, 409))
        except ApiError as exc:
            logger.warning("Could not cancel earlier upload session %s: %s", build.upload_id, exc)
    part_size = api.request("GET", "/datasets/uploads/config")["max_part_size"]
    manifest = [{"rel_path": rel, "size": local.stat().st_size,
                 "parts": max(1, math.ceil(local.stat().st_size / part_size))}
                for rel, local in _files(Path(build.dataset_path))]
    created = api.request("POST", "/datasets/uploads", json={
        **body, "source_kind": "folder", "manifest": manifest, "commit_mode": "on_finalize"})
    build.upload_id, build.handoff_status, build.handoff_error = created["upload_id"], "uploading", None
    build.handoff_user = username


def start(db, plugin: Plugin, build: PluginBuild, user: Dict[str, Any], seek_project_id: int, fhir: bool) -> None:
    """Open the API upload session for ``build`` as ``user`` (the caller then runs :func:`run` in the background)."""
    token = user["token"]
    body = {"name": plugin.name, "description": plugin.description, "category": TOOL_CATEGORY,
            "tool_type": TOOL_TYPES[plugin.label], "seek_project_id": seek_project_id}
    if fhir:
        body["fhir_descriptions"] = fhir_descriptions(plugin)
    open_session(Api(make_http(), lambda: token), build, user["username"], body)
    plugin.seek_project_id = seek_project_id
    db.commit()
    relay.put(build.build_id, token)
```

  In `run`, the signature becomes `def run(build_id: str, build_cls=PluginBuild, complete=None) -> None:`, with:
  - `build = db.query(build_cls).filter(build_cls.build_id == build_id).one()`
  - the `_complete(...)` call replaced by `(complete or _tool_complete)(db, api, build, session["dataset_uuid"])`
  - a new `def _tool_complete(db, api, build, dataset_uuid): _complete(db, api, build.plugin, build, dataset_uuid)`
  - the log message changed to `"Handoff failed for build %s"`.

  Then run `tests.test_tool_handoff`. It must stay green before you continue.
- [ ] **Step 4b: Create `app/services/workflow_handoff.py`**

```python
"""Hand an approved SDS workflow build to digitaltwins-api, as the approving user.

Same session protocol and token relay as :mod:`app.services.tool_handoff`. The
API ingests the package as a workflow dataset plus a tool dataset per tool
(docs/decisions/2026-10-02-workflow-dataset-ingest.md); a re-approval or a
delete removes the previous dataset with its tools
(docs/decisions/2026-10-02-portal-sds-workflow-approval.md).
"""
import json
import logging
from typing import Any, Dict

from app.models.db_model import Workflow, WorkflowBuild
from app.services import tool_handoff

logger = logging.getLogger(__name__)

WORKFLOW_CATEGORY = "workflows"
PLACEHOLDER_PREFIX = "sparc-workflow-"  # the legacy approval stub's uuid; never in the platform


def in_platform(workflow: Workflow) -> bool:
    return bool(workflow.uuid) and not workflow.uuid.startswith(PLACEHOLDER_PREFIX)


def fhir_descriptions(workflow: Workflow) -> Dict[str, Any]:
    """``{"workflow": {...}, "workflow_tools": {...}}`` from the Annotation step's ``{"steps": [...]}`` draft.

    Steps that run the same tool share its ActivityDefinition: the first one's ports annotate it.
    """
    note = workflow.annotation.fhir_note if workflow.annotation else None
    draft = json.loads(note) if note else {}
    actions, tools, seen = [], {}, set()
    for step in draft.get("steps") or []:
        actions.append({
            "step": step["step"],
            "input": [{"id": p["name"], "resource_type": p["resource"]}
                      for p in step.get("inputs") or [] if p.get("resource")],
            "output": [{"id": p["name"], "resource_type": p["resource"],
                        **{k: p[k] for k in ("code", "system", "unit") if p.get(k)}}
                       for p in step.get("outputs") or [] if p.get("resource")],
        })
        if step.get("tool") not in seen:
            seen.add(step.get("tool"))
            tools[step["step"]] = tool_handoff.tool_section(workflow.version, step)
    section: Dict[str, Any] = {"version": workflow.version}
    if workflow.author:
        section["author"] = workflow.author
    if workflow.description:
        section["description"] = workflow.description
    section["action"] = actions
    return {"workflow": section, "workflow_tools": tools}


def start(db, workflow: Workflow, build: WorkflowBuild, user: Dict[str, Any], seek_project_id: int,
          fhir: bool) -> None:
    """Open the API upload session for ``build`` as ``user`` (the caller then runs :func:`run` in the background)."""
    token = user["token"]
    body = {"name": workflow.name, "description": workflow.description, "category": WORKFLOW_CATEGORY,
            "workflow_type": workflow.workflow_type, "seek_project_id": seek_project_id}
    if fhir:
        body["fhir_descriptions"] = fhir_descriptions(workflow)
    tool_handoff.open_session(tool_handoff.Api(tool_handoff.make_http(), lambda: token),
                              build, user["username"], body)
    workflow.seek_project_id = seek_project_id
    db.commit()
    tool_handoff.relay.put(build.build_id, token)


def _complete(db, api: tool_handoff.Api, build: WorkflowBuild, dataset_uuid: str) -> None:
    """Record the committed dataset; with re-approval, the previous one (and its tools) is deleted only now."""
    workflow = build.workflow
    seek_id = api.request("GET", f"/datasets/{dataset_uuid}")["dataset"].get("seek_id")
    previous = workflow.uuid if in_platform(workflow) else None
    build.dataset_uuid, build.seek_id, build.handoff_status = dataset_uuid, seek_id, "completed"
    workflow.uuid = dataset_uuid
    db.commit()
    if previous and previous != dataset_uuid:
        try:
            api.request("DELETE", f"/datasets/{previous}", expect=(200, 404), params={"delete_tools": "true"})
            db.query(WorkflowBuild).filter(WorkflowBuild.dataset_uuid == previous).update({"dataset_uuid": None})
        except Exception as exc:
            logger.warning("Previous dataset %s of workflow %s not deleted: %s", previous, workflow.id, exc)
            build.handoff_error = f"Approved, but the previous version {previous} could not be deleted: {exc}"
        db.commit()


def run(build_id: str) -> None:
    tool_handoff.run(build_id, WorkflowBuild, _complete)
```

- [ ] **Step 4c: Router.** In `workflow_router.py`:

```python
from app.services import tool_handoff, workflow_handoff
# get_current_user and WRITER come from Task 3b.


class WorkflowApprovalRequest(BaseModel):
    seek_project_id: Optional[int] = None  # defaults to the project of the previous approval
    fhir: bool = True                      # push the PlanDefinition and an ActivityDefinition per tool


@router.post("/{workflow_id}/approval", status_code=202)
def approve_workflow(workflow_id: str, background: BackgroundTasks, body: Optional[WorkflowApprovalRequest] = None,
                     user: dict = WRITER, db: Session = Depends(get_db)):
    """Hand the latest completed build of an SDS workflow to digitaltwins-api as the calling user.

    The API registers the workflow and each of its tools in SEEK and stores them
    under new dataset UUIDs; once that commits, a previously approved version
    (with its tools) is deleted. Poll ``GET .../approval/status`` for progress.
    """
    body = body or WorkflowApprovalRequest()
    workflow, latest = get_latest_build_record(workflow_id, "workflow", db)
    if not workflow.workflow_type:
        raise HTTPException(status_code=409, detail="Only SDS workflow packages are approved to the platform")
    if latest is None or latest.status != BuildStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="The latest build has not completed")
    if latest.handoff_status in tool_handoff.ACTIVE:
        raise HTTPException(status_code=409, detail="This build is already being approved")
    if latest.handoff_status == "completed":
        raise HTTPException(status_code=409, detail="This build is already approved; rebuild to approve a new version")
    seek_project_id = body.seek_project_id or workflow.seek_project_id
    if seek_project_id is None:
        raise HTTPException(status_code=400, detail="seek_project_id is required")
    try:
        workflow_handoff.start(db, workflow, latest, user, seek_project_id, body.fhir)
    except tool_handoff.NeedsReauth:
        raise HTTPException(status_code=401, detail="digitaltwins-api rejected the token")
    except tool_handoff.ApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    background.add_task(workflow_handoff.run, latest.build_id)
    return tool_handoff.status_view(latest)


@router.get("/{workflow_id}/approval/status")
def workflow_approval_status(workflow_id: str, background: BackgroundTasks, user: dict = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Handoff progress of the workflow's most recent approval; the approver's poll also resumes a paused handoff."""
    if db.query(Workflow).filter(Workflow.id == workflow_id).first() is None:  # type: ignore
        raise HTTPException(status_code=404, detail="Workflow not found")
    build = (db.query(WorkflowBuild)
             .filter(WorkflowBuild.workflow_id == workflow_id, WorkflowBuild.upload_id.isnot(None))
             .order_by(WorkflowBuild.created_at.desc()).first())
    if build is None:
        return {"handoff_status": None}
    if build.handoff_status in tool_handoff.ACTIVE and tool_handoff.relay_token(build, user):
        if not tool_handoff.is_running(build.build_id):
            background.add_task(workflow_handoff.run, build.build_id)
    return tool_handoff.status_view(build)
```

  - **Legacy `get_workflow_approval`.** Right after `get_latest_build_record(...)`, add: `if workflow.workflow_type: raise HTTPException(status_code=409, detail="SDS workflow packages are approved with POST /api/workflow/{id}/approval")`.
  - **`delete_plugin`.** Task 3b already gives it `user: dict = WRITER`. Replace the `if workflow.uuid:` FHIR block's guard as follows; everything else stays the same:

```python
            # An approved SDS workflow lives in the platform: digitaltwins-api removes it with its tools
            # (Postgres, MinIO, SEEK, FHIR). Done first, so a failure keeps the workflow.
            if workflow_handoff.in_platform(workflow) and workflow.workflow_type:
                api = tool_handoff.Api(tool_handoff.make_http(), lambda: user["token"])
                api.request("DELETE", f"/datasets/{workflow.uuid}", expect=(200, 404),
                            params={"delete_tools": "true"})
            elif workflow.uuid:
                ...  # the existing PlanDefinition cleanup, unchanged
```

  The `and workflow.workflow_type` condition keeps root-`.cwl` workflows on the old path even if a stub UUID were ever reformatted.
- [ ] **Step 5: Run the test and check that it passes.** Run `tests.test_workflow_handoff`, `tests.test_tool_handoff` and `tests.test_tools_auth`. Expected: all OK.
- [ ] **Step 6: Commit:** `feat(portal): hand approved SDS workflows to digitaltwins-api`.

---

### Task 5: Frontend SDS-workflow detection

**Files:**
- Modify:
  - `services/portal/frontend/src/views/upload-dataset/components/utils.ts`: after `noToolCwlMessage` (`:94-96`)
  - `services/portal/frontend/src/composables/useLocalFolderInfo.ts`
  - `services/portal/frontend/src/composables/useGithubRepoInfo.ts`
  - `services/portal/frontend/src/models/types.ts`: `ProbeSourceResponse` data (`:106`)
- Test:
  - `services/portal/frontend/src/composables/__tests__/useLocalFolderInfo.spec.ts`
  - `services/portal/frontend/src/composables/__tests__/useGithubRepoInfo.spec.ts`

**Interfaces:**
- Produces:
  - `type SdsKind = 'tool' | 'workflow'`
  - `useLocalFolderInfo().refresh(source, checkCwl, sds: SdsKind | null = null)`
  - `LocalFolderInfo.isSds: boolean` and `GitRepoInfo.isSds: boolean`
  - `ProbeSourceResponse.data.toolCwls?: { cwlFile: string; content: string }[]`
  - `sdsWorkflowCwls(names)`, `sdsWorkflowCwlResult(ok)`, `noWorkflowCwlMessage(where)`

- [ ] **Step 1: Write the failing spec** `useLocalFolderInfo.spec.ts`

```ts
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import { useLocalFolderInfo } from '@/composables/useLocalFolderInfo';
import type { LocalSource } from '@/bootstrap/upload_source';

const file = (path: string) => {
  const f = new File(['x'], path.split('/').pop()!);
  Object.defineProperty(f, 'webkitRelativePath', { value: path });
  return f;
};
const folder = (paths: string[]): LocalSource =>
  ({ kind: 'folder', rootName: 'workflow_convert', files: paths.map(file) }) as LocalSource;
const SDS_WORKFLOW = [
  'workflow_convert/dataset_description.xlsx',
  'workflow_convert/primary/workflow_convert.cwl',
  'workflow_convert/primary/tool_a.cwl',
  'workflow_convert/primary/tool_b.cwl',
  'workflow_convert/code/tool_a.py',
];

describe('useLocalFolderInfo', () => {
  it('accepts an SDS workflow package for a workflow', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(SDS_WORKFLOW), true, 'workflow');
    expect(info.value.isSds).toBe(true);
    expect(info.value.cwlExists).toBe(true);
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });

  it('needs exactly one primary/workflow_*.cwl', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder([...SDS_WORKFLOW, 'workflow_convert/primary/workflow_other.cwl']), true, 'workflow');
    expect(info.value.cwlExists).toBe(false);
    expect(info.value.cwlRepoErr?.message).toContain('primary/workflow_*.cwl');
  });

  it('keeps the root-.cwl rule for a workflow source tree', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(['flow/flow.cwl', 'flow/scripts/run.py']), true, 'workflow');
    expect(info.value.isSds).toBe(false);
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });

  it('still requires one primary/tool_*.cwl for a tool', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(SDS_WORKFLOW), true, 'tool'); // two tool CWLs
    expect(info.value.cwlExists).toBe(false);
  });

  it('reads an SDS workflow zip with a wrapper folder', async () => {
    const zip = new JSZip();
    SDS_WORKFLOW.forEach((p) => zip.file(p, 'x'));
    const blob = new Blob([await zip.generateAsync({ type: 'uint8array' })]);
    const { info, refresh } = useLocalFolderInfo();
    await refresh({ kind: 'zip', rootName: 'workflow_convert', blob } as LocalSource, true, 'workflow');
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });
});
```

  Check the `LocalSource` field names against `bootstrap/upload_source.ts` (`kind`, `rootName`, `files`, `blob`) and adjust them if they differ. If jsdom's `Blob` can't be read by JSZip, construct the source from `zip.generateAsync({ type: 'blob' })` instead.
- [ ] **Step 2: Write the failing spec** `useGithubRepoInfo.spec.ts`. Mock `getRepoContents` with `vi.mock('@/views/upload-dataset/components/utils', async (orig) => ({ ...(await orig()), getRepoContents: vi.fn() }))`, and stub `global.fetch` for `findPackageJsonPaths` so it returns `{ tree: [] }`. Cover two cases:
  1. **Public GitHub.** The root listing has `dataset_description.xlsx` and the dirs `primary` and `code`. `primary` lists `workflow_convert.cwl`, `tool_a.cwl` and `tool_b.cwl`. After `refresh(url, true, { kind: 'workflow' })`, expect `info.isSds === true` and `cwlRepoErr.available === true`.
  2. **Backend probe.** Mock `useProbeWorkflowSource` to return `{ ok: true, data: { foldersInRoot: [], hasCwl: true, isSds: true } }` and use `auth: { token: 't' }`. Expect `cwlRepoErr.message` to equal `sdsWorkflowCwlResult(true).message`.
- [ ] **Step 3: Run the specs and check that they fail.** Run `yarn test`. Expected: the workflow cases fail, because `'workflow'` is treated like `false` (truthy, but no workflow branch) and there is no `isSds`.
- [ ] **Step 4: Implement.**
  - `utils.ts`:

    ```ts
    const SDS_WORKFLOW_CWL = /^workflow_.*\.cwl$/;

    export const sdsWorkflowCwls = (primaryFiles: string[]) => primaryFiles.filter((name) => SDS_WORKFLOW_CWL.test(name));

    export const sdsWorkflowCwlResult = (ok: boolean): CheckNameResponse => ok
      ? { available: true, message: "Detected an SDS workflow package: approving it registers the workflow and its tools." }
      : { available: false, message: "An SDS workflow package must have exactly one primary/workflow_*.cwl." };

    export const noWorkflowCwlMessage = (where: string) =>
      `No CWL found in the ${where}. Expected a .cwl at the root (source code), ` +
      `or one primary/workflow_*.cwl in an SDS package (${SDS_MARKER} at the root).`;
    ```

  - `useLocalFolderInfo.ts`:
    - add `isSds: boolean` to `LocalFolderInfo`, to the initial state and to `reset()`;
    - `refresh(source, checkCwl = false, sds: SdsKind | null = null)` passes `sds` down instead of `allowSds`, and so do `refreshFromFiles` and `refreshFromZip`;
    - `applyCwlCheck(rootFolders, rootHasCwl, scan, checkCwl, sds, where)` becomes:

    ```ts
    const isSds = !!sds && scan.rootFiles.has(SDS_MARKER);
    const sdsOk = (sds === 'workflow' ? sdsWorkflowCwls : sdsToolCwls)(scan.primaryFiles).length === 1;
    info.value.isSds = isSds;
    info.value.foldersInRoot = Array.from(isSds ? scan.codeFolders : rootFolders).sort();
    info.value.cwlExists = isSds ? sdsOk : rootHasCwl;
    if (checkCwl) {
      if (isSds) {
        info.value.cwlRepoErr = sds === 'workflow' ? sdsWorkflowCwlResult(sdsOk) : sdsCwlResult(sdsOk);
      } else {
        info.value.cwlRepoErr = rootHasCwl
          ? { available: true, message: '' }
          : {
              available: false,
              message: sds === 'tool' ? noToolCwlMessage(where)
                : sds === 'workflow' ? noWorkflowCwlMessage(where)
                : `No CWL files found in the root of the ${where}.`,
            };
      }
    }
    ```

    Rename the `SdsScan` parameter `sds` to `scan` inside `applyCwlCheck`, so it doesn't clash with the new parameter. Export `type SdsKind = 'tool' | 'workflow'` from this file. Update the docstring `@param`.
  - `useGithubRepoInfo.ts`:
    - add `isSds` to `GitRepoInfo`, its initial state and its reset points;
    - `refreshPublicGithub(normalizedUrl, checkCwl, sds: SdsKind)` checks `items.some(... SDS_MARKER)` for both kinds and calls `refreshPublicGithubSds(normalizedUrl, items, checkCwl, sds)`, which sets `info.value.isSds = true` and uses `sdsWorkflowCwls` / `sdsWorkflowCwlResult` when `sds === 'workflow'`;
    - the no-root message picks `noToolCwlMessage` or `noWorkflowCwlMessage` by `sds`;
    - in `refreshViaBackend`, set `info.value.isSds = !!res.data.isSds`; when it is SDS, use `backendKind === 'workflow' ? sdsWorkflowCwlResult(res.data.hasCwl) : sdsCwlResult(res.data.hasCwl)`; the no-root message is chosen by `backendKind` in the same way;
    - in `refresh(...)`, pass `opts.kind` instead of `opts.kind === 'tool'`.
  - `types.ts`: add `toolCwls?: { cwlFile: string; content: string }[]` to the probe data, next to `isSds`.
  - `BaseInformationStep.vue:296` becomes `await localFolder.refresh(formData.source, true, props.type);`.
- [ ] **Step 5: Run the specs and check that they pass.** Run `yarn test`. Expected: all green, including the 20 existing specs.
- [ ] **Step 6: Commit:** `feat(portal): detect SDS workflow packages in the workflow wizard`.

---

### Task 6: Workflow type in the Registration step

**Files:**
- Modify:
  - `services/portal/frontend/src/models/types.ts`: `WorkflowInformationStep`, `WorkflowResponse`
  - `services/portal/frontend/src/views/upload-dataset/components/BaseInformationStep.vue`

**Interfaces:**
- Consumes: `repoInfo.isSds` from Task 5.
- Produces:
  - `type WorkflowType = 'script' | 'notebook' | 'gui'`
  - `WorkflowInformationStep.workflowType?: WorkflowType`
  - `WorkflowResponse.workflowType?: string` (already there), plus `seekProjectId?: number` and `handoffStatus?: HandoffStatus | null`
  - The create payload carries `workflowType`, which reaches the backend as `workflow_type`, only for SDS sources.

This task is template wiring, about 15 lines with no branching logic of its own. It is verified by `vue-tsc` and the live check in Task 9, not by a component spec: mounting `BaseInformationStep` needs the dropzone, both composables and the name check mocked. Say so in the walkthrough.

- [ ] **Step 1: Types.**

```ts
export type WorkflowType = 'script' | 'notebook' | 'gui'
// WorkflowInformationStep:
    workflowType?: WorkflowType
// WorkflowResponse:
    seekProjectId?: number
    // Handoff to the platform of the latest build (SDS workflows; see ToolApprovalStatus).
    handoffStatus?: HandoffStatus | null
```

- [ ] **Step 2: Template.** Inside `<CommonInfoForm>`'s default slot, before the tool GUI `<div>`, add:

```vue
        <!-- Workflow + SDS package: the API needs its type -->
        <div v-if="type === 'workflow' && repoInfo.isSds" class="w-100">
          <h4 class="my-2">Choose the workflow type *</h4>
          <v-radio-group v-model="formData.workflowType" inline class="w-100 d-flex justify-start">
            <v-radio color="#5fd6e8" label="Script" value="script" />
            <v-radio color="#5fd6e8" label="Notebook" value="notebook" class="ml-2" />
            <v-radio color="#5fd6e8" label="Web GUI" value="gui" class="ml-2" />
          </v-radio-group>
        </div>
```

- [ ] **Step 3: Script.**
  - `formData` becomes `reactive<ToolInformationStep & { source?: LocalSource; workflowType?: WorkflowType }>`, with `workflowType: undefined`.
  - In `validate()`, the workflow branch becomes `return valid && !!cwlCheck.value && (!repoInfo.value.isSds || !!formData.workflowType);`.
  - In `handleSubmit`, `workflowData` gains `workflowType: repoInfo.value.isSds ? formData.workflowType : undefined,`.
  - The workflow alert text becomes `'... workflow name, and, for an SDS package, its workflow type.'`.
- [ ] **Step 4: Verify.** Run `vue-tsc --noEmit`; expect no new errors. Run `yarn test`; it should stay green.
- [ ] **Step 5: Commit:** `feat(portal): choose the workflow type of an SDS workflow package`.

---

### Task 7: Annotation step for SDS workflows

**Files:**
- Create: `services/portal/frontend/src/views/upload-dataset/components/sds_workflow.ts`
- Modify:
  - `services/portal/frontend/src/views/upload-dataset/components/BaseAnnotateStep.vue`
  - `services/portal/frontend/src/bootstrap/workflow_api.ts`: the `useGetWorkflowLocalCwl` return type
- Test: `services/portal/frontend/src/views/upload-dataset/components/__tests__/sds_workflow.spec.ts`

**Interfaces:**
- Consumes:
  - `GET /api/workflow/{id}/cwl` → `{cwlFile, content, toolCwls?: [{cwlFile, content}]}` (Task 2)
  - probe `data.toolCwls` (Task 5)
- Produces:
  - `SdsStepAnnotation { step: string; tool: string; inputs: {name, resource}[]; outputs: {name, resource, code, system, unit}[] }`
  - `sdsWorkflowSteps(workflowCwl: any, toolCwls: { cwlFile: string; content: any }[]): SdsStepAnnotation[]`, which throws on a step whose tool is missing
  - The annotation is submitted as `fhirNote = JSON.stringify({ steps })`. Task 4's `fhir_descriptions` reads this shape.

- [ ] **Step 1: Write the failing spec** `sds_workflow.spec.ts`

```ts
import { describe, expect, it } from 'vitest';
import { sdsWorkflowSteps } from '../sds_workflow';

const tool = (cwlFile: string, inputs: any, outputs: any) => ({ cwlFile, content: { class: 'CommandLineTool', inputs, outputs } });

describe('sdsWorkflowSteps', () => {
  it('maps each step to the ports of the tool it runs (map form)', () => {
    const wf = { steps: { convert: { run: 'tool_a.cwl', in: {}, out: [] } } };
    expect(sdsWorkflowSteps(wf, [tool('tool_a.cwl', { src: 'Directory' }, { nifti: 'File' })])).toEqual([{
      step: 'convert', tool: 'tool_a.cwl',
      inputs: [{ name: 'src', resource: '' }],
      outputs: [{ name: 'nifti', resource: '', code: '', system: '', unit: '' }],
    }]);
  });

  it('accepts list-form steps and ports', () => {
    const wf = { steps: [{ id: 'convert', run: 'tool_a.cwl' }] };
    const [step] = sdsWorkflowSteps(wf, [tool('tool_a.cwl', [{ id: 'src', type: 'Directory' }], [{ id: 'nifti' }])]);
    expect(step.inputs.map((p) => p.name)).toEqual(['src']);
    expect(step.outputs.map((p) => p.name)).toEqual(['nifti']);
  });

  it('names a step whose tool CWL is not in primary/', () => {
    const wf = { steps: { convert: { run: 'tool_missing.cwl' } } };
    expect(() => sdsWorkflowSteps(wf, [])).toThrow(/convert.*tool_missing\.cwl/);
  });
});
```

- [ ] **Step 2: Run the spec and check that it fails.** Run `yarn test`. Expected: the module is not found.
- [ ] **Step 3: Implement `sds_workflow.ts`**

```ts
/** An SDS workflow package's steps, each with the ports of the primary/tool_*.cwl it runs. */
export interface SdsStepAnnotation {
  step: string;
  tool: string;
  inputs: { name: string; resource: string }[];
  outputs: { name: string; resource: string; code: string; system: string; unit: string }[];
}

/** CWL ports and steps come as a map (`{id: …}`) or a list (`[{id, …}]`). */
const ids = (section: any): string[] =>
  Array.isArray(section) ? section.map((entry) => entry.id) : Object.keys(section ?? {});

export function sdsWorkflowSteps(workflowCwl: any, toolCwls: { cwlFile: string; content: any }[]): SdsStepAnnotation[] {
  const steps = workflowCwl?.steps ?? {};
  const entries: [string, any][] = Array.isArray(steps) ? steps.map((s: any) => [s.id, s]) : Object.entries(steps);
  return entries.map(([step, def]) => {
    const tool = toolCwls.find((t) => t.cwlFile === def?.run);
    if (!tool) throw new Error(`Step ${step} runs ${def?.run}, which is not a tool CWL in primary/`);
    return {
      step,
      tool: tool.cwlFile,
      inputs: ids(tool.content?.inputs).map((name) => ({ name, resource: '' })),
      outputs: ids(tool.content?.outputs).map((name) => ({ name, resource: '', code: '', system: '', unit: '' })),
    };
  });
}
```

- [ ] **Step 4: Run the spec and check that it passes.**
- [ ] **Step 5: Wire up `BaseAnnotateStep.vue`.**
  - `const isSdsWorkflow = computed(() => props.type === 'workflow' && !!(props.data as WorkflowResponse | undefined)?.workflowType);` and `const sdsSteps = ref<SdsStepAnnotation[]>([]);`.
  - The existing workflow `<template v-if="type === 'workflow'">` becomes `v-if="type === 'workflow' && !isSdsWorkflow"`.
  - Add a new branch before it, `<template v-if="isSdsWorkflow">`. It has the heading "Workflow FHIR Annotation". For each `s` in `sdsSteps` it shows "Step {{ i + 1 }}: {{ s.step }} ({{ s.tool }})", then the tool branch's inputs and outputs controls (the `v-select` of `fhirResources`; Code, Code System and Unit for `Observation`), bound to `s.inputs` and `s.outputs`. A `loadError` `v-alert` is shown when loading fails.
  - **Loading.** In `onMounted`'s workflow branch, `if (isSdsWorkflow.value) { … return; }` before `useWorkflowTools()`. SDS workflows don't pick portal tools. It does this:

```ts
async function loadSdsWorkflowCwls(workflow: WorkflowResponse): Promise<{ content: any; tools: { cwlFile: string; content: any }[] }> {
  const parseAll = (tools: { cwlFile: string; content: string }[] = []) =>
    tools.map((t) => ({ cwlFile: t.cwlFile, content: parseCwlText(t.content) }));
  if (workflow.sourceType === 'local') {
    const res = await useGetWorkflowLocalCwl(workflow.id);
    return { content: parseCwlText(res.content), tools: parseAll(res.toolCwls) };
  }
  if (_canUsePublicGithubPath(workflow.sourceType)) {
    const primary = ((await getRepoContents(workflow.repositoryUrl, 'primary')).data as GitContent[])
      .filter((item) => item.type === 'file' && item.name.endsWith('.cwl'));
    const read = async (name: string) =>
      atob(((await getRepoContents(workflow.repositoryUrl, `primary/${name}`)).data.content as string).replace(/\n/g, ''));
    const [wfName] = sdsWorkflowCwls(primary.map((item) => item.name));
    if (!wfName) throw new Error('No primary/workflow_*.cwl in the repository.');
    const tools = await Promise.all(primary.filter((item) => item.name.startsWith('tool_'))
      .map(async (item) => ({ cwlFile: item.name, content: parseCwlText(await read(item.name)) })));
    return { content: parseCwlText(await read(wfName)), tools };
  }
  const res = await useProbeWorkflowSource({
    sourceType: workflow.sourceType as Exclude<SourceType, 'local'>, url: workflow.repositoryUrl,
    token: props.pendingAuth?.token, authUsername: props.pendingAuth?.authUsername,
    verifySsl: props.pendingAuth?.verifySsl ?? true,
  });
  if (!res.ok || !res.data.cwlContent) throw new Error(`Failed to fetch CWL: ${res.ok ? 'none found' : res.message}`);
  return { content: parseCwlText(res.data.cwlContent), tools: parseAll(res.data.toolCwls) };
}
// in onMounted:
    if (isSdsWorkflow.value) {
      try {
        const { content, tools } = await loadSdsWorkflowCwls(workflow);
        sdsSteps.value = sdsWorkflowSteps(content, tools);
        cwlObj.value = content;
      } catch (err: any) {
        loadError.value = err?.message ?? String(err);
      }
      return;
    }
```

  - **The `cwlObj` watcher.** Return early when `isSdsWorkflow.value`, because the steps come from `sdsWorkflowSteps`.
  - **`handleAnnotationSubmit`.** In the workflow case, emit `fhirNote: JSON.stringify(isSdsWorkflow.value ? { steps: sdsSteps.value } : annotateSteps.value)`.
  - **`workflow_api.ts`.** `useGetWorkflowLocalCwl` returns `Promise<{ cwlFile: string; content: string; toolCwls?: { cwlFile: string; content: string }[] }>`.
  - **Imports.** Add `sdsWorkflowCwls` from `./utils`, and `sdsWorkflowSteps` and `SdsStepAnnotation` from `./sds_workflow`.
- [ ] **Step 6: Verify.** Run `yarn test`, then `vue-tsc --noEmit`; expect no new errors.
- [ ] **Step 7: Commit:** `feat(portal): annotate the steps of an SDS workflow package`.

---

### Task 8: Approval dialog, card and hub

**Files:**
- Modify:
  - `services/portal/frontend/src/bootstrap/workflow_api.ts`
  - `services/portal/frontend/src/views/upload-dataset/components/ToolApprovalDialog.vue`
  - `services/portal/frontend/src/views/upload-dataset/workflow-tool/ToolsOverallView.vue` (`:55`)
  - `services/portal/frontend/src/views/upload-dataset/components/WorkflowCard.vue`
  - `services/portal/frontend/src/views/upload-dataset/workflow/WorkflowsOverallView.vue`
- Test:
  - `services/portal/frontend/src/views/upload-dataset/components/__tests__/ToolApprovalDialog.spec.ts` (new)
  - `services/portal/frontend/src/views/upload-dataset/components/__tests__/cards.spec.ts`

**Interfaces:**
- Consumes: Task 4's endpoints and Task 6's `WorkflowResponse.handoffStatus`.
- Produces:
  - `useWorkflowPlatformApproval(id, { seekProjectId?, fhir? }): Promise<ToolApprovalStatus>`
  - `useWorkflowApprovalStatus(id): Promise<ToolApprovalStatus>`
  - `ToolApprovalDialog` props `{ item: ToolResponse | WorkflowResponse | null; kind?: 'tool' | 'workflow' }`
  - `WorkflowCard` emits `approve-platform(workflow)` and `approval-done(status)`.

- [ ] **Step 1: Write the failing specs.**
  - `ToolApprovalDialog.spec.ts`: mock `@/bootstrap/tool_api` (`useSeekProjects` → `[{ id: 11, title: 'P' }]`, `useToolApproval`, `useToolApprovalStatus`, `usePlatformDataset`, `useRetryToolFhir`) and `@/bootstrap/workflow_api` (`useWorkflowPlatformApproval`, `useWorkflowApprovalStatus`), and stub `vue-toastification`. Use the `src/testing` Vuetify setup, the same way `DeletePlatformDatasetDialog.spec.ts` does. Cover two cases:
    1. With `kind="workflow"` and `item={ id: 'w1', name: 'Convert', seekProjectId: 11 }`, opening and pressing Approve calls `useWorkflowPlatformApproval('w1', { seekProjectId: 11, fhir: true })` and not `useToolApproval`. Then the status poll calls `useWorkflowApprovalStatus('w1')`.
    2. With the default kind, Approve calls `useToolApproval`. This guards the rename.
  - `cards.spec.ts`: add two cases.
    1. A portal workflow with `workflowType: 'script'` (not `platformOnly`): its menu's "Submit to approval" emits `approve-platform` with the workflow.
    2. A portal workflow without `workflowType` still emits `submit-approve` with its id.
- [ ] **Step 2: Run the specs and check that they fail.**
- [ ] **Step 3: Implement.**
  - `workflow_api.ts`:

    ```ts
    /** Hand the latest build of an SDS workflow to the platform (as the signed-in user). */
    export async function useWorkflowPlatformApproval(id: string, body: { seekProjectId?: number; fhir?: boolean }) {
      return http.post<ToolApprovalStatus>(`/workflow/${id}/approval`, body);
    }

    /** Handoff progress. Polling it also hands the backend a fresh token, which resumes a paused handoff. */
    export async function useWorkflowApprovalStatus(id: string) {
      return http.get<ToolApprovalStatus>(`/workflow/${id}/approval/status`);
    }
    ```

    `useWorkflow()` passes an `enrichFn`, `async (_w, latestBuild) => ({ handoffStatus: latestBuild.handoffStatus ?? null })`, as `useWorkflowTools` does for tools. Import `ToolApprovalStatus`.
  - `ToolApprovalDialog.vue`:
    - the props become `defineProps<{ item: ToolResponse | WorkflowResponse | null; kind?: 'tool' | 'workflow' }>()`;
    - `const calls = computed(() => props.kind === 'workflow' ? { approve: useWorkflowPlatformApproval, status: useWorkflowApprovalStatus } : { approve: useToolApproval, status: useToolApprovalStatus });`
    - replace `props.tool` with `props.item` throughout, and `useToolApproval(` / `useToolApprovalStatus(` with `calls.value.approve(` / `calls.value.status(`;
    - the info text becomes `The latest build of <strong>{{ item?.name }}</strong> is registered in SEEK as you, and stored in the platform{{ kind === 'workflow' ? ', with a tool dataset for each of its tools' : '' }}. Approving a rebuild replaces its previous version.`;
    - the FHIR checkbox label is `kind === 'workflow' ? 'Publish to FHIR (a PlanDefinition, and an ActivityDefinition per tool)' : 'Publish to FHIR (ActivityDefinition with the port annotations)'`;
    - the "running" hint says "the Workflow Hub keeps it going" for workflows.

    `useRetryToolFhir` and `usePlatformDataset` work for any dataset UUID, because `POST /datasets/{uuid}/fhir/push` re-pushes a workflow with its tools, so they are kept.
  - `ToolsOverallView.vue:55`: change `:tool="approvalTool"` to `:item="approvalTool"`.
  - `WorkflowCard.vue`:
    - the portal branch of `menuItems` uses `workflow.value.workflowType ? () => emit('approve-platform', workflow.value) : onSubmit` for "Submit to approval";
    - add the ToolCard-style handoff poll: a `handoffActive` computed over `workflow.value.handoffStatus`, then a `setInterval` that calls `useWorkflowApprovalStatus(workflow.value.id)` every 3 s and emits `approval-done` once the handoff leaves `uploading`, `awaiting_reauth` and `committing`, with the timer cleared `onBeforeUnmount`;
    - add an "approval failed" chip when `handoffStatus === 'failed'`, as in `ToolCard.vue:23`;
    - extend `defineEmits` with `"approve-platform"` and `"approval-done"`.
  - `WorkflowsOverallView.vue`:
    - wire `@approve-platform="openApproval"` and `@approval-done="onApprovalDone"` on `WorkflowCard`;
    - add `<ToolApprovalDialog v-model="approvalOpen" kind="workflow" :item="approvalWorkflow" @done="onApprovalDone" />`;
    - `onApprovalDone` shows a toast for success or for failure (`status.handoffError`) and refreshes the list, mirroring `ToolsOverallView.vue:303-322`.
- [ ] **Step 4: Run the specs and check that they pass.** Then run `vue-tsc --noEmit`; expect no new errors.
- [ ] **Step 5: Commit:** `feat(portal): approve SDS workflows from the Workflow Hub`.

---

### Task 9: Verification, docs and artifacts

- [ ] **Step 1: Full backend suite**, using the isolated `docker run --network none` command from Global constraints. Expected: everything that passed before still passes, plus the new modules.
- [ ] **Step 2: Frontend.** Run `yarn test`, `yarn build` and `vue-tsc --noEmit` (no new errors), using the `node:20-alpine` command. Also do a clean `--frozen-lockfile` install. No new dependencies are expected.
- [ ] **Step 3: Live end-to-end check.** The user rebuilds `portal-backend` and `portal-frontend`. Then:
  1. In the Workflow Hub, choose New Workflow, switch to local, and select the folder `tests/data/workflow_image_conversion`. Expected: "Detected an SDS workflow package…", plus the workflow type radio. Choose Script and submit.
  2. In Annotation, steps `dicom_to_nifti` and `dicom_to_nrrd` show their tools' ports. Set `dicom_input` to ImagingStudy and each output to ImagingStudy, then submit.
  3. Build. The log shows the SDS package copy, and the build completes.
  4. On the card, choose Submit to approval, choose the SEEK project, keep FHIR on, and approve. Expected: "Approved" with a dataset UUID and a SEEK id. Then check:
     - the Workflow Hub shows the workflow once, not also as a "platform upload" row;
     - SEEK shows 1 workflow tagged `workflow` + `script` and 2 tools;
     - `GET /digitaltwins-api/datasets/<uuid>/workflow-tools` lists both tools;
     - HAPI has a PlanDefinition whose two actions point to ActivityDefinitions.
  5. Rebuild and approve again. Expected: a new UUID; the old workflow and its 2 tools are gone from the API.
  6. Delete the workflow. Expected: the dataset and its tools are gone from SEEK, MinIO, Postgres and HAPI.
  7. Regression: a root-`.cwl` workflow is still accepted, annotated with portal tools, and approved through the legacy path.
  8. Authentication:
     - `curl -s -o /dev/null -w '%{http_code}' http://localhost/api/workflow/` with no token returns `401`;
     - a viewer-only user sees the Workflow Hub but gets 403 on New Workflow submit and on Delete;
     - the Workflow Hub still loads for a researcher.
- [ ] **Step 4: Docs.**
  - Write `walkthrough.md` in this folder: what changed, the deviations, and the test counts.
  - Set the ADR's status to Accepted, or update it if the outcome diverged.
  - Mention in the walkthrough that `ToolApprovalDialog` now serves both kinds and kept its name.
- [ ] **Step 5: Sync and scan.** Re-sync the artifacts, then run `gitleaks detect --source docs/artifacts/2026-10-02-122144-portal-sds-workflow-approval --no-git` and `gitleaks detect --source docs/decisions --no-git`.
- [ ] **Step 6: Commit** (only when asked). Commit the artifacts and the ADR in the same branch as the code.

## Out of scope

- Root-`.cwl` workflow approval through the API, and retiring the `sparc-workflow-` stub.
- npm-building the GUI tool of a `gui` workflow. Its code is stored as source, as for API and CLI uploads.
- A delete confirmation in the portal for portal workflows; the existing delete has none.
- Any digitaltwins-api change.
