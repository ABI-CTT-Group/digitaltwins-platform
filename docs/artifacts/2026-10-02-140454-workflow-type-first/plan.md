# Workflow Type First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The portal Workflow wizard asks for the workflow type first, as the Tool wizard does. `workflows.is_sds` is decided by the build, so `workflow_type` is only the type.

**Architecture:**
- A nullable `workflows.is_sds` column is added once and backfilled from `workflow_type`.
- A successful workflow build writes it from `detect_workflow_layout`.
- Approval reads `is_sds`.
- The Annotation step works out SDS itself from the CWL source it already reads, using a new loader module.
- Both registration forms default to Script and list Script, Notebook, Web GUI.

**Tech Stack:**
- Portal backend: FastAPI, SQLAlchemy and pydantic; tests use `unittest`.
- Portal frontend: Vue 3, Vuetify and vitest, with `@vue/test-utils`.

**Spec:** [spec.md](spec.md) (approved 2026-10-02). **ADR (Proposed):** [2026-10-02-workflow-type-independent-of-sds](../../decisions/2026-10-02-workflow-type-independent-of-sds.md).

## Global Constraints

- Workflow types are `script`, `notebook` and `gui`; tool labels are `Script`, `Notebook` and `GUI`. Both forms list them in the order **Script, Notebook, Web GUI** and default to Script.
- The tool form's `hasBackend` defaults to `false`. Its radio shows only when Web GUI is selected.
- `is_sds` is never accepted from the client. Only a successful workflow build writes it. `NULL` means not built, and is treated as `false`.
- The backfill `is_sds = (workflow_type IS NOT NULL)` runs **only** when the column is created.
- digitaltwins-api is not changed. The handoff still sends `workflow_type`.
- **Backend tests** must never run in the live portal container, which would `drop_all()` the live Postgres. Run them in a throwaway container with no network, from `services/portal/backend`:
  ```bash
  docker run --rm --network none -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-portal-backend -c '/app/.venv/bin/python -m unittest tests.<module> -v'
  ```
  For the full suite, use `-c '/app/.venv/bin/python -m unittest discover -s tests -t .'`. Baseline: 141 tests, OK (9 skipped).
- **Frontend tests** run locally from `services/portal/frontend` with `npx vitest run [file]`. Baseline: 36 tests passing.
- **Frontend build** runs under Node 20, with `node_modules` and the output kept inside the container. From `services/portal/frontend`:
  ```bash
  docker run --rm -v $PWD:/app -v /app/node_modules -w /app node:20-alpine sh -c "corepack enable && corepack prepare yarn@1.22.22 --activate && yarn install --frozen-lockfile --silent && npx vite build --outDir /tmp/out --emptyOutDir"
  ```
  Baseline: it builds.
- `vue-tsc --noEmit` already crashes before reporting anything: `Search string not found: "/supportedTSExtensions = .*(?=;)/"`, from `vue-tsc ^1.2` with the resolved TypeScript, on Node 18 and Node 20. It is **not** a gate for this work. It is reported to the user separately.
- **Commits:** only when the user asks for them. Use Conventional Commits, one commit per task, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Before staging, run `gitleaks detect --source <changed paths> --no-git`.

## Review Focus

1. **Existing Postgres deployment upgrade.** On the first startup after deploy, `is_sds` is added to the portal schema. Approved SDS workflows then show `is_sds = true`, so delete still removes them from the platform. Root-`.cwl` rows show `false`. Unit tests cover only SQLite. Task 7, Step 4 is a manual check against the dev stack.
2. **A public GitHub repository with both `dataset_description.xlsx` and a root `.cwl`.** It is treated as SDS, matching the backend rule (`detect_workflow_layout`). Pinned in Task 5's loader test.
3. **A private GitHub repository, which has a token.** The loader goes through `/probe-source` with the token and takes `isSds` from the probe; it never calls the anonymous GitHub API. Pinned in Task 5.
4. **GUI → Yes → Script, then submit.** The tool is saved with `hasBackend: false`, because several readers ignore the label. Pinned in Task 6.
5. **Approving a workflow that hasn't been built yet, or whose last build failed.** `is_sds` stays `NULL` or its previous value. The SDS approval returns 409 when it is `NULL`. Pinned in Task 2 (a failed build leaves it alone) and Task 3 (a `NULL` value is not approved).

---

### Task 1: The `workflows.is_sds` column and its one-time backfill

**Files:**
- Modify: `services/portal/backend/app/models/db_model.py:170-171` (the `Workflow` columns)
- Modify: `services/portal/backend/app/database/database.py` (a new function, called from `init_db`)
- Create: `services/portal/backend/tests/test_workflow_is_sds_migration.py`

**Interfaces:**
- Produces: `Workflow.is_sds` (a `Boolean`, nullable), and `migrate_workflow_is_sds(bind) -> None` in `app.database.database`.

- [ ] **Step 1: Write the failing test** `tests/test_workflow_is_sds_migration.py`

```python
"""workflows.is_sds is added once and backfilled from workflow_type (until 2026-10-02 a set type meant SDS).

Run from `backend/`:
    python -m unittest tests.test_workflow_is_sds_migration
"""
import tempfile
import unittest
from pathlib import Path

import tests.tool_app  # noqa: F401,I001  (sets DATABASE_PATH first)
from sqlalchemy import create_engine, text

from app.database.database import migrate_workflow_is_sds
from app.models.db_model import Base


def _engine():
    return create_engine(f"sqlite:///{Path(tempfile.mkdtemp()) / 'portal.db'}")


def _is_sds(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, is_sds FROM workflows ORDER BY id")).all())


class WorkflowIsSdsMigrationTest(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        with self.engine.begin() as conn:  # the workflows table as it was before is_sds
            conn.execute(text("CREATE TABLE workflows (id VARCHAR PRIMARY KEY, workflow_type VARCHAR)"))
            conn.execute(text("INSERT INTO workflows VALUES ('sds', 'script'), ('root', NULL)"))

    def test_the_first_run_marks_typed_workflows_as_sds(self):
        migrate_workflow_is_sds(self.engine)
        self.assertEqual(_is_sds(self.engine), {"root": False, "sds": True})

    def test_a_later_run_leaves_rows_alone(self):
        migrate_workflow_is_sds(self.engine)
        with self.engine.begin() as conn:  # a root-.cwl workflow registered after the change has a type
            conn.execute(text("UPDATE workflows SET workflow_type = 'gui' WHERE id = 'root'"))
        migrate_workflow_is_sds(self.engine)
        self.assertEqual(_is_sds(self.engine), {"root": False, "sds": True})

    def test_a_fresh_database_already_has_the_column(self):
        engine = _engine()
        Base.metadata.create_all(engine)
        migrate_workflow_is_sds(engine)  # nothing to do
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT COUNT(is_sds) FROM workflows")).scalar(), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and check that it fails.** Use the backend test command with `tests.test_workflow_is_sds_migration`. Expected: `ImportError: cannot import name 'migrate_workflow_is_sds'`.

- [ ] **Step 3: Add the column.** In `app/models/db_model.py`, replace the two lines

```python
    # Set (script|notebook|gui) for an SDS workflow package, which approval hands to digitaltwins-api.
    workflow_type = Column(String, nullable=True)
```

with

```python
    workflow_type = Column(String, nullable=True)  # script|notebook|gui; NULL on rows registered before 2026-10-02
    # Set by a successful build from the source layout (app/builder/workflow_layout.py); NULL until built.
    # An SDS package is approved through digitaltwins-api (see docs/decisions/2026-10-02-workflow-type-independent-of-sds.md).
    is_sds = Column(Boolean, nullable=True)
```

- [ ] **Step 4: Add the migration.** In `app/database/database.py`, add this after `migrate_add_missing_columns`:

```python
def migrate_workflow_is_sds(bind=engine):
    """Add workflows.is_sds, backfilled from workflow_type, only when the column is created.

    Until 2026-10-02 a set workflow_type marked an SDS package. Since then every
    workflow has a type, so running the backfill again would mark root-.cwl workflows as SDS.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if not inspector.has_table("workflows"):
        return
    if "is_sds" in {col["name"] for col in inspector.get_columns("workflows")}:
        return
    logger.info("Migrating: ALTER TABLE workflows ADD COLUMN is_sds BOOLEAN, backfilled from workflow_type")
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE workflows ADD COLUMN is_sds BOOLEAN"))
        conn.execute(text("UPDATE workflows SET is_sds = (workflow_type IS NOT NULL)"))
```

In `init_db`, call it before the generic column migration:

```python
    create_tables(bind)
    migrate_workflow_is_sds(bind)
    migrate_add_missing_columns(bind)
    migrate_enum_values(bind)
```

- [ ] **Step 5: Run it and check that it passes.** Use the same command. Expected: 3 tests OK.

- [ ] **Step 6: Commit** (only if the user has asked for commits)

```bash
git add services/portal/backend/app/models/db_model.py services/portal/backend/app/database/database.py services/portal/backend/tests/test_workflow_is_sds_migration.py
git commit -m "feat(portal): add workflows.is_sds with a one-time backfill from workflow_type"
```

---

### Task 2: A successful workflow build writes `is_sds`

**Files:**
- Modify: `services/portal/backend/app/builder/build_workflow.py:145-151` (validation), and the success `return` at about line 190
- Modify: `services/portal/backend/app/utils/builder_utils.py:316-320` (the executor's success branch)
- Modify: `services/portal/backend/tests/test_workflow_build_dataset.py`
- Create: `services/portal/backend/tests/test_workflow_build_executor.py`

**Interfaces:**
- Consumes: `Workflow.is_sds` (Task 1).
- Produces: a successful `WorkflowBuilder.build()` result has `"is_sds": bool`. `execute_build_in_background` copies it to `build_record.workflow.is_sds`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_workflow_build_dataset.py`, add `self.assertTrue(result["is_sds"])` as the last line of `test_an_sds_build_succeeds_with_a_workflow_type`. Then replace the whole of `test_a_workflow_type_needs_an_sds_package` with:

```python
    def test_a_root_cwl_workflow_with_a_type_builds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        result = self._build(src, "script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertFalse(result["is_sds"])
```

Create `tests/test_workflow_build_executor.py`:

```python
"""A successful workflow build records whether the source is an SDS package; a failed one leaves it alone.

Run from `backend/`:
    python -m unittest tests.test_workflow_build_executor
"""
import unittest
import uuid

from fastapi import BackgroundTasks

from tests.tool_app import make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, SessionLocal, Workflow, WorkflowBuild
from app.utils.builder_utils import execute_build_in_background


class FakeBuilder:
    def __init__(self, result):
        self.result = result

    def build(self, data):
        return self.result


class WorkflowBuildExecutorTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        self.build_id = str(uuid.uuid4())
        with SessionLocal() as db:
            wf = Workflow(name="convert", version="1.0.0", repository_url="local://x", source_type="local",
                          workflow_type="script")
            db.add(wf)
            db.commit()
            self.wf_id = wf.id
            db.add(WorkflowBuild(workflow_id=wf.id, build_id=self.build_id, status=BuildStatus.PENDING.value))
            db.commit()

    def _run(self, result):
        tasks = BackgroundTasks()
        execute_build_in_background(self.build_id, {}, FakeBuilder(result), WorkflowBuild, tasks)
        for task in tasks.tasks:
            task.func(*task.args, **task.kwargs)
        with SessionLocal() as db:
            return db.get(Workflow, self.wf_id).is_sds

    def test_a_successful_build_records_the_layout(self):
        ok = {"success": True, "s3_path": None, "dataset_path": "/d", "expose_name": "convert_ab12", "is_sds": True}
        self.assertTrue(self._run(ok))

    def test_a_failed_build_leaves_it_alone(self):
        self.assertIsNone(self._run({"success": False, "error_message": "boom"}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and check that they fail.** Run with `tests.test_workflow_build_dataset tests.test_workflow_build_executor`. Expected:
  - `KeyError: 'is_sds'` in the two build tests;
  - the root-`.cwl` test fails with "not an SDS workflow package";
  - `test_a_successful_build_records_the_layout` fails with `None is not true`.

- [ ] **Step 3: Implement it in the builder.** In `app/builder/build_workflow.py`, delete these three lines:

```python
            if workflow_type and not layout.is_sds:
                raise RuntimeError("A workflow type is set, but the source is not an SDS workflow package "
                                   "(dataset_description.xlsx and one primary/workflow_*.cwl)")
```

In the success `return {...}` of `build()`, add `"is_sds": layout.is_sds,` after `"dataset_path": str(dataset_dir),`.

- [ ] **Step 4: Implement it in the executor.** In `app/utils/builder_utils.py`, add these lines in the `if result["success"]:` branch, after `build_record.expose_name = result["expose_name"]`:

```python
                        if "is_sds" in result:  # workflow builds: the source layout decides (workflow_layout.py)
                            build_record.workflow.is_sds = result["is_sds"]
```

- [ ] **Step 5: Run them and check that they pass.** Use the same command. Expected: OK.

- [ ] **Step 6: Commit** (only if asked): `feat(portal): record whether a workflow is an SDS package when it builds`

---

### Task 3: The API contract and approval gating

**Files:**
- Modify: `services/portal/backend/app/models/db_model.py` (`WorkflowCreate`, `WorkflowResponse`)
- Modify: `services/portal/backend/app/router/workflow_router.py`: line 33 (import), the `/cwl` return at about line 146, and lines 478, 519 and 599
- Create: `services/portal/backend/tests/test_workflow_create.py`
- Modify: `services/portal/backend/tests/test_workflow_sds_source.py`
- Modify: `services/portal/backend/tests/test_workflow_handoff.py`

**Interfaces:**
- Consumes: `Workflow.is_sds` (Task 1).
- Produces:
  - `POST /api/workflow/create` requires `workflow_type` and ignores `is_sds`;
  - `WorkflowResponse.is_sds: Optional[bool]`, which the frontend sees as `isSds`;
  - `GET /api/workflow/{id}/cwl` returns `is_sds: bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workflow_create.py`:

```python
"""Every new workflow names its type; whether it is an SDS package is left to the build.

Run from `backend/`:
    python -m unittest tests.test_workflow_create
"""
import unittest

from tests.tool_app import bearer, make_workflow_client

BODY = {"name": "convert", "version": "1.0.0", "repository_url": "https://github.com/acme/convert",
        "source_type": "github"}


class WorkflowCreateTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()

    def _create(self, body):
        return self.client.post("/api/workflow/create", json=body, headers=bearer("researcher"))

    def test_a_workflow_needs_a_type(self):
        self.assertEqual(self._create(BODY).status_code, 422)

    def test_a_new_workflow_is_not_known_to_be_sds_until_built(self):
        r = self._create({**BODY, "workflow_type": "gui"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["workflow_type"], r.json()["is_sds"]), ("gui", None))

    def test_the_client_cannot_set_is_sds(self):
        r = self._create({**BODY, "workflow_type": "gui", "is_sds": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["is_sds"])


if __name__ == "__main__":
    unittest.main()
```

In `tests/test_workflow_sds_source.py`, add `self.assertTrue(r.json()["is_sds"])` as the last line of `test_cwl_returns_the_workflow_and_its_tool_cwls`, and add this test after it:

```python
    def test_cwl_reports_a_root_cwl_source_as_not_sds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        with SessionLocal() as db:
            wf = Workflow(name="flow", version="1.0.0", repository_url="local://y", source_type="local",
                          local_archive_path=str(src), workflow_type="script")
            db.add(wf)
            db.commit()
            wf_id = wf.id
        r = self.client.get(f"/api/workflow/{wf_id}/cwl", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["is_sds"])
```

In `tests/test_workflow_handoff.py`:
- In `setUp`, change `workflow_type="script")` to `workflow_type="script", is_sds=True)`.
- In `test_a_root_cwl_workflow_is_not_approved_to_the_platform`, change `db.get(Workflow, self.wf_id).workflow_type = None` to `db.get(Workflow, self.wf_id).is_sds = False`. A root-`.cwl` workflow now has a type, and only `is_sds` keeps it out of the SDS approval.
- Add this test after it:

```python
    def test_a_workflow_not_built_yet_is_not_approved_to_the_platform(self):
        with SessionLocal() as db:
            db.get(Workflow, self.wf_id).is_sds = None
            db.commit()
        self.assertEqual(self._approve().status_code, 409)
```

- [ ] **Step 2: Run them and check that they fail.** Run with `tests.test_workflow_create tests.test_workflow_sds_source tests.test_workflow_handoff`. Expected:
  - `test_a_workflow_needs_a_type`: 200 is not 422;
  - the two `is_sds` response tests: `KeyError: 'is_sds'`;
  - the two `/cwl` tests: `KeyError`;
  - `test_a_root_cwl_workflow_is_not_approved…` and `test_a_workflow_not_built_yet…`: 202 is not 409.

- [ ] **Step 3: Update the models.** In `app/models/db_model.py`, replace `WorkflowCreate` and add `is_sds` to `WorkflowResponse`:

```python
class WorkflowCreate(WorkflowBase):
    workflow_type: Literal["script", "notebook", "gui"]  # required for new workflows; optional on WorkflowBase for older rows
    upload_id: Optional[str] = None  # client-supplied at create-time only; resolved to local_archive_path server-side


class WorkflowResponse(WorkflowBase):
    id: str
    uuid: Optional[str] = None
    local_archive_path: Optional[str] = None
    seek_project_id: Optional[int] = None
    is_sds: Optional[bool] = None  # set by the build; never accepted from the client
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Update the router.** In `app/router/workflow_router.py`:
  - **line 33:** `from app.builder.workflow_layout import detect_workflow_layout, inspect_workflow_source, read_workflow_cwl`
  - **`get_workflow_cwl`:** replace the final `return result` with `return {**result, "is_sds": detect_workflow_layout(staging).is_sds}`. `result` isn't `None` here, so an SDS package has its one workflow CWL and `detect_workflow_layout` doesn't raise.
  - **`approve_workflow`** (line 478): change `if not workflow.workflow_type:` to `if not workflow.is_sds:`.
  - **`get_workflow_approval`** (line 519): change `if workflow.workflow_type:` to `if workflow.is_sds:`.
  - **`delete_plugin`** (line 599): change `if workflow_handoff.in_platform(workflow) and workflow.workflow_type:` to `if workflow_handoff.in_platform(workflow):`. Only the SDS handoff gives a workflow a real (non-placeholder) dataset UUID. The existing delete tests in `test_workflow_handoff.py` cover this path.

- [ ] **Step 5: Run them and check that they pass.** Use the same command, then also run `tests.test_workflow_auth` to check that `/create` with a researcher token still isn't 401 or 403. Expected: OK.

- [ ] **Step 6: Commit** (only if asked): `feat(portal): require a workflow type and approve SDS workflows by is_sds`

---

### Task 4: WorkflowCard routes approval by `isSds`

**Files:**
- Modify: `services/portal/frontend/src/models/types.ts` (`WorkflowResponse`)
- Modify: `services/portal/frontend/src/views/upload-dataset/components/WorkflowCard.vue:62`
- Modify: `services/portal/frontend/src/views/upload-dataset/components/__tests__/cards.spec.ts`

**Interfaces:**
- Consumes: `isSds` on `WorkflowResponse` (Task 3).
- Produces: `WorkflowResponse.isSds?: boolean | null`.

- [ ] **Step 1: Write the failing test.** In `cards.spec.ts`, inside `it("routes a portal SDS workflow to the platform approval", ...)`, change `const sds = { ...WORKFLOW, workflowType: "script" };` to `const sds = { ...WORKFLOW, workflowType: "script", isSds: true };`. Then add this test after `it("keeps the legacy approval for a portal workflow without a type", ...)`:

```ts
  it("keeps the legacy approval for a typed workflow that is not an SDS package", () => {
    const rootCwl = { ...WORKFLOW, workflowType: "gui", isSds: false };
    const w = mount(WorkflowCard, { props: { workflow: rootCwl as any }, global: { plugins } });

    menu(w)[0].onClick();
    expect(w.emitted("submit-approve")?.[0]).toEqual(["p1"]);
    expect(w.emitted("approve-platform")).toBeUndefined();
  });
```

- [ ] **Step 2: Run it and check that it fails.** Run `npx vitest run src/views/upload-dataset/components/__tests__/cards.spec.ts`. Expected: the new test fails, because `submit-approve` is undefined.

- [ ] **Step 3: Implement it.** In `types.ts`, in `interface WorkflowResponse`, add this line after `workflowType?: string;`:

```ts
    // An SDS package, as the latest successful build found it (null until built); approval goes to the platform.
    isSds?: boolean | null;
```

In `WorkflowCard.vue`, line 62, change `onClick: workflow.value.workflowType ? () => emit("approve-platform", workflow.value) : onSubmit` to `onClick: workflow.value.isSds ? () => emit("approve-platform", workflow.value) : onSubmit`.

- [ ] **Step 4: Run it and check that it passes.** Use the same command. Expected: 8 tests pass.

- [ ] **Step 5: Commit** (only if asked): `feat(portal): route workflow approval by isSds in the Workflow Hub`

---

### Task 5: The Annotation step works out SDS from the source

**Files:**
- Create: `services/portal/frontend/src/views/upload-dataset/components/workflow_cwls.ts`
- Create: `services/portal/frontend/src/views/upload-dataset/components/__tests__/workflow_cwls.spec.ts`
- Modify: `services/portal/frontend/src/bootstrap/workflow_api.ts:95-97` (the `/cwl` response type)
- Modify: `services/portal/frontend/src/views/upload-dataset/components/BaseAnnotateStep.vue`

**Interfaces:**
- Consumes: `is_sds` from `GET /api/workflow/{id}/cwl` (Task 3), and `isSds` from `/probe-source`, which already exists.
- Produces:
  - `loadWorkflowCwls(workflow: WorkflowResponse, auth?: TransientAuth | null): Promise<WorkflowCwls>`, where `WorkflowCwls = { isSds: boolean; content: any; tools: ParsedCwl[] }`;
  - `parseCwlText(raw: string): any`;
  - `canUsePublicGithubPath(sourceType: SourceType | undefined, auth?: TransientAuth | null): boolean`.

- [ ] **Step 1: Write the failing test** `__tests__/workflow_cwls.spec.ts`

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
const { getRepoContents, localCwl, probe } = vi.hoisted(() => ({ getRepoContents: vi.fn(), localCwl: vi.fn(), probe: vi.fn() }));
vi.mock("@/views/upload-dataset/components/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/views/upload-dataset/components/utils")>()), getRepoContents,
}));
vi.mock("@/bootstrap/workflow_api", () => ({ useGetWorkflowLocalCwl: localCwl, useProbeWorkflowSource: probe }));

import { loadWorkflowCwls } from "../workflow_cwls";

const WF = "class: Workflow\nsteps:\n  convert:\n    run: tool_convert.cwl\n";
const TOOL = "class: CommandLineTool\ninputs:\n  src: File\n";
const workflow = (sourceType: string) => ({ id: "w1", sourceType, repositoryUrl: "https://github.com/acme/convert" }) as any;
const file = (name: string) => ({ type: "file", name });
const encoded = (text: string) => ({ data: { content: btoa(text) } });

describe("loadWorkflowCwls", () => {
  beforeEach(() => vi.resetAllMocks());

  it("takes isSds from /cwl for a local source", async () => {
    localCwl.mockResolvedValue({ cwlFile: "workflow_convert.cwl", content: WF, isSds: true,
      toolCwls: [{ cwlFile: "tool_convert.cwl", content: TOOL }] });
    const res = await loadWorkflowCwls(workflow("local"));
    expect(res.isSds).toBe(true);
    expect(res.tools.map((t) => t.cwlFile)).toEqual(["tool_convert.cwl"]);
  });

  it("finds an SDS package on public GitHub by its dataset_description.xlsx, even with a root .cwl", async () => {
    getRepoContents.mockImplementation(async (_url: string, path = "") => {
      if (path === "") return { data: [file("dataset_description.xlsx"), file("legacy.cwl")] };
      if (path === "primary") return { data: [file("workflow_convert.cwl"), file("tool_convert.cwl")] };
      return encoded(path.endsWith("workflow_convert.cwl") ? WF : TOOL);
    });
    const res = await loadWorkflowCwls(workflow("github"));
    expect(res.isSds).toBe(true);
    expect(res.content.class).toBe("Workflow");
    expect(res.tools.map((t) => t.cwlFile)).toEqual(["tool_convert.cwl"]);
  });

  it("reads a root .cwl on public GitHub as not SDS", async () => {
    getRepoContents.mockImplementation(async (_url: string, path = "") =>
      path === "" ? { data: [file("flow.cwl"), file("README.md")] } : encoded(WF));
    const res = await loadWorkflowCwls(workflow("github"));
    expect(res).toMatchObject({ isSds: false, tools: [] });
    expect(getRepoContents).toHaveBeenCalledWith("https://github.com/acme/convert", "flow.cwl");
  });

  it("takes isSds from /probe-source for private GitHub and other hosts", async () => {
    probe.mockResolvedValue({ ok: true, data: { isSds: true, cwlContent: WF,
      toolCwls: [{ cwlFile: "tool_convert.cwl", content: TOOL }] } });
    const res = await loadWorkflowCwls(workflow("github"), { token: "<REDACTED>" });
    expect(res.isSds).toBe(true);
    expect(probe).toHaveBeenCalledWith(expect.objectContaining({ sourceType: "github", token: "<REDACTED>" }));
    expect(getRepoContents).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run it and check that it fails.** Run `npx vitest run src/views/upload-dataset/components/__tests__/workflow_cwls.spec.ts`. Expected: it fails to resolve `../workflow_cwls`.

- [ ] **Step 3: Write the loader** `components/workflow_cwls.ts`

```ts
import yaml from 'js-yaml';
import type { GitContent, SourceType, TransientAuth, WorkflowResponse } from '@/models/types';
import { useGetWorkflowLocalCwl, useProbeWorkflowSource } from '@/bootstrap/workflow_api';
import { SDS_MARKER, getRepoContents, sdsWorkflowCwls } from '@/views/upload-dataset/components/utils';

export interface ParsedCwl { cwlFile: string; content: any }

/** A workflow's CWL for the Annotation step. `isSds` comes from the source itself; the build records the same. */
export interface WorkflowCwls { isSds: boolean; content: any; tools: ParsedCwl[] }

export function parseCwlText(raw: string): any {
  try { return yaml.load(raw); }
  catch { return JSON.parse(raw); }
}

/** Public GitHub without a token is read from the browser; private GitHub and other hosts go through /probe-source. */
export function canUsePublicGithubPath(sourceType: SourceType | undefined, auth?: TransientAuth | null): boolean {
  return sourceType === 'github' && !auth?.token;
}

const parseAll = (tools: { cwlFile: string; content: string }[] = []): ParsedCwl[] =>
  tools.map((t) => ({ cwlFile: t.cwlFile, content: parseCwlText(t.content) }));

async function readGithubFile(repositoryUrl: string, path: string): Promise<string> {
  const res = await getRepoContents(repositoryUrl, path);
  return atob((res.data.content as string).replace(/\n/g, ''));
}

/** SDS when the root has dataset_description.xlsx, as the backend's detect_workflow_layout decides. */
async function loadPublicGithub(repositoryUrl: string): Promise<WorkflowCwls> {
  const files = ((await getRepoContents(repositoryUrl)).data as GitContent[]).filter((item) => item.type === 'file');
  if (!files.some((item) => item.name === SDS_MARKER)) {
    const cwlFile = files.filter((item) => item.name.endsWith('.cwl')).pop()?.name;
    if (!cwlFile) throw new Error('No CWL file found at repo root.');
    return { isSds: false, content: parseCwlText(await readGithubFile(repositoryUrl, cwlFile)), tools: [] };
  }
  const primary = ((await getRepoContents(repositoryUrl, 'primary')).data as GitContent[])
    .filter((item) => item.type === 'file' && item.name.endsWith('.cwl'));
  const [wfName] = sdsWorkflowCwls(primary.map((item) => item.name));
  if (!wfName) throw new Error('No primary/workflow_*.cwl in the repository.');
  const tools = await Promise.all(primary.filter((item) => item.name.startsWith('tool_'))
    .map(async (item) => ({ cwlFile: item.name, content: parseCwlText(await readGithubFile(repositoryUrl, `primary/${item.name}`)) })));
  return { isSds: true, content: parseCwlText(await readGithubFile(repositoryUrl, `primary/${wfName}`)), tools };
}

export async function loadWorkflowCwls(workflow: WorkflowResponse, auth?: TransientAuth | null): Promise<WorkflowCwls> {
  if (workflow.sourceType === 'local') {
    const res = await useGetWorkflowLocalCwl(workflow.id);
    return { isSds: res.isSds, content: parseCwlText(res.content), tools: parseAll(res.toolCwls) };
  }
  if (canUsePublicGithubPath(workflow.sourceType, auth)) return loadPublicGithub(workflow.repositoryUrl);
  const res = await useProbeWorkflowSource({
    sourceType: workflow.sourceType as Exclude<SourceType, 'local'>, url: workflow.repositoryUrl,
    token: auth?.token, authUsername: auth?.authUsername, verifySsl: auth?.verifySsl ?? true,
  });
  if (!res.ok) throw new Error(`Failed to fetch CWL: ${res.message}`);
  if (!res.data.cwlContent) throw new Error('No CWL file found at the root of the repository.');
  return { isSds: !!res.data.isSds, content: parseCwlText(res.data.cwlContent), tools: parseAll(res.data.toolCwls) };
}
```

In `bootstrap/workflow_api.ts`, lines 95-96: in both places, change the response type `{ cwlFile: string; content: string; toolCwls?: { cwlFile: string; content: string }[] }` to `{ cwlFile: string; content: string; isSds: boolean; toolCwls?: { cwlFile: string; content: string }[] }`.

- [ ] **Step 4: Run it and check that it passes.** Use the same command. Expected: 4 tests pass.

- [ ] **Step 5: Wire the loader into `BaseAnnotateStep.vue`**
  - **Imports:**
    - Replace `import { getRepoContents, getRepoRootCWLContent, sdsWorkflowCwls } from '@/views/upload-dataset/components/utils';` with `import { getRepoRootCWLContent } from '@/views/upload-dataset/components/utils';`.
    - Delete `import type { GitContent } from '@/models/types';`, `import yaml from 'js-yaml';` and `import { useGetWorkflowLocalCwl, useProbeWorkflowSource } from '@/bootstrap/workflow_api';`.
    - Add `import { canUsePublicGithubPath, loadWorkflowCwls, parseCwlText } from '@/views/upload-dataset/components/workflow_cwls';`.
  - **State:** replace line 214, `const isSdsWorkflow = computed(...)`, with:
    ```ts
    // From the source, by loadWorkflowCwls (the build records the same as workflows.is_sds).
    const isSdsWorkflow = ref(false);
    const loadingCwl = ref(props.type === 'workflow');
    ```
  - **Delete** the local `parseCwlText` and `_canUsePublicGithubPath`, plus their doc comments. Also delete `loadWorkflowCwl` and `loadSdsWorkflowCwls`.
  - **`_loadCwlViaBackendProbe` is now used only for tools.** Remove its `kind` parameter and call `useProbeToolSource` directly:
    ```ts
    async function _loadCwlViaBackendProbe(
      sourceType: Exclude<SourceType, 'local'>,
      repositoryUrl: string,
    ): Promise<{ cwlFile: string; content: any }> {
      const res = await useProbeToolSource({
    ```
    The rest of its body is unchanged.
  - **`loadToolCwl`:**
    - `if (_canUsePublicGithubPath(tool.sourceType)) {` becomes `if (canUsePublicGithubPath(tool.sourceType, props.pendingAuth)) {`;
    - its fallback call becomes `_loadCwlViaBackendProbe(tool.sourceType as Exclude<SourceType, 'local'>, tool.repositoryUrl)`.
  - **`onMounted`:** replace the body of `if (props.type === 'workflow') { ... }` with:
    ```ts
        try {
          const workflow = props.data as WorkflowResponse | undefined;
          if (!workflow) { console.warn('No workflow info in annotation stepper.'); return; }
          const { isSds, content, tools } = await loadWorkflowCwls(workflow, props.pendingAuth);
          isSdsWorkflow.value = isSds;
          if (isSds) sdsSteps.value = sdsWorkflowSteps(content, tools);
          else workflowTools.value = await useWorkflowTools();
          cwlObj.value = content;
        } catch (err: any) {
          loadError.value = err?.message ?? String(err);
        } finally {
          loadingCwl.value = false;
        }
    ```
  - **Template:** directly before `<template v-if="isSdsWorkflow">` (line 13), add
    ```vue
      <!-- Whether a workflow is an SDS package is read from its source first -->
      <v-progress-linear v-if="type === 'workflow' && loadingCwl" indeterminate color="#5fd6e8" />
    ```
    Then change `<template v-if="isSdsWorkflow">` to `<template v-else-if="isSdsWorkflow">`.

- [ ] **Step 6: Run the frontend suite.** Run `npx vitest run`. Expected: all pass (36 baseline, +1 from Task 4, +4 here). Then run the frontend build command. Expected: it builds.

- [ ] **Step 7: Commit** (only if asked): `feat(portal): detect SDS workflow packages from the source in the Annotation step`

---

### Task 6: Registration forms ask for the type first, defaulting to Script

**Files:**
- Modify: `services/portal/frontend/src/views/upload-dataset/components/BaseInformationStep.vue`
- Modify: `services/portal/frontend/src/models/types.ts` (`WorkflowInformationStep`)
- Create: `services/portal/frontend/src/views/upload-dataset/components/__tests__/BaseInformationStep.spec.ts`

**Interfaces:**
- Produces: `WorkflowInformationStep.workflowType: WorkflowType`, now required. The workflow `submit` payload always carries `workflowType`. The tool payload's `hasBackend` is `false` unless Web GUI is selected and the user picked Yes.

- [ ] **Step 1: Write the failing test** `__tests__/BaseInformationStep.spec.ts`

```ts
import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(async () => ({ available: true, message: "" })) }));
vi.mock("@/bootstrap/upload_source", () => ({ useUploadToolSource: vi.fn(), useUploadWorkflowSource: vi.fn() }));
vi.mock("@/composables/useGithubRepoInfo", async () => {
  const { ref } = await import("vue");
  return { useGitRepoInfo: () => ({ info: ref({ foldersInRoot: [], isSds: false, cwlExists: false }), refresh: vi.fn() }) };
});
vi.mock("@/composables/useLocalFolderInfo", async () => {
  const { ref } = await import("vue");
  return { useLocalFolderInfo: () => ({ info: ref({ foldersInRoot: [], isSds: false, cwlExists: false }), refresh: vi.fn() }) };
});

import BaseInformationStep from "../BaseInformationStep.vue";

// The source fields belong to CommonInfoForm; render only its slots, so the type radios are tested on their own.
const stubs = { CommonInfoForm: { template: "<div><slot name='dropzone' /><slot /></div>" }, LocalFolderDropzone: true };
const mountStep = (type: "tool" | "workflow") =>
  mount(BaseInformationStep, { props: { type }, global: { plugins: [testVuetify()], stubs } });
type Step = ReturnType<typeof mountStep>;
const typeGroup = (w: Step) => w.findAllComponents({ name: "VRadioGroup" })[0];
const labels = (w: Step) => typeGroup(w).findAllComponents({ name: "VRadio" }).map((r) => r.props("label"));
const pick = async (w: Step, value: string) => { typeGroup(w).vm.$emit("update:modelValue", value); await flushPromises(); };

async function submit(w: Step) {
  const vm = w.vm as any;
  vm.formData.name = "convert";
  vm.cwlCheck = true;  // the source check passed
  await w.findAll("button").find((b) => b.text().startsWith("Submit"))!.trigger("click");
  await flushPromises();
  return w.emitted("submit")?.[0]?.[0] as any;
}

describe("BaseInformationStep", () => {
  it("asks a workflow for its type before any source is chosen, defaulting to Script", () => {
    const w = mountStep("workflow");
    expect(w.text()).toContain("Choose the workflow type *");
    expect(labels(w)).toEqual(["Script", "Notebook", "Web GUI"]);
    expect(typeGroup(w).props("modelValue")).toBe("script");
  });

  it("sends the workflow type for any source", async () => {
    const w = mountStep("workflow");
    await pick(w, "notebook");
    expect(await submit(w)).toMatchObject({ workflowType: "notebook" });
  });

  it("lists tool types in the same order, defaulting to Script with no backend", () => {
    const w = mountStep("tool");
    expect(labels(w)).toEqual(["Script", "Notebook", "Web GUI"]);
    expect(typeGroup(w).props("modelValue")).toBe("Script");
    expect(w.text()).not.toContain("has backend?");
    expect((w.vm as any).formData.hasBackend).toBe(false);
  });

  it("asks about a backend only for a Web GUI tool, and never sends one for a Script tool", async () => {
    const w = mountStep("tool");
    await pick(w, "GUI");
    expect(w.text()).toContain("has backend?");
    expect((w.vm as any).formData.hasBackend).toBe(false);

    (w.vm as any).formData.hasBackend = true;
    await pick(w, "Script");
    expect(await submit(w)).toMatchObject({ label: "Script", hasBackend: false });
  });
});
```

- [ ] **Step 2: Run it and check that it fails.** Run `npx vitest run src/views/upload-dataset/components/__tests__/BaseInformationStep.spec.ts`. Expected:
  - the workflow tests fail: no "Choose the workflow type *" text, because `isSds` is false;
  - the tool tests fail: labels are `["Web GUI", "Script", "Notebook"]` and the model value is `"GUI"`.

  If `w.vm.formData` or `w.vm.cwlCheck` can't be reached, stop and report it. Don't add a `defineExpose` just for tests.

- [ ] **Step 3: Change the template.** In `BaseInformationStep.vue`, replace the tool type block (lines 15-39) with:

```vue
      <!-- The type comes first, for tools and workflows alike -->
      <template v-if="type === 'tool'">
        <h4 class="my-2">Choose the tool type *</h4>
        <v-radio-group
          v-model="formData.label"
          inline
          class="w-100 d-flex justify-start"
          @update:modelValue="handleLabelChange"
        >
          <v-radio color="#5fd6e8" label="Script" value="Script" />
          <v-tooltip text="Script tools currently support Python scripts only." location="top" open-delay="200">
            <template #activator="{ props: tip }">
              <v-icon
                icon="mdi-information-outline"
                size="16"
                class="ml-n1 mr-2 text-medium-emphasis"
                style="cursor: help;"
                v-bind="tip"
              />
            </template>
          </v-tooltip>
          <v-radio color="#5fd6e8" label="Notebook" value="Notebook" class="ml-2" />
          <v-radio color="#5fd6e8" label="Web GUI" value="GUI" class="ml-2" />
        </v-radio-group>
      </template>
      <template v-else>
        <h4 class="my-2">Choose the workflow type *</h4>
        <v-radio-group v-model="formData.workflowType" inline class="w-100 d-flex justify-start">
          <v-radio color="#5fd6e8" label="Script" value="script" />
          <v-radio color="#5fd6e8" label="Notebook" value="notebook" class="ml-2" />
          <v-radio color="#5fd6e8" label="Web GUI" value="gui" class="ml-2" />
        </v-radio-group>
      </template>
```

Delete the old SDS-only workflow radio inside `<CommonInfoForm>`. That is the comment `<!-- Workflow + SDS package: the API needs its type -->` and the whole `<div v-if="type === 'workflow' && repoInfo.isSds" class="w-100">…</div>` that follows it.

- [ ] **Step 4: Change the script**
  - **`formData`:**
    - change the type to `reactive<ToolInformationStep & { source?: LocalSource; workflowType: WorkflowType }>`;
    - change the defaults `label: 'GUI'` to `label: 'Script'`, `hasBackend: true` to `hasBackend: false`, and `workflowType: undefined` to `workflowType: 'script'`.
  - **`validate()`:** for workflows, change `return valid && !!cwlCheck.value && (!repoInfo.value.isSds || !!formData.workflowType);` to `return valid && !!cwlCheck.value && !!formData.workflowType;`.
  - **Workflow alert text:** `'Some required fields are missing. Please provide your source (GitHub URL or local folder), workflow name and workflow type.'`
  - **`workflowData`:** change `workflowType: repoInfo.value.isSds ? formData.workflowType : undefined,` to `workflowType: formData.workflowType,`.
  - `handleLabelChange` is unchanged. It still sets `hasBackend = false` when the user switches away from GUI.
  - **`types.ts`:** in `WorkflowInformationStep`, change `workflowType?: WorkflowType;` to `workflowType: WorkflowType;`.

- [ ] **Step 5: Run it and check that it passes.** Run the same spec, then `npx vitest run` for the whole suite. Expected: all pass. Then run the frontend build command. Expected: it builds.

- [ ] **Step 6: Commit** (only if asked): `feat(portal): ask for the tool and workflow type first, defaulting to Script`

---

### Task 7: ADRs, walkthrough, and verifying the whole change

**Files:**
- Modify: `docs/decisions/2026-10-02-workflow-type-independent-of-sds.md` (status)
- Modify: `docs/decisions/2026-10-02-portal-sds-workflow-approval.md` (decision 2)
- Create: `docs/artifacts/2026-10-02-140454-workflow-type-first/walkthrough.md`

- [ ] **Step 1: Accept the ADR.** In `2026-10-02-workflow-type-independent-of-sds.md`, change `- **Status:** Proposed` to `- **Status:** Accepted`. If the implementation differed from the ADR, update the ADR to match.

- [ ] **Step 2: Mark the old decision as superseded.** In `2026-10-02-portal-sds-workflow-approval.md`, append this to decision 2, after "The build fails when the two don't match.":
  ` *Superseded by [2026-10-02-workflow-type-independent-of-sds](2026-10-02-workflow-type-independent-of-sds.md): every workflow has a type, and the build sets `workflows.is_sds`.*`

- [ ] **Step 3: Run the full suites.**
  - The backend suite, using the full-suite command. Expected: OK, with 141 baseline tests plus the new ones.
  - `npx vitest run`. Expected: all pass.
  - The frontend build. Expected: it builds.

  Record the counts in the walkthrough.

- [ ] **Step 4: Manual check on the dev stack** (only with the user's go-ahead: it rebuilds the running portal containers).
  1. Rebuild and restart the portal containers.
  2. Check the backend log for the line `Migrating: ALTER TABLE workflows ADD COLUMN is_sds BOOLEAN, backfilled from workflow_type`, then query `SELECT name, workflow_type, is_sds FROM portal.workflows` (`PORTAL_DB_SCHEMA = "portal"`). Typed rows should be `true` and untyped rows `false`.
  3. Open `http://localhost/upload-workflow-dataset`. The type radio shows Script, Notebook, Web GUI with Script selected, before Source.
  4. Register `tests/data/workflow_image_conversion` (local). The Annotation step shows the SDS step form, the build succeeds, and "Submit to approval" opens the platform approval dialog.
  5. Open `http://localhost/upload-tool-dataset`. It opens on Script with no backend fields. Choosing Web GUI shows "has backend?" set to No.

- [ ] **Step 5: Write `walkthrough.md`** in this folder. Cover:
  - what changed, per task;
  - the test counts and the build result;
  - the result of the manual check, or "not run", with the reason;
  - the `vue-tsc` crash, as a separate defect outside this change.

  Then sync it: it lives in `docs/artifacts/2026-10-02-140454-workflow-type-first/`. Run `gitleaks detect --source docs/artifacts/2026-10-02-140454-workflow-type-first --no-git`, and also on the two ADR files.

- [ ] **Step 6: Commit** (only if asked): `docs: record the workflow-type-first decision and walkthrough`. It includes `spec.md`, `plan.md`, `walkthrough.md` and both ADRs, in the same branch as the code.
