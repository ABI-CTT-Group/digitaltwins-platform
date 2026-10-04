# Launchable GUI Tools from gui Workflows: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to carry out this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** when a gui SDS workflow such as `workflow_volview` is built, the portal also builds its tool's frontend. The tool then appears in the Tool Hub, where it can be launched (and its backend deployed) like a standalone GUI tool: from `tool-builds` before approval, and from the platform `tools` bucket after.

**Architecture:**
- `PluginBuilder` gains one method, `build_frontend`, which holds the GUI build steps that used to be inline in `build()`. `WorkflowBuilder` calls it on a scratch copy of `code/`, writes the bundle to `primary/<tool_stem>/` and also uploads it to `tool-builds`.
- digitaltwins-api's `_assemble_tool` copies `primary/<tool_stem>/` into the tool dataset's `primary/`.
- The approval handoff records the platform tool dataset's UUID.
- New portal endpoints list gui workflows' tools for the Tool Hub, add them to `/api/tools/metadata`, and deploy their backends. Deploying reuses the tool deploy code, which moves into a shared function, and a deployment row can now point at a workflow build.
- On the frontend, the Tool Hub merges the new rows, ToolCard gets a "from workflow" variant, and the Workflow wizard shows the GUI fields for gui SDS packages.

**Tech stack:**
- Portal backend: FastAPI, SQLAlchemy, pydantic v2; tests use `unittest`.
- Portal frontend: Vue 3.5, Vuetify, vitest.
- digitaltwins-api: pytest.

**Spec:** [spec.md](spec.md) (approved 2026-10-02). ADR: [2026-10-02-build-gui-workflow-tools](../../decisions/2026-10-02-build-gui-workflow-tools.md) (Accepted).

## Changes from the spec, found while planning

Task 13 writes these back into the spec and the ADR.

1. **No `gui_frontend.py` module.** The shared build becomes the `PluginBuilder.build_frontend` method. Its helpers (`_update_vite_config`, `_create_env_file`, `frontend_install`, `frontend_build`) are `PluginBuilder` methods that existing tests use, so moving them out would add churn without benefit.
2. **gui workflows that aren't SDS packages are unchanged.** The spec said they should fail to build, but that contradicts its own acceptance criterion ("root-`.cwl` workflows behave exactly as before") and ADR 2026-10-02-workflow-type-independent-of-sds. A root-`.cwl` gui workflow runs portal tools that are built as tools already. So:
   - only gui **SDS** workflows build a frontend;
   - the wizard shows the GUI fields only when the source is an SDS package.
3. **There is no workflow update endpoint, so none is added.** An SDS gui workflow registered before this change has empty GUI fields. Its build uses the defaults: no backend, `npm run build:plugin`, frontend at the `code/` root. That's VolView's layout, so `workflow_volview` just needs a **Rebuild**, not a new registration.
4. **`workflow_builds.tool_name` marks a build that has a bundle.** `bundle_path` stays null when the upload to `tool-builds` fails. That failure doesn't fail the build, the same as a tool test build's MinIO upload.
5. **`GET /api/tools/builds/{id}/logs` also falls back to workflow builds**, so "View logs" works after the in-memory log has expired.

## Global constraints

- **Portal backend tests must never run where `PORTAL_DB_HOST` is set**, because the suite drops the live portal tables. Run them only like this, from `services/portal/backend`:
  ```bash
  docker run --rm --network none -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-portal-backend -c '/app/.venv/bin/python -m unittest discover -s tests -t .'
  ```
  - For one module, use `... -c '/app/.venv/bin/python -m unittest tests.<module> -v'`.
  - Baseline on 2026-10-02: `Ran 152 tests … OK (skipped=9)`.
- **digitaltwins-api tests**, from `services/api`: `PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/<file>`. Baseline: `tests/test_workflow_validation.py` has 22 passing.
- **Frontend tests**, from `services/portal/frontend`: `npx vitest run [file]`. Baseline: 50 passing.
- **Frontend type check and build** run in Node 20; the local Node 18 can't run `vue-tsc`. From `services/portal/frontend`:
  ```bash
  docker run --rm -v $PWD:/app -w /app node:20-alpine sh -c "corepack enable && corepack prepare yarn@1.22.22 --activate && yarn install --frozen-lockfile && yarn build"
  ```
  Record its `error TS` count before Task 10. There must be no new errors.
- **Fixed values:**
  - bundle file name `my-app.umd.js`
  - default build command `npm run build:plugin`
  - build-command rule `^(npm|yarn)\s+\S+`
  - test-build bucket `tool-builds`
  - backend route prefix `/plugin/<expose>`
  - bundle folder in the workflow package `primary/<tool_stem>/`
- **No commits unless the user asks** (user CLAUDE.md). Each task ends with a *checkpoint* that names the commit message to use if the user has authorised commits. When committing, use Conventional Commits and the Co-Authored-By trailer, and keep commits atomic. Before staging, check for secrets (gitleaks runs as a pre-commit hook).
- **Artifacts:** after editing anything in this folder, sync it right away. That means updating `task.md` and copying any regenerated document into `docs/artifacts/2026-10-02-155146-gui-workflow-tool-build/` (AGENTS.md). Use `<REDACTED>` for any secret.
- **Out of scope:** the existing tool-side bugs listed in the spec's "Out of scope" section. Don't fix them in passing.

## Review focus

Inputs and conditions the spec implies but doesn't spell out. Each one has a test in the task that owns the code.

1. **An SDS gui workflow registered before this change** (its GUI fields are null): a rebuild uses the defaults and builds from `code/` with `npm run build:plugin`. Covered in Task 5, `test_a_workflow_registered_before_gui_fields_uses_the_defaults`.
2. **A completed build from before this change** (no bundle): the Tool Hub doesn't list it, and `/metadata` skips it, so Launch never opens nothing. Covered in Task 7 and Task 8, `..._without_a_bundle_...`.
3. **Approval succeeded but the tool lookup failed** (`tool_dataset_uuid` is null): Launch falls back to the build's `tool-builds` bundle. Covered in Task 7, `test_an_approved_build_without_its_tool_dataset_falls_back_to_tool_builds`.
4. **The bundle upload to `tool-builds` fails:** the build still succeeds with `bundle_path` null, and nothing is listed until approval. Covered in Task 5 `test_a_failed_bundle_upload_does_not_fail_the_build` and Task 7 `test_a_build_with_nowhere_to_load_from_is_skipped`.
5. **A newer build exists after approval:** deploy, metadata and listing all use the **approved** build, so the bundle and its `/plugin/<expose>` backend route stay matched. Covered in Task 7 `test_the_approved_build_wins_over_a_newer_one` and Task 9 `test_deploy_uses_the_approved_build`.

---

### Task 1: digitaltwins-api copies `primary/<tool_stem>/` into the tool dataset

**Files:**
- Modify: `services/api/src/digitaltwins/workflows/pipeline.py:20-34` (`_assemble_tool`)
- Modify: `services/api/README.md` (section "Uploading a workflow dataset", after the bullet list of code folders, about line 194)
- Create: `services/api/tests/test_workflow_assemble_tool.py`

**Interfaces:**
- Produces: a workflow package's `primary/<tool_stem>/` contents end up in the tool dataset at `primary/`, so the tool dataset contains `primary/my-app.umd.js`.

- [ ] **Step 1: Write the failing test.**

```python
"""Tests for ``digitaltwins.workflows.pipeline._assemble_tool``: ``primary/<tool stem>/`` joins the tool's primary/."""
import yaml

from digitaltwins.tools.validation import find_tool_cwl
from digitaltwins.workflows.pipeline import _assemble_tool
from digitaltwins.workflows.validation import load_workflow

TOOL = {"cwlVersion": "v1.2", "class": "CommandLineTool", "inputs": {}, "outputs": {}}
WORKFLOW = {"cwlVersion": "v1.2", "class": "Workflow", "inputs": {}, "outputs": {},
            "steps": {"viewer": {"run": "tool_viewer.cwl", "in": {}, "out": []}}}


def _gui_workflow(root):
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary" / "workflow_viewer.cwl").write_text(yaml.safe_dump(WORKFLOW))
    (root / "primary" / "tool_viewer.cwl").write_text(yaml.safe_dump(TOOL))
    (root / "code" / "package.json").write_text("{}")
    return root


def _files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _assemble(root, parent):
    layout = load_workflow(root, "gui")
    return _assemble_tool(layout, layout.steps[0].tool_cwl, parent)


def test_a_tool_primary_folder_is_copied_into_the_tool_primary(tmp_path):
    root = _gui_workflow(tmp_path / "wf")
    (root / "primary" / "tool_viewer" / "assets").mkdir(parents=True)
    (root / "primary" / "tool_viewer" / "my-app.umd.js").write_text("//")
    (root / "primary" / "tool_viewer" / "assets" / "a.wasm").write_bytes(b"\0")

    tool = _assemble(root, tmp_path / "out")

    assert _files(tool / "primary") == ["assets/a.wasm", "my-app.umd.js", "tool_viewer.cwl"]
    assert find_tool_cwl(tool).name == "tool_viewer.cwl"


def test_without_the_folder_the_tool_is_assembled_as_before(tmp_path):
    tool = _assemble(_gui_workflow(tmp_path / "wf"), tmp_path / "out")

    assert _files(tool) == ["code/package.json", "dataset_description.xlsx", "primary/tool_viewer.cwl"]
```

- [ ] **Step 2: Run the test and check that it fails.** Run `cd services/api && PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/test_workflow_assemble_tool.py`. Expected: `test_a_tool_primary_folder_is_copied_into_the_tool_primary` fails because `my-app.umd.js` is missing; the other test passes.

- [ ] **Step 3: Implement.** In `_assemble_tool`, replace the docstring and add the copy after the CWL copy:

```python
def _assemble_tool(layout: WorkflowLayout, tool_cwl: Path, parent: Path) -> Path:
    """A tool dataset folder: the workflow's root metadata files, the tool's CWL, the files in
    ``primary/<tool stem>/`` (e.g. the portal's built GUI bundle) and the tool's code."""
    root = parent / tool_cwl.stem
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    for path in layout.root.iterdir():
        if path.is_file():
            shutil.copy2(path, root / path.name)
    shutil.copy2(tool_cwl, root / "primary" / tool_cwl.name)
    built = tool_cwl.parent / tool_cwl.stem
    if built.is_dir():
        shutil.copytree(built, root / "primary", dirs_exist_ok=True)
    for path in layout.tool_code[tool_cwl]:
        if path.is_dir():
            shutil.copytree(path, root / "code", dirs_exist_ok=True)
        else:
            shutil.copy2(path, root / "code" / path.name)
    return root
```

In `services/api/README.md`, after the three code bullets ("otherwise, for a notebook or gui tool, all of `code/`."), add this paragraph:

```markdown
If the package has a `primary/<tool_name>/` folder, its contents are copied into the tool dataset's `primary/`, next to the tool's CWL. The portal puts a gui workflow tool's built bundle (`my-app.umd.js` and its assets) there, so the tool can be launched like an approved portal GUI tool.
```

- [ ] **Step 4: Run the tests and check that they pass.** Run `PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/test_workflow_assemble_tool.py tests/test_workflow_validation.py`. Expected: 24 passed.

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit with `feat(api): carry a workflow tool's primary/<tool>/ files into its tool dataset`.

---

### Task 2: Portal schema for workflow GUI tools and workflow deployments

**Files:**
- Modify: `services/portal/backend/app/models/db_model.py`. Touch the imports (line 3); `Workflow` (about 158-182); `WorkflowBuild` (about 185-210); `PluginDeployment` (about 124-143); `PluginDeployResponse` (about 300-318).
- Modify: `services/portal/backend/app/database/database.py` (new migration function, plus a call in `init_db`)
- Test: `services/portal/backend/tests/test_db_constraints.py`

**Interfaces:**
- Produces:
  - `Workflow`: `has_backend` (Boolean, default False), `frontend_folder`, `frontend_build_command`, `backend_folder`
  - `WorkflowBuild`: `tool_name`, `bundle_path`, `tool_dataset_uuid`, and the `deployments` relationship
  - `PluginDeployment`: `workflow_build_id` and the `workflow_build` relationship; `plugin_id` and `build_id` become nullable
  - the constant `DEPLOYMENT_ONE_BUILD = "ck_plugin_deployments_one_build"`
  - `migrate_plugin_deployments_for_workflows(bind)`

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_db_constraints.py`, before `if __name__ == "__main__":`. Extend the model import to `from app.models.db_model import Base, Plugin, PluginBuild, PluginDeployment, Workflow, WorkflowBuild  # noqa: E402`, and add `from sqlalchemy.exc import IntegrityError  # noqa: E402`.

```python
def add_workflow_build(session):
    workflow = Workflow(name="w", version="1", repository_url="local://w", workflow_type="gui")
    session.add(workflow)
    session.flush()
    build = WorkflowBuild(workflow_id=workflow.id, build_id="wf-build-key")
    session.add(build)
    session.flush()
    return workflow, build


class WorkflowDeploymentTest(unittest.TestCase):
    def test_a_deployment_can_belong_to_a_workflow_build(self):
        session = make_fk_session()
        _, build = add_workflow_build(session)
        session.add(PluginDeployment(workflow_build_id=build.build_id, deploy_id="d1"))
        session.commit()
        self.assertEqual(session.query(PluginDeployment).one().workflow_build.build_id, "wf-build-key")

    def test_a_deployment_needs_a_build(self):
        session = make_fk_session()
        session.add(PluginDeployment(deploy_id="d2"))
        with self.assertRaises(IntegrityError):
            session.commit()

    def test_a_deployment_belongs_to_only_one_build(self):
        session = make_fk_session()
        add_plugin_with_deployment(session)
        _, build = add_workflow_build(session)
        session.add(PluginDeployment(build_id="build-business-key", workflow_build_id=build.build_id, deploy_id="d3"))
        with self.assertRaises(IntegrityError):
            session.commit()

    def test_delete_workflow_cascades_its_deployments(self):
        session = make_fk_session()
        workflow, build = add_workflow_build(session)
        session.add(PluginDeployment(workflow_build_id=build.build_id, deploy_id="d4"))
        session.commit()
        session.delete(workflow)
        session.commit()
        self.assertEqual(session.query(PluginDeployment).count(), 0)

    def test_the_postgres_migration_leaves_sqlite_alone(self):
        from app.database.database import migrate_plugin_deployments_for_workflows
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        migrate_plugin_deployments_for_workflows(engine)  # must not raise
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_db_constraints -v'`. Expected: errors on `workflow_build_id` (an invalid keyword for `PluginDeployment`) and an `ImportError` for `migrate_plugin_deployments_for_workflows`.

- [ ] **Step 3: Implement the models.** In `db_model.py`:
  - Add `CheckConstraint` to the `sqlalchemy` import on line 3.
  - Add this constant after `PORTAL_DB_SCHEMA`:

```python
# A deployment runs the backend of either a tool build or a gui workflow's build, never both.
DEPLOYMENT_ONE_BUILD = "ck_plugin_deployments_one_build"
```

Replace the `PluginDeployment` class header and its first columns, keeping the rest of the class:

```python
class PluginDeployment(Base):
    __tablename__ = "plugin_deployments"
    __table_args__ = (CheckConstraint("(build_id IS NULL) <> (workflow_build_id IS NULL)", name=DEPLOYMENT_ONE_BUILD),)
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=True)  # null for a gui workflow's tool
    # References the build's business key (what the deploy endpoint stores), not plugin_builds.id.
    build_id = Column(String, ForeignKey("plugin_builds.build_id"), nullable=True)
    workflow_build_id = Column(String, ForeignKey("workflow_builds.build_id"), nullable=True)
```

…and add this beside the existing relationships at the bottom of the class:

```python
    workflow_build = relationship("WorkflowBuild", back_populates="deployments")
```

In `Workflow`, after `seek_project_id`:

```python
    # A gui SDS workflow builds its tool's frontend like a GUI tool (Plugin); folders are relative to code/.
    has_backend = Column(Boolean, nullable=True, default=False)
    frontend_folder = Column(String, nullable=True)
    frontend_build_command = Column(String, nullable=True)
    backend_folder = Column(String, nullable=True)
```

In `WorkflowBuild`, after `handoff_user`:

```python
    # A gui SDS workflow's built tool (app/builder/build_workflow.py): its CWL stem (set only when the bundle
    # was built), the bundle's tool-builds prefix (null if that upload failed) and, once approved, its tool dataset.
    tool_name = Column(String, nullable=True)
    bundle_path = Column(String, nullable=True)        # e.g. tool-builds/<expose>/primary
    tool_dataset_uuid = Column(String, nullable=True)
```

…and after `workflow = relationship(...)`:

```python
    deployments = relationship("PluginDeployment", back_populates="workflow_build", cascade="all, delete-orphan")
```

In `PluginDeployResponse`, change `plugin_id: str` and `build_id: str` to `Optional[str] = None`, and add `workflow_build_id: Optional[str] = None`.

- [ ] **Step 4: Implement the Postgres migration.** In `database.py`, change the first line to `from app.models.db_model import SessionLocal, Base, engine, PORTAL_DB_SCHEMA, DEPLOYMENT_ONE_BUILD`, and add this after `migrate_workflow_is_sds`:

```python
def migrate_plugin_deployments_for_workflows(bind=engine):
    """Let a deployment belong to a gui workflow's build (create_all does this for new tables).

    Postgres tables created before 2026-10-02 get nullable plugin_id/build_id, the workflow_build_id
    foreign key and the one-build check. SQLite databases are only test or legacy ones and are left alone.
    """
    from sqlalchemy import inspect, text

    if bind.dialect.name != "postgresql":
        return
    inspector = inspect(bind)
    if not inspector.has_table("plugin_deployments"):
        return
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("plugin_deployments")}
    checks = {ck["name"] for ck in inspector.get_check_constraints("plugin_deployments")}
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE plugin_deployments ALTER COLUMN plugin_id DROP NOT NULL"))
        conn.execute(text("ALTER TABLE plugin_deployments ALTER COLUMN build_id DROP NOT NULL"))
        if "plugin_deployments_workflow_build_id_fkey" not in foreign_keys:
            logger.info("Migrating: plugin_deployments.workflow_build_id references workflow_builds.build_id")
            conn.execute(text("ALTER TABLE plugin_deployments ADD CONSTRAINT plugin_deployments_workflow_build_id_fkey "
                              "FOREIGN KEY (workflow_build_id) REFERENCES workflow_builds (build_id)"))
        if DEPLOYMENT_ONE_BUILD not in checks:
            logger.info("Migrating: a plugin deployment belongs to exactly one build")
            conn.execute(text(f"ALTER TABLE plugin_deployments ADD CONSTRAINT {DEPLOYMENT_ONE_BUILD} "
                              "CHECK ((build_id IS NULL) <> (workflow_build_id IS NULL))"))
```

In `init_db`, call it right after `migrate_add_missing_columns(bind)`, which creates `workflow_build_id` first:

```python
    migrate_add_missing_columns(bind)
    migrate_plugin_deployments_for_workflows(bind)
    migrate_enum_values(bind)
```

- [ ] **Step 5: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_db_constraints tests.test_postgres_integration tests.test_migrate_sqlite_to_postgres -v'`. Expected: OK. The Postgres integration tests skip when Postgres is unreachable.

- [ ] **Step 6: Checkpoint.** If the user has authorised commits, commit with `feat(portal): store gui workflow tool layout and let deployments belong to workflow builds`.

---

### Task 3: Workflow registration accepts and checks the GUI fields

**Files:**
- Modify: `services/portal/backend/app/models/db_model.py`. Touch the imports, `WorkflowBase` (about 342-350) and `WorkflowCreate` (about 397-399).
- Test: `services/portal/backend/tests/test_workflow_create.py`

**Interfaces:**
- Consumes: the `Workflow` columns from Task 2.
- Produces:
  - `DEFAULT_GUI_BUILD_COMMAND = "npm run build:plugin"` in `app.models.db_model`
  - `WorkflowBase` fields `has_backend`, `frontend_folder`, `frontend_build_command` and `backend_folder`, which `WorkflowResponse` inherits
  - `POST /api/workflow/create` stores these fields

- [ ] **Step 1: Write the failing tests.** Add these to `WorkflowCreateTest`:

```python
    GUI = ("has_backend", "frontend_folder", "frontend_build_command", "backend_folder")

    def _gui(self, r):
        self.assertEqual(r.status_code, 200, r.text)
        return {k: r.json()[k] for k in self.GUI}

    def test_a_gui_workflow_keeps_its_frontend_layout(self):
        r = self._create({**BODY, "workflow_type": "gui", "has_backend": True, "frontend_folder": "frontend",
                          "backend_folder": "backend", "frontend_build_command": "yarn build"})
        self.assertEqual(self._gui(r), {"has_backend": True, "frontend_folder": "frontend",
                                        "frontend_build_command": "yarn build", "backend_folder": "backend"})

    def test_a_gui_workflow_defaults_to_the_plugin_build_without_a_backend(self):
        r = self._create({**BODY, "workflow_type": "gui", "frontend_folder": "ignored"})
        self.assertEqual(self._gui(r), {"has_backend": False, "frontend_folder": None,
                                        "frontend_build_command": "npm run build:plugin", "backend_folder": None})

    def test_a_gui_build_command_must_be_npm_or_yarn(self):
        r = self._create({**BODY, "workflow_type": "gui", "frontend_build_command": "make all"})
        self.assertEqual(r.status_code, 422)

    def test_a_backend_needs_both_folders(self):
        r = self._create({**BODY, "workflow_type": "gui", "has_backend": True, "frontend_folder": "frontend"})
        self.assertEqual(r.status_code, 422)

    def test_other_types_drop_the_gui_fields(self):
        r = self._create({**BODY, "workflow_type": "script", "has_backend": True, "frontend_folder": "f",
                          "backend_folder": "b", "frontend_build_command": "npm run x"})
        self.assertEqual(self._gui(r), {"has_backend": False, "frontend_folder": None,
                                        "frontend_build_command": None, "backend_folder": None})
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_create -v'`. Expected: `KeyError: 'has_backend'` in the response, and the two 422 tests get 200.

- [ ] **Step 3: Implement.**
  - At the top of `db_model.py`, add `import re`, and change the pydantic import to `from pydantic import BaseModel, model_validator`.
  - After the `DeployStatus` enum, add:

```python
# A GUI tool's frontend build command (tools and gui workflows): only npm or yarn runs on the portal.
DEFAULT_GUI_BUILD_COMMAND = "npm run build:plugin"
GUI_BUILD_COMMAND = re.compile(r"^(npm|yarn)\s+\S+")
```

In `WorkflowBase`, after `workflow_type`:

```python
    # gui SDS workflows only (see Workflow): how to build the tool's frontend, as for GUI tools.
    has_backend: Optional[bool] = False
    frontend_folder: Optional[str] = None
    frontend_build_command: Optional[str] = None
    backend_folder: Optional[str] = None
```

In `WorkflowCreate`, after `upload_id`:

```python
    @model_validator(mode="after")
    def _gui_fields(self):
        """Only a gui workflow keeps a frontend layout; a backend needs both folders (relative to code/)."""
        if self.workflow_type != "gui":
            self.has_backend, self.frontend_folder, self.frontend_build_command, self.backend_folder = False, None, None, None
            return self
        self.has_backend = bool(self.has_backend)
        self.frontend_build_command = self.frontend_build_command or DEFAULT_GUI_BUILD_COMMAND
        if not GUI_BUILD_COMMAND.match(self.frontend_build_command):
            raise ValueError("frontend_build_command must be an npm or yarn command, e.g. npm run build:plugin")
        if self.has_backend and not (self.frontend_folder and self.backend_folder):
            raise ValueError("A gui workflow with a backend needs frontend_folder and backend_folder")
        if not self.has_backend:
            self.frontend_folder = self.backend_folder = None
        return self
```

`create_tool_plugin` in `workflow_router.py` already does `Workflow(**data, …)` from `model_dump()`, so it needs no change.

- [ ] **Step 4: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_create tests.test_workflow_type tests.test_workflow_auth -v'`. Expected: OK.

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit with `feat(portal): accept a gui workflow's frontend layout at registration`.

---

### Task 4: Extract `PluginBuilder.build_frontend`, the shared GUI build

**Files:**
- Modify: `services/portal/backend/app/builder/build_tool.py`. Add a new method before `build()` (about line 506), and replace the GUI block inside `build()` (about 565-630).
- Create: `services/portal/backend/tests/test_gui_frontend_build.py`

**Interfaces:**
- Produces: `PluginBuilder.build_frontend(self, frontend_path: Path, expose_name: str, build_command: str, has_backend: bool, sink=None) -> Optional[Path]`. It returns the `dist/` or `build/` folder, or None. It raises `RuntimeError` when there is no `package.json`, or when npm install or the build fails.

- [ ] **Step 1: Write the tests.** The `PluginGuiBuildTest` characterisation test passes **before** the refactor and must still pass after it.

```python
"""PluginBuilder.build_frontend: the GUI tool build shared by tool builds and gui workflow builds.

Run from `backend/`:
    python -m unittest tests.test_gui_frontend_build
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from app.builder import build_tool  # noqa: E402
from app.builder.build_tool import PluginBuilder  # noqa: E402

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n"
# `name` before `fileName`: the lib-block rewrite stops at the first `}` (here, inside `${format}`).
VITE_CONFIG = """import { defineConfig } from 'vite'
export default defineConfig({
  plugins: [],
  build: {
    lib: { entry: './src/index.ts', name: 'placeholder', formats: ['es'], fileName: (format) => `x.${format}.js` },
    rollupOptions: { external: ['vue', 'vuetify', 'pinia', 'vue-toastification'] },
  },
})
"""


def make_frontend(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name": "viewer", "version": "2.1.0"}')
    (root / "vite.config.ts").write_text(VITE_CONFIG)
    return root


def fake_npm(project_dir, *args, **kwargs):
    """Stands in for frontend_install / frontend_build: 'builds' dist/my-app.umd.js."""
    (project_dir / "dist").mkdir(exist_ok=True)
    (project_dir / "dist" / "my-app.umd.js").write_text("//")
    return {"success": True, "stdout": "", "stderr": ""}


class FakeMinio:
    def upload_directory(self, local, prefix):
        return f"s3://tool-builds/{prefix}"


class BuildFrontendTest(unittest.TestCase):
    def setUp(self):
        self.builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        self.frontend = make_frontend(Path(tempfile.mkdtemp()) / "frontend")

    def _build(self, has_backend=False, build=fake_npm):
        with mock.patch.object(self.builder, "frontend_install", side_effect=fake_npm), \
             mock.patch.object(self.builder, "frontend_build", side_effect=build) as npm_build:
            out = self.builder.build_frontend(self.frontend, "viewer_ab12cd34", "yarn build", has_backend)
        return out, npm_build

    def test_builds_the_umd_bundle_under_the_expose_name(self):
        out, npm_build = self._build()
        self.assertEqual(out, self.frontend / "dist")
        config = (self.frontend / "vite.config.ts").read_text()
        self.assertIn("name: 'viewer_ab12cd34'", config)
        self.assertIn("formats: ['umd']", config)
        self.assertIn("my-app.${format}.js", config)
        self.assertEqual(npm_build.call_args.args[:2], (self.frontend, "yarn build"))
        self.assertFalse((self.frontend / ".env").exists())

    def test_a_backend_gets_its_route_prefix(self):
        self._build(has_backend=True)
        self.assertIn("VITE_PLUGIN_ROUTE_PREFIX=/plugin/viewer_ab12cd34", (self.frontend / ".env").read_text())

    def test_a_folder_without_package_json_is_refused(self):
        (self.frontend / "package.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "No package.json"):
            self._build()

    def test_a_failed_npm_build_fails(self):
        def failed(*args, **kwargs):
            return {"success": False, "error": "exited with code 1"}
        with self.assertRaisesRegex(RuntimeError, "npm build failed: exited with code 1"):
            self._build(build=failed)


class PluginGuiBuildTest(unittest.TestCase):
    """Characterisation: a GUI tool build still puts the bundle next to the CWL."""

    def test_a_gui_tool_build_puts_the_bundle_in_primary(self):
        src = make_frontend(Path(tempfile.mkdtemp()))
        (src / "viewer.cwl").write_text(CWL)
        builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        with mock.patch.object(build_tool, "get_minio_client", lambda bucket=None: FakeMinio()), \
             mock.patch.object(builder, "frontend_install", side_effect=fake_npm), \
             mock.patch.object(builder, "frontend_build", side_effect=fake_npm), \
             mock.patch.object(PluginBuilder, "_update_plugin_version", return_value="2.1.0"):
            result = builder.build({"id": "p1", "name": "Viewer", "label": "GUI", "has_backend": False,
                                    "source_type": "local", "local_archive_path": str(src),
                                    "frontend_build_command": "npm run build:plugin", "metadata": {}})
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(sorted(p.name for p in (Path(result["dataset_path"]) / "primary").iterdir()),
                         ["my-app.umd.js", "tool_viewer.cwl"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_gui_frontend_build -v'`. Expected: the four `BuildFrontendTest` tests fail with `AttributeError: 'PluginBuilder' object has no attribute 'build_frontend'`, and `PluginGuiBuildTest` **passes**.

- [ ] **Step 3: Implement.** Add this method to `PluginBuilder`, right before `def build(`:

```python
    def build_frontend(self, frontend_path: Path, expose_name: str, build_command: str,
                       has_backend: bool, sink=None) -> Optional[Path]:
        """Build a GUI tool's frontend as the portal's UMD plugin bundle, exposed as ``expose_name``.

        Shared by tool builds and gui workflow builds (build_workflow.py). Returns the dist/ or build/
        folder, or None if the build left neither.
        """
        if not self.check_npm_project(frontend_path):
            raise RuntimeError("No package.json found - not an npm project")
        logger.info("npm project detected; updating vite.config")
        self._update_vite_config(frontend_path, expose_name)
        if has_backend:
            logger.info("Creating the frontend .env file with the backend route prefix")
            self._create_env_file(frontend_path, expose_name)

        logger.info("Running npm install")
        install_result = self.frontend_install(frontend_path, sink=sink)
        if not install_result["success"]:
            raise RuntimeError(f"npm install failed: {install_result.get('error', 'Unknown error')}")
        logger.info("Running npm build")
        build_result = self.frontend_build(frontend_path, build_command, sink=sink)
        if not build_result["success"]:
            raise RuntimeError(f"npm build failed: {build_result.get('error', 'Unknown error')}")

        for dir_name in ("dist", "build"):
            if (frontend_path / dir_name).exists():
                logger.info(f"Found build output directory: {frontend_path / dir_name}")
                return frontend_path / dir_name
        return None
```

In `build()`, replace everything from `# Step 2: Check if it's an npm project and extract metadata` down to just before `# read config file in the cloned directory` with:

```python
                # Steps 2-4: vite.config rewrite, .env route prefix, npm install + build
                logger.info("Step 2: Building the frontend...")
                frontend_path = layout.source_dir / frontend_folder if has_backend else layout.source_dir
                build_output_dir = self.build_frontend(frontend_path, plugin_unique_expose_name,
                                                       frontend_build_command, has_backend, sink=sink)
                logger.info("npm build completed successfully")

                # update plugin version base on plugin frontend package.json version
                new_version = self._update_plugin_version(frontend_path, plugin_id)
                version = new_version if new_version is not None else version
```

Then delete the now-redundant output-directory search (from `# Look for common build output directories` down to the `break` loop) that sits just before `dataset_dir = self.create_sparc_dataset(project_dir, label, has_backend, build_output_dir, …)`. Keep the `config.portal.json` block and the `logger.info("Step 5: …")` line as they are.

- [ ] **Step 4: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_gui_frontend_build tests.test_tool_build_dataset tests.test_vite_config_injection tests.test_subprocess_env_scrub tests.test_tool_sds_source -v'`. Expected: OK.

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit with `refactor(portal): extract the GUI frontend build into PluginBuilder.build_frontend`.

---

### Task 5: A gui SDS workflow build builds its tool's frontend

**Files:**
- Modify: `services/portal/backend/app/builder/build_workflow.py`
- Modify: `services/portal/backend/app/router/workflow_router.py` (`_trigger_workflow_build`'s `workflow_dict`, about lines 325-338)
- Modify: `services/portal/backend/app/utils/builder_utils.py` (`execute_build_in_background` success branch, about lines 318-322)
- Test: `services/portal/backend/tests/test_workflow_build_dataset.py`, `services/portal/backend/tests/test_workflow_build_executor.py`

**Interfaces:**
- Consumes: `PluginBuilder.build_frontend` (Task 4), `DEFAULT_GUI_BUILD_COMMAND` (Task 3), and `TOOL_BUILDS_BUCKET = "tool-builds"` from `app.builder.build_tool`.
- Produces:
  - `WorkflowBuilder.build_gui_tool(package_root: Path, dataset_dir: Path, workflow: dict, expose_name: str) -> str`, which returns the tool stem.
  - The `WorkflowBuilder.build()` result gains `"tool_name"` and `"bundle_path"`; both are None unless a bundle was built.
  - The executor stores both on `WorkflowBuild`.
  - `workflow_dict` carries `has_backend`, `frontend_folder`, `frontend_build_command` and `backend_folder`.

- [ ] **Step 1: Write the failing builder tests.** In `tests/test_workflow_build_dataset.py`:
  - Add the imports `from unittest import mock` and `from app.builder.build_tool import PluginBuilder`.
  - Add a FakeMinio that records buckets and can fail.
  - Add this class:

```python
class RecordingMinio:
    def __init__(self, buckets, fail=()):
        self.buckets, self.fail = buckets, fail

    def __call__(self, bucket):
        self.buckets.append(bucket)
        outer = self

        class Client:
            def upload_directory(self, path, name):
                if bucket in outer.fail:
                    raise RuntimeError("MinIO unreachable")
                return f"s3://{bucket}/{name}"
        return Client()


class GuiWorkflowBuildTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        self.buckets, self.calls = [], []
        build_workflow.get_minio_client = RecordingMinio(self.buckets)
        self.builder = WorkflowBuilder(dataset_dir=tempfile.mkdtemp())
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")
        (self.root / "code" / "package.json").write_text("{}")

    def _fake_build_frontend(self, _builder, frontend, expose, command, has_backend, sink=None):
        self.calls.append({"frontend": frontend, "expose": expose, "command": command, "has_backend": has_backend})
        (frontend / "dist").mkdir()
        (frontend / "dist" / "my-app.umd.js").write_text("//")
        return frontend / "dist"

    def _build(self, workflow_type="gui", side_effect=None, **gui):
        with mock.patch.object(PluginBuilder, "build_frontend", autospec=True,
                               side_effect=side_effect or self._fake_build_frontend):
            return self.builder.build({"id": "w1", "name": "convert", "source_type": "local",
                                       "local_archive_path": str(self.root), "workflow_type": workflow_type, **gui})

    def test_a_gui_workflow_gets_its_bundle_in_primary_tool_folder(self):
        result = self._build(frontend_build_command="yarn build:plugin")
        self.assertTrue(result["success"], result["error_message"])
        self.assertIn("primary/tool_convert/my-app.umd.js", _files(Path(result["dataset_path"])))
        self.assertEqual(result["tool_name"], "tool_convert")
        self.assertEqual(result["bundle_path"], f"tool-builds/{result['expose_name']}/primary")
        self.assertIn("tool-builds", self.buckets)
        [call] = self.calls
        self.assertEqual((call["expose"], call["command"], call["has_backend"]),
                         (result["expose_name"], "yarn build:plugin", False))

    def test_the_source_is_never_modified(self):
        before = _files(self.root)
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(_files(self.root), before)
        self.assertNotIn(self.root, self.calls[0]["frontend"].parents)

    def test_a_workflow_registered_before_gui_fields_uses_the_defaults(self):
        self._build()  # no has_backend / folders / command keys at all
        [call] = self.calls
        self.assertEqual((call["frontend"].name, call["command"], call["has_backend"]),
                         ("code", "npm run build:plugin", False))

    def test_a_backend_builds_its_frontend_folder_and_keeps_its_backend(self):
        for layer in ("frontend", "backend"):
            (self.root / "code" / layer).mkdir()
        (self.root / "code" / "backend" / "docker-compose.yml").write_text("services: {}\n")
        result = self._build(has_backend=True, frontend_folder="frontend", backend_folder="backend")
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls[0]["frontend"].name, self.calls[0]["has_backend"]), ("frontend", True))
        self.assertIn("code/backend/docker-compose.yml", _files(Path(result["dataset_path"])))

    def test_a_failed_frontend_build_fails_the_workflow_build(self):
        def failing(*args, **kwargs):
            raise RuntimeError("npm build failed: exited with code 1")
        result = self._build(side_effect=failing)
        self.assertFalse(result["success"])
        self.assertIn("npm build failed", result["error_message"])

    def test_a_failed_bundle_upload_does_not_fail_the_build(self):
        build_workflow.get_minio_client = RecordingMinio(self.buckets, fail=("tool-builds",))
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((result["tool_name"], result["bundle_path"]), ("tool_convert", None))

    def test_script_workflows_are_not_npm_built(self):
        result = self._build(workflow_type="script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls, result["tool_name"], result["bundle_path"]), ([], None, None))

    def test_a_root_cwl_gui_workflow_is_built_as_before(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "flow.cwl").write_text(WORKFLOW)
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls, result["tool_name"]), ([], None))
```

In `tests/test_workflow_build_executor.py`, add to `WorkflowBuildExecutorTest`:

```python
    def test_a_gui_build_records_its_tool_and_bundle(self):
        self._run({"success": True, "s3_path": None, "dataset_path": "/d", "expose_name": "convert_ab12",
                   "is_sds": True, "tool_name": "tool_convert", "bundle_path": "tool-builds/convert_ab12/primary"})
        with SessionLocal() as db:
            build = db.query(WorkflowBuild).filter(WorkflowBuild.build_id == self.build_id).one()
            self.assertEqual((build.tool_name, build.bundle_path),
                             ("tool_convert", "tool-builds/convert_ab12/primary"))
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_build_dataset tests.test_workflow_build_executor -v'`. Expected: the gui tests fail with `KeyError: 'tool_name'` or with `self.calls` empty, the executor test asserts `None`, and the script and root-`.cwl` tests fail on the missing `tool_name` key.

- [ ] **Step 3: Implement the builder.** In `build_workflow.py`:
  - Add `import tempfile` to the imports.
  - Add `from app.builder.build_tool import PluginBuilder, TOOL_BUILDS_BUCKET` and `from app.models.db_model import DEFAULT_GUI_BUILD_COMMAND`.
  - Extend `from app.utils.utils import safe_path` to `from app.utils.utils import force_rmtree, safe_path`.
  - Add these methods to `WorkflowBuilder`, after `create_sparc_dataset`:

```python
    def build_gui_tool(self, package_root: Path, dataset_dir: Path, workflow: Dict[str, Any], expose_name: str) -> str:
        """Build a gui SDS workflow's tool frontend into ``primary/<tool stem>/`` of the dataset; returns the stem.

        digitaltwins-api copies that folder into the tool dataset's primary/ on approval. The build runs in a
        scratch copy of code/, so the source (for a local upload, its staging folder) is never modified.
        """
        tool_cwls = sorted(p for p in (package_root / "primary").glob("tool_*.cwl") if p.is_file())
        if len(tool_cwls) != 1:
            raise RuntimeError(f"A gui workflow must have exactly one primary/tool_*.cwl (found {len(tool_cwls)})")
        tool_name = tool_cwls[0].stem
        has_backend = bool(workflow.get("has_backend"))
        scratch = Path(tempfile.mkdtemp(prefix="gui_build_", dir=self.tmp_dir))
        try:
            code = scratch / "code"
            code.mkdir()
            for item in (package_root / "code").iterdir():
                copy_item(item, code)  # skips .git, node_modules, dist, build
            frontend = code / workflow["frontend_folder"] if has_backend else code
            command = workflow.get("frontend_build_command") or DEFAULT_GUI_BUILD_COMMAND
            output = PluginBuilder(dataset_dir=str(self.dataset_dir)).build_frontend(
                frontend, expose_name, command, has_backend)
            if output is None:
                raise RuntimeError("The frontend build produced no dist/ or build/ folder")
            shutil.copytree(output, dataset_dir / "primary" / tool_name, dirs_exist_ok=True)
        finally:
            force_rmtree(scratch)
        return tool_name

    @staticmethod
    def upload_bundle(bundle_dir: Path, expose_name: str) -> Optional[str]:
        """Serve a gui workflow's bundle before approval from the public tool-builds bucket, like a tool test build.

        Returns the bundle's prefix, or None if the upload failed (the build still succeeds, as for tools).
        """
        prefix = f"{expose_name}/primary"
        try:
            get_minio_client(TOOL_BUILDS_BUCKET).upload_directory(str(bundle_dir), prefix)
        except Exception as e:
            logger.error(f"Failed to upload the gui tool bundle to {TOOL_BUILDS_BUCKET}: {e}")
            return None
        return f"{TOOL_BUILDS_BUCKET}/{prefix}"
```

In `build()`, right after the `logger.info(f"SPARC dataset created in {dataset_dir}")` that follows Step 2, add:

```python
            # Step 2.1: a gui SDS workflow builds its one tool's frontend, as GUI tools do
            tool_name = bundle_path = None
            if layout.is_sds and workflow_type == "gui":
                logger.info("Step 2.1: Building the gui tool's frontend")
                tool_name = self.build_gui_tool(layout.root, dataset_dir, workflow, workflow_unique_expose_name)
                bundle_path = self.upload_bundle(dataset_dir / "primary" / tool_name, workflow_unique_expose_name)
```

…and add `"tool_name": tool_name, "bundle_path": bundle_path,` to the success return dict, after `"is_sds"`.

- [ ] **Step 4: Pass the GUI fields into the build.** In `workflow_router._trigger_workflow_build`, add these to `workflow_dict` after `"workflow_type"`:

```python
        "has_backend": workflow.has_backend,
        "frontend_folder": workflow.frontend_folder,
        "frontend_build_command": workflow.frontend_build_command,
        "backend_folder": workflow.backend_folder,
```

- [ ] **Step 5: Store the results.** In `builder_utils.execute_build_in_background`, right after the `if "is_sds" in result:` block, add:

```python
                        if result.get("tool_name"):  # a gui workflow's built tool (build_workflow.py)
                            build_record.tool_name = result["tool_name"]
                            build_record.bundle_path = result["bundle_path"]
```

- [ ] **Step 6: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_build_dataset tests.test_workflow_build_executor tests.test_workflow_sds_source -v'`. Expected: OK.

- [ ] **Step 7: Checkpoint.** If the user has authorised commits, commit with `feat(portal): build a gui SDS workflow's tool frontend during the workflow build`.

---

### Task 6: Approval records the gui workflow's tool dataset

**Files:**
- Modify: `services/portal/backend/app/services/workflow_handoff.py` (`_complete`, about lines 70-86)
- Modify: `services/portal/backend/tests/test_tool_handoff.py` (`FakeApi`: add a `/workflow-tools` route)
- Test: `services/portal/backend/tests/test_workflow_handoff.py`

**Interfaces:**
- Consumes: digitaltwins-api's `GET /datasets/{uuid}/workflow-tools`, which returns `{workflow_type, tools: [{dataset_uuid, dataset_name, seek_id, step_ids}]}`.
- Produces: `WorkflowBuild.tool_dataset_uuid` is set when a gui workflow's approval completes.

- [ ] **Step 1: Extend the fake.** In `FakeApi.__init__`, add:

```python
        self.workflow_tools = []          # what GET /datasets/{uuid}/workflow-tools lists
        self.fail_workflow_tools = False
```

In `FakeApi.__call__`, add this route **before** the `if path.startswith("/datasets/") and method == "GET":` line:

```python
        if path.startswith("/datasets/") and path.endswith("/workflow-tools"):
            if self.fail_workflow_tools:
                return httpx.Response(500, json={"detail": "Postgres unreachable"})
            return httpx.Response(200, json={"workflow_type": "gui", "tools": self.workflow_tools})
```

- [ ] **Step 2: Write the failing tests.** Add to `WorkflowHandoffTest`:

```python
    def _make_gui(self):
        with SessionLocal() as db:
            db.get(Workflow, self.wf_id).workflow_type = "gui"
            db.commit()

    def _tool_dataset(self):
        with SessionLocal() as db:
            return db.query(WorkflowBuild).filter(WorkflowBuild.build_id == self.build_id).one().tool_dataset_uuid

    def test_a_gui_approval_records_its_tool_dataset(self):
        self._make_gui()
        self.api.workflow_tools = [{"dataset_uuid": "tool-1", "dataset_name": "tool_convert", "seek_id": "7",
                                    "step_ids": ["convert"]}]
        self._approve()
        self.assertEqual(self._status().json()["handoff_status"], "completed")
        self.assertEqual(self._tool_dataset(), "tool-1")

    def test_an_unknown_tool_dataset_does_not_fail_the_approval(self):
        self._make_gui()
        self.api.fail_workflow_tools = True
        self._approve()
        self.assertEqual(self._status().json()["handoff_status"], "completed")
        self.assertIsNone(self._tool_dataset())

    def test_a_script_approval_does_not_look_up_tools(self):
        self.api.workflow_tools = [{"dataset_uuid": "tool-1"}]
        self._approve()
        self.assertIsNone(self._tool_dataset())
```

- [ ] **Step 3: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_handoff -v'`. Expected: `test_a_gui_approval_records_its_tool_dataset` fails because `None != 'tool-1'`.

- [ ] **Step 4: Implement.** In `workflow_handoff.py`, add this function above `_complete` (if `Optional` isn't imported yet, add it from `typing`):

```python
def _tool_dataset_uuid(api: tool_handoff.Api, workflow: Workflow, dataset_uuid: str) -> Optional[str]:
    """The platform tool dataset of a gui workflow's one step, so the Tool Hub can launch it (None if unknown)."""
    if workflow.workflow_type != "gui":
        return None
    try:
        tools = api.request("GET", f"/datasets/{dataset_uuid}/workflow-tools")["tools"]
    except Exception as exc:
        logger.warning("Tool dataset of gui workflow %s not found: %s", workflow.id, exc)
        return None
    return tools[0]["dataset_uuid"] if len(tools) == 1 else None
```

In `_complete`, set it together with the other build fields:

```python
    build.dataset_uuid, build.seek_id, build.handoff_status = dataset_uuid, seek_id, "completed"
    build.tool_dataset_uuid = _tool_dataset_uuid(api, workflow, dataset_uuid)
    workflow.uuid = dataset_uuid
```

- [ ] **Step 5: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_handoff tests.test_tool_handoff tests.test_tool_catalogue -v'`. Expected: OK.

- [ ] **Step 6: Checkpoint.** If the user has authorised commits, commit with `feat(portal): record a gui workflow's platform tool dataset on approval`.

---

### Task 7: The launcher's metadata lists gui workflow tools, and build logs fall back to workflow builds

**Files:**
- Modify: `services/portal/backend/app/utils/workflow_tool_utils.py` (new helpers)
- Modify: `services/portal/backend/app/router/workflow_tool_plugin.py`. Touch the imports (lines 20-27 and 38-41), `get_metadata_json` (about 921-962) and `get_build_logs` (about 868-877).
- Modify: `services/portal/backend/tests/tool_app.py` (add `make_hub_client`)
- Create: `services/portal/backend/tests/test_workflow_gui_tools.py`

**Interfaces:**
- Consumes: `WorkflowBuild.tool_name`, `bundle_path` and `tool_dataset_uuid` (Tasks 2, 5 and 6).
- Produces:
  - `served_workflow_build(db, workflow) -> Optional[WorkflowBuild]`
  - `workflow_bundle_path(build) -> Optional[str]`
  - `latest_deployment(db, build) -> Optional[PluginDeployment]`
  - `/api/tools/metadata` entries with `kind: "workflow"` and `id` = the workflow id
  - `tests.tool_app.make_hub_client()`, which serves both routers

- [ ] **Step 1: Add the test client.** In `tests/tool_app.py`, add:

```python
def make_hub_client():
    """Both the /api/tools and /api/workflow routers, as the Tool Hub uses them, on fresh SQLite tables."""
    from app.router import workflow_router  # imported late: it builds MinIO / FHIR clients at import

    auth.get_keycloak_client = lambda: FakeKeycloak()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(workflow_tool_plugin.router)
    app.include_router(workflow_router.router)
    return TestClient(app)
```

- [ ] **Step 2: Write the failing tests.** Create `tests/test_workflow_gui_tools.py`:

```python
"""A gui SDS workflow's tool in the Tool Hub: launcher metadata, the listing, its backend deploy.

Run from `backend/`:
    python -m unittest tests.test_workflow_gui_tools
"""
import unittest
import uuid
from datetime import datetime, timedelta

from tests.tool_app import bearer, make_hub_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, PluginDeployment, SessionLocal, Workflow, WorkflowBuild


def add_workflow(workflow_type="gui", has_backend=False, **fields):
    with SessionLocal() as db:
        wf = Workflow(name="workflow_volview", version="1.0", repository_url="local://v", source_type="local",
                      workflow_type=workflow_type, is_sds=True, has_backend=has_backend,
                      backend_folder="backend" if has_backend else None, **fields)
        db.add(wf)
        db.commit()
        return wf.id


def add_build(wf_id, age_minutes=0, bundle=True, status=BuildStatus.COMPLETED.value, **fields):
    expose = f"workflowvolview_{uuid.uuid4().hex[:8]}"
    values = {"tool_name": "tool_volview" if bundle else None,
              "bundle_path": f"tool-builds/{expose}/primary" if bundle else None, **fields}
    with SessionLocal() as db:
        build = WorkflowBuild(workflow_id=wf_id, build_id=str(uuid.uuid4()), status=status, expose_name=expose,
                              dataset_path=f"/portal_workspace/workflows/{expose}",
                              created_at=datetime(2026, 10, 2, 12) - timedelta(minutes=age_minutes), **values)
        db.add(build)
        db.commit()
        return build.build_id, expose


def approve(wf_id, build_id, tool_uuid="tool-v"):
    with SessionLocal() as db:
        db.get(Workflow, wf_id).uuid = "wf-v"
        build = db.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).one()
        build.dataset_uuid, build.tool_dataset_uuid = "wf-v", tool_uuid
        db.commit()


class LauncherMetadataTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def _components(self):
        r = self.client.get("/api/tools/metadata", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return [c for c in r.json()["components"] if c.get("kind") == "workflow"]

    def test_a_built_gui_workflow_loads_from_tool_builds(self):
        wf_id = add_workflow()
        _, expose = add_build(wf_id)
        [c] = self._components()
        self.assertEqual((c["id"], c["name"], c["expose"], c["label"]), (wf_id, "tool_volview", expose, "GUI"))
        self.assertTrue(c["path"].startswith(f"/tool-builds/{expose}/primary/my-app.umd.js?v="), c["path"])

    def test_an_approved_gui_workflow_loads_from_its_platform_tool_dataset(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        approve(wf_id, build_id)
        [c] = self._components()
        self.assertEqual(c["uuid"], "tool-v")
        self.assertTrue(c["path"].startswith("/tools/tool-v/primary/my-app.umd.js?v="), c["path"])

    def test_the_approved_build_wins_over_a_newer_one(self):
        wf_id = add_workflow()
        build_id, approved_expose = add_build(wf_id, age_minutes=10)
        approve(wf_id, build_id)
        add_build(wf_id)
        [c] = self._components()
        self.assertEqual(c["expose"], approved_expose)

    def test_an_approved_build_without_its_tool_dataset_falls_back_to_tool_builds(self):
        wf_id = add_workflow()
        build_id, expose = add_build(wf_id)
        approve(wf_id, build_id, tool_uuid=None)
        [c] = self._components()
        self.assertTrue(c["path"].startswith(f"/tool-builds/{expose}/"), c["path"])

    def test_a_build_with_nowhere_to_load_from_is_skipped(self):
        wf_id = add_workflow()
        add_build(wf_id, bundle_path=None)
        self.assertEqual(self._components(), [])

    def test_builds_without_a_bundle_and_other_types_are_not_listed(self):
        add_build(add_workflow(), bundle=False)
        add_build(add_workflow(workflow_type="script"), bundle=False)
        self.assertEqual(self._components(), [])


class BuildLogsTest(unittest.TestCase):
    def test_a_workflow_build_log_is_served_after_it_left_memory(self):
        client = make_hub_client()
        build_id, _ = add_build(add_workflow(), build_logs="npm run build:plugin\nok")
        r = client.get(f"/api/tools/builds/{build_id}/logs", headers=bearer("viewer"))
        self.assertEqual((r.status_code, r.text), (200, "npm run build:plugin\nok"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_gui_tools -v'`. Expected: the metadata tests fail on `[c] = []` (not enough values to unpack), and the logs test gets 404.

- [ ] **Step 4: Implement the helpers.** In `workflow_tool_utils.py`, which already imports `Workflow`, `WorkflowBuild`, `PluginDeployment` and `BuildStatus`, append:

```python
def served_workflow_build(db: Session, workflow: Workflow) -> Optional[WorkflowBuild]:
    """The build whose gui tool the Tool Hub launches and deploys: the approved one, else the latest with a bundle."""
    builds = (db.query(WorkflowBuild)
              .filter(WorkflowBuild.workflow_id == workflow.id,
                      WorkflowBuild.status == BuildStatus.COMPLETED.value,
                      WorkflowBuild.tool_name.isnot(None))
              .order_by(WorkflowBuild.created_at.desc())
              .all())
    approved = next((b for b in builds if workflow.uuid and b.dataset_uuid == workflow.uuid), None)
    return approved or (builds[0] if builds else None)


def workflow_bundle_path(build: WorkflowBuild) -> Optional[str]:
    """Where the launcher loads a gui workflow's bundle: its platform tool dataset once approved, else tool-builds."""
    ts = int(build.created_at.timestamp()) if build.created_at else 0
    if build.tool_dataset_uuid:
        return f"/tools/{build.tool_dataset_uuid}/primary/my-app.umd.js?v={ts}"
    if build.bundle_path:
        return f"/{build.bundle_path}/my-app.umd.js?v={ts}"
    return None


def latest_deployment(db: Session, build: WorkflowBuild) -> Optional[PluginDeployment]:
    return (db.query(PluginDeployment)
            .filter(PluginDeployment.workflow_build_id == build.build_id)
            .order_by(PluginDeployment.created_at.desc())
            .first())
```

- [ ] **Step 5: Implement metadata and logs.** In `workflow_tool_plugin.py`:
  - Add `Workflow, WorkflowBuild,` to the `app.models.db_model` import.
  - Add `served_workflow_build, workflow_bundle_path,` to the `app.utils.workflow_tool_utils` import.
  - In `get_metadata_json`, after the `for plugin in plugins:` loop and before `return JSONResponse(`, add:

```python
    # A gui SDS workflow's tool is launched like a GUI tool (built by build_workflow.py).
    for workflow in db.query(Workflow).filter(Workflow.workflow_type == "gui").all():
        build = served_workflow_build(db, workflow)
        path = workflow_bundle_path(build) if build else None
        if not path:
            continue
        components.append({
            "uuid": build.tool_dataset_uuid or "",
            "id": workflow.id,
            "kind": "workflow",
            "name": build.tool_name,
            "path": path,
            "expose": build.expose_name,
            "label": "GUI",
            "description": workflow.description or "",
            "version": workflow.version,
            "created_at": workflow.created_at.isoformat() if workflow.created_at else "",
            "author": workflow.author or "",
            "repository_url": workflow.repository_url,
            "is_local": False,
            "frontend_folder": workflow.frontend_folder,
            "has_backend": bool(workflow.has_backend),
            "backend_folder": workflow.backend_folder,
            "backend_deploy_command": None,
            "config": {},
        })
```

In `get_build_logs`, replace the record lookup line with:

```python
    rec = (db.query(PluginBuild).filter(PluginBuild.build_id == build_id).first()
           or db.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).first())
```

- [ ] **Step 6: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_gui_tools tests.test_tool_catalogue tests.test_log_stream -v'`. Expected: OK.

- [ ] **Step 7: Checkpoint.** If the user has authorised commits, commit with `feat(portal): launch a gui workflow's tool from the Tool Hub's launcher metadata`.

---

### Task 8: `GET /api/workflow/gui-tools` lists gui workflow tools as Tool Hub rows

**Files:**
- Modify: `services/portal/backend/app/router/workflow_router.py`. Touch the imports, and add the endpoint right after `get_metadata_json` (about line 264), **before** `/{expose_name}/primary/{path:path}` and `/{workflow_id}`.
- Test: `services/portal/backend/tests/test_workflow_gui_tools.py`

**Interfaces:**
- Consumes: `served_workflow_build` and `latest_deployment` (Task 7).
- Produces: `GET /api/workflow/gui-tools`, which returns a list of snake_case rows. Their camelCased form matches the frontend's `ToolResponse`, plus `kind: "workflow"` and `workflow_name`.

- [ ] **Step 1: Write the failing tests.** Append this class to `tests/test_workflow_gui_tools.py`, before `if __name__`:

```python
class GuiToolListingTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def _rows(self):
        r = self.client.get("/api/workflow/gui-tools", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_a_built_gui_workflow_is_a_tool_row(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        [row] = self._rows()
        self.assertEqual({k: row[k] for k in ("id", "kind", "workflow_name", "name", "label", "status",
                                              "latest_build_id", "has_backend", "uuid")},
                         {"id": wf_id, "kind": "workflow", "workflow_name": "workflow_volview", "name": "tool_volview",
                          "label": "GUI", "status": "completed", "latest_build_id": build_id,
                          "has_backend": False, "uuid": None})

    def test_an_approved_row_carries_its_platform_tool_dataset(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        approve(wf_id, build_id)
        self.assertEqual(self._rows()[0]["uuid"], "tool-v")

    def test_a_building_workflow_is_listed_while_it_builds(self):
        add_build(add_workflow(), bundle=False, status=BuildStatus.BUILDING.value)
        self.assertEqual([r["status"] for r in self._rows()], ["building"])

    def test_workflows_never_built_or_built_without_a_bundle_are_not_listed(self):
        add_workflow()
        add_build(add_workflow(), bundle=False)
        add_build(add_workflow(workflow_type="script"))
        self.assertEqual(self._rows(), [])

    def test_a_row_shows_the_latest_deploy_of_the_served_build(self):
        wf_id = add_workflow(has_backend=True)
        build_id, _ = add_build(wf_id)
        with SessionLocal() as db:
            db.add(PluginDeployment(workflow_build_id=build_id, deploy_id="d1", status="completed", up=True))
            db.commit()
        [row] = self._rows()
        self.assertEqual((row["latest_deploy_id"], row["deploy_status"], row["has_backend"]), ("d1", "completed", True))
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_gui_tools -v'`. Expected: the listing tests get a 404 or 422 from `GET /api/workflow/{workflow_id}`, which treats `gui-tools` as a workflow id.

- [ ] **Step 3: Implement.** In `workflow_router.py`, change the utils import to `from app.utils.workflow_tool_utils import get_build_record_or_404, get_latest_build_record, served_workflow_build, latest_deployment`, and add after `get_metadata_json`:

```python
def _iso(value):
    return value.isoformat() if value else None


@router.get("/gui-tools")
async def get_gui_tools(db: Session = Depends(get_db)):
    """gui SDS workflows' tools as Tool Hub rows (the frontend's ToolResponse, plus kind and workflow_name)."""
    rows = []
    for workflow in db.query(Workflow).filter(Workflow.workflow_type == "gui", Workflow.is_sds.is_(True)).all():
        latest = (db.query(WorkflowBuild).filter(WorkflowBuild.workflow_id == workflow.id)
                  .order_by(WorkflowBuild.created_at.desc()).first())
        served = served_workflow_build(db, workflow)
        if latest is None or (served is None and latest.status == BuildStatus.COMPLETED.value):
            continue  # never built, or built before gui workflows built their tool (no bundle)
        deploy = latest_deployment(db, served) if served else None
        rows.append({
            "id": workflow.id,
            "kind": "workflow",
            "workflow_name": workflow.name,
            "name": (served or latest).tool_name or workflow.name,
            "label": "GUI",
            "version": workflow.version,
            "description": workflow.description,
            "author": workflow.author,
            "repository_url": workflow.repository_url,
            "frontend_folder": workflow.frontend_folder or "",
            "frontend_build_command": workflow.frontend_build_command or "",
            "has_backend": bool(workflow.has_backend),
            "backend_folder": workflow.backend_folder,
            "backend_deploy_command": "",
            "tool_metadata": {},
            "status": latest.status,
            "latest_build_id": latest.build_id,
            "latest_build_created_at": _iso(latest.created_at),
            "latest_build_updated_at": _iso(latest.updated_at),
            "uuid": served.tool_dataset_uuid if served else None,
            "deploy_status": deploy.status if deploy else None,
            "latest_deploy_id": deploy.deploy_id if deploy else None,
            "latest_deploy_created_at": _iso(deploy.created_at) if deploy else None,
            "latest_deploy_updated_at": _iso(deploy.updated_at) if deploy else None,
            "created_at": _iso(workflow.created_at),
            "updated_at": _iso(workflow.updated_at),
        })
    return rows
```

- [ ] **Step 4: Run the tests and check that they pass.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_gui_tools tests.test_workflow_auth -v'`. Expected: OK.

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit with `feat(portal): list gui workflow tools for the Tool Hub`.

---

### Task 9: Deploy a gui workflow tool's backend; clean up on rebuild and delete

These query `PluginDeployment` without a join to `Plugin`, so they already cover workflow deployment rows and need no change:
- Compose up/down: `GET /api/tools/plugin/deploy/{deploy_id}/execute`
- the check: `GET /api/tools/check/deploy/{deploy_id}/`
- the deploy log endpoints
- `main.py`'s startup reconcile and shutdown cleanup

**Files:**
- Modify: `services/portal/backend/app/utils/workflow_tool_utils.py`. Move `_parse_docker_compose_routing` here as `parse_docker_compose_routing`; extract `run_deployment`; add `shut_down_workflow_backends`.
- Modify: `services/portal/backend/app/router/workflow_tool_plugin.py`. Delete `_parse_docker_compose_routing` (lines 65-108), and make `get_plugin_deploy` (about 582-679) use `run_deployment`.
- Modify: `services/portal/backend/app/router/workflow_router.py`. Touch the imports, add `ADMIN` and `deployer`, the deploy endpoint, the shutdown in `_trigger_workflow_build`, and the shutdown plus bundle cleanup in `delete_plugin`.
- Test: `services/portal/backend/tests/test_workflow_gui_tools.py`

**Interfaces:**
- Consumes: `served_workflow_build` (Task 7) and `PluginDeployment.workflow_build_id` (Task 2).
- Produces:
  - `parse_docker_compose_routing(backend_dir: Path, expose_name: str = "") -> dict`
  - `run_deployment(deployer: PluginDeployer, deploy_id: str, deploy_dict: dict) -> None`, where `deploy_dict` has the keys `expose_name`, `dataset_path` and `backend_folder`
  - `shut_down_workflow_backends(workflow_id: str, deployer: PluginDeployer) -> None`
  - `GET /api/workflow/{workflow_id}/deploy` (admin), which returns `{build_id, deploy_id, status, message}`

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_workflow_gui_tools.py`, before `if __name__`. Add `from app.router import workflow_router` and `from tests.test_tool_catalogue import FakeBucket` to the imports at the top.

```python
class WorkflowToolDeployTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()
        self.deployed, self.shut_down = [], []
        self._orig = (workflow_router.run_deployment, workflow_router.shut_down_workflow_backends,
                      workflow_router.execute_build_in_background, workflow_router.minio,
                      workflow_router.get_minio_client)
        workflow_router.run_deployment = lambda deployer, deploy_id, d: self.deployed.append((deploy_id, d))
        workflow_router.shut_down_workflow_backends = lambda wf_id, deployer: self.shut_down.append(wf_id)
        workflow_router.execute_build_in_background = lambda **kwargs: None

    def tearDown(self):
        (workflow_router.run_deployment, workflow_router.shut_down_workflow_backends,
         workflow_router.execute_build_in_background, workflow_router.minio,
         workflow_router.get_minio_client) = self._orig

    def _deploy(self, wf_id, token="admin"):
        return self.client.get(f"/api/workflow/{wf_id}/deploy", headers=bearer(token))

    def test_only_admins_deploy(self):
        wf_id = add_workflow(has_backend=True)
        add_build(wf_id)
        self.assertEqual(self._deploy(wf_id, token="researcher").status_code, 403)

    def test_deploy_runs_the_served_build_backend(self):
        wf_id = add_workflow(has_backend=True)
        build_id, expose = add_build(wf_id)
        r = self._deploy(wf_id)
        self.assertEqual(r.status_code, 200, r.text)
        [(deploy_id, d)] = self.deployed
        self.assertEqual((r.json()["deploy_id"], r.json()["build_id"]), (deploy_id, build_id))
        self.assertEqual(d, {"expose_name": expose, "dataset_path": f"/portal_workspace/workflows/{expose}",
                             "backend_folder": "backend"})
        with SessionLocal() as db:
            row = db.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).one()
            self.assertEqual((row.workflow_build_id, row.build_id, row.plugin_id), (build_id, None, None))

    def test_deploy_uses_the_approved_build(self):
        wf_id = add_workflow(has_backend=True)
        build_id, approved_expose = add_build(wf_id, age_minutes=10)
        approve(wf_id, build_id)
        add_build(wf_id)
        self._deploy(wf_id)
        self.assertEqual(self.deployed[0][1]["expose_name"], approved_expose)

    def test_a_workflow_without_a_backend_or_a_bundle_is_not_deployed(self):
        no_backend = add_workflow()
        add_build(no_backend)
        unbuilt = add_workflow(has_backend=True)
        self.assertEqual(self._deploy(no_backend).status_code, 400)
        self.assertEqual(self._deploy(unbuilt).status_code, 400)
        self.assertEqual(self.deployed, [])

    def test_a_rebuild_shuts_down_the_backend_first(self):
        with_backend, without = add_workflow(has_backend=True), add_workflow()
        for wf_id in (with_backend, without):
            r = self.client.post(f"/api/workflow/{wf_id}/build", json={}, headers=bearer("researcher"))
            self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.shut_down, [with_backend])

    def test_delete_shuts_down_the_backend_and_removes_the_bundle(self):
        wf_id = add_workflow(has_backend=True)
        build_id, expose = add_build(wf_id)
        with SessionLocal() as db:
            db.add(PluginDeployment(workflow_build_id=build_id, deploy_id="d1", status="completed"))
            db.commit()
        tool_builds = FakeBucket([f"{expose}/primary/my-app.umd.js", "other_ab12/primary/my-app.umd.js"])
        workflow_router.minio = FakeBucket()
        workflow_router.get_minio_client = lambda bucket=None: tool_builds

        r = self.client.delete(f"/api/workflow/{wf_id}", headers=bearer("researcher"))

        self.assertTrue(r.json()["status"], r.text)
        self.assertEqual(self.shut_down, [wf_id])
        self.assertEqual(tool_builds.deleted, [f"{expose}/primary/my-app.umd.js"])
        with SessionLocal() as db:
            self.assertEqual(db.query(PluginDeployment).count(), 0)
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `... -c '/app/.venv/bin/python -m unittest tests.test_workflow_gui_tools -v'`. Expected: `setUp` errors with `AttributeError: module 'app.router.workflow_router' has no attribute 'run_deployment'`.

- [ ] **Step 3: Move and extract the shared deploy code.** In `workflow_tool_utils.py`:
  - Add the imports `import yaml`, `from datetime import datetime`, `from pathlib import Path` and `from app.builder.log_stream import log_registry, bind_thread_job, unbind_thread_job`.
  - Move `_parse_docker_compose_routing` from `workflow_tool_plugin.py` here **unchanged**, renamed to `parse_docker_compose_routing`.
  - Then add the code below. It is the tool router's former inner `run_deploy`, with `latest_build.expose_name` replaced by `deploy_dict["expose_name"]`:

```python
def run_deployment(deployer: PluginDeployer, deploy_id: str, deploy_dict: dict) -> None:
    """Run a deployment row's backend (docker compose) and route /plugin/<expose> to it: a tool's or a gui workflow's.

    ``deploy_dict`` holds ``expose_name``, ``dataset_path`` and ``backend_folder`` (PluginDeployer.deploy).
    """
    job_key = f"deploy:{deploy_id}"
    try:
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(
                PluginDeployment.deploy_id == deploy_id).first()  # type: ignore
            if deploy_record:
                deploy_record.status = DeployStatus.DEPLOYING.value
                session.commit()
        log_registry.open(job_key)
        # Bind this thread so every deploy log record (compose up output AND
        # the surrounding orchestration steps) streams into the console.
        bind_thread_job(job_key)
        logger.info("Starting plugin deployment...")
        try:
            result = deployer.deploy(deploy_dict)
        finally:
            unbind_thread_job()
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
            if deploy_record:
                if result["success"]:
                    log_registry.finish(job_key, "completed")
                    deploy_record.status = DeployStatus.COMPLETED.value
                    deploy_record.source_path = result["backend_dir"]
                    deploy_record.up = True

                    # Generate nginx config for this plugin
                    expose_name = deploy_dict["expose_name"]
                    backend_dir = Path(result["backend_dir"])
                    routing = parse_docker_compose_routing(backend_dir, expose_name)
                    if routing and expose_name:
                        route_prefix = f"/plugin/{expose_name}"
                        deploy_record.route_prefix = route_prefix
                        deploy_record.internal_host = routing["internal_host"]
                        deploy_record.internal_port = routing["internal_port"]
                        deploy_record.has_websocket = routing.get("has_websocket", True)
                        deployer.generate_nginx_conf(
                            expose_name=expose_name,
                            internal_host=routing["internal_host"],
                            internal_port=routing["internal_port"],
                            has_websocket=routing.get("has_websocket", True),
                        )
                        deployer.reload_nginx()
                        logger.info(f"Nginx config generated for plugin {expose_name}")
                else:
                    log_registry.finish(job_key, "failed")
                    deploy_record.status = BuildStatus.FAILED.value
                    deploy_record.error = result["error_message"]

                deploy_record.updated_at = datetime.now()
                session.commit()
    except Exception as e:
        log_registry.finish(job_key, "failed")
        logger.error(f"Deploy failed: {e}")
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
            if deploy_record:
                deploy_record.status = DeployStatus.FAILED.value
                deploy_record.error_message = str(e)
                deploy_record.updated_at = datetime.now()
                session.commit()
```

(The `deploy_record.error` and `.error_message` lines are the existing out-of-scope bug. Move them as they are.)

Refactor `shuttle_down_deployed_backend`, and add the workflow variant:

```python
def _shut_down(deploys, deployer: PluginDeployer) -> None:
    for deployment in deploys:
        logger.info("Start to shuttle down the deployment {}".format(deployment.id))
        expose_name = deployment.route_prefix.replace("/plugin/", "") if deployment.route_prefix else ""
        deploy_dict = {
            "backend_dir": deployment.source_path,
            "expose_name": expose_name,
        }
        logger.info("the deployment is {}".format(deploy_dict))
        deployer.delete(deploy_dict)


def shuttle_down_deployed_backend(plugin_id: str, deployer: PluginDeployer):
    try:
        with SessionLocal() as session:
            _shut_down(session.query(PluginDeployment).filter(PluginDeployment.plugin_id == plugin_id).all(), deployer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def shut_down_workflow_backends(workflow_id: str, deployer: PluginDeployer):
    """Stop every backend deployed from a gui workflow's builds (before a rebuild or a delete)."""
    try:
        with SessionLocal() as session:
            deploys = (session.query(PluginDeployment)
                       .join(WorkflowBuild, PluginDeployment.workflow_build_id == WorkflowBuild.build_id)
                       .filter(WorkflowBuild.workflow_id == workflow_id).all())
            _shut_down(deploys, deployer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Make the tool router use it.** In `workflow_tool_plugin.py`:
  - Delete the `_parse_docker_compose_routing` function. Its only caller was `run_deploy`, which now lives in the utils module.
  - Add `run_deployment` to the `app.utils.workflow_tool_utils` import.
  - In `get_plugin_deploy`, delete the inner `def run_deploy(): …` and replace the scheduling block with:

```python
    if background_tasks:
        background_tasks.add_task(run_deployment, deployer, deploy_id, plugin_dict)
    else:
        thread = threading.Thread(target=run_deployment, args=(deployer, deploy_id, plugin_dict))
        thread.start()
```

`plugin_dict` already holds `expose_name`, `dataset_path` and `backend_folder`.

- [ ] **Step 5: Add the workflow deploy endpoint, rebuild shutdown and delete cleanup.** In `workflow_router.py`:
  - Add `import threading`.
  - Add `DeployStatus, PluginDeployment,` to the `app.models.db_model` import.
  - Add `from app.builder.deploy_tool import PluginDeployer`.
  - Extend the utils import with `run_deployment, shut_down_workflow_backends`.
  - After `WRITER = …`, add:

```python
ADMIN = Depends(require_any_role("admin"))  # running plugin backends (docker on the host socket) needs admin
deployer = PluginDeployer()
```

Add the endpoint after `get_gui_tools`:

```python
@router.get("/{workflow_id}/deploy", dependencies=[ADMIN])
async def deploy_workflow_tool(workflow_id: str, background_tasks: BackgroundTasks = None,
                               db: Session = Depends(get_db)):
    """Deploy a gui workflow tool's backend, as for GUI tools, from the build whose bundle the Tool Hub launches."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    build = served_workflow_build(db, workflow)
    if not workflow.has_backend or build is None:
        raise HTTPException(status_code=400, detail="This workflow has no built gui tool with a backend")
    deploy_dict = {"expose_name": build.expose_name, "dataset_path": build.dataset_path,
                   "backend_folder": workflow.backend_folder}
    deploy_id = str(uuid.uuid4())
    db.add(PluginDeployment(workflow_build_id=build.build_id, deploy_id=deploy_id, status=DeployStatus.PENDING.value))
    db.commit()
    if background_tasks:
        background_tasks.add_task(run_deployment, deployer, deploy_id, deploy_dict)
    else:
        threading.Thread(target=run_deployment, args=(deployer, deploy_id, deploy_dict)).start()
    return {"build_id": build.build_id, "deploy_id": deploy_id, "status": DeployStatus.PENDING.value,
            "message": "Deploy started in background"}
```

In `_trigger_workflow_build`, right after the 404 check:

```python
    if workflow.has_backend:
        shut_down_workflow_backends(workflow.id, deployer)  # the rebuild gets a new expose name and route
```

In `delete_plugin`, right before `builds = db.query(WorkflowBuild)…`:

```python
            shut_down_workflow_backends(workflow.id, deployer)
```

…and inside the `for build in builds:` loop, before `if build.s3_path is not None:`:

```python
                if build.bundle_path:  # a gui workflow's tool bundle, served from tool-builds before approval
                    bucket, prefix = build.bundle_path.split("/", 1)
                    tool_builds = get_minio_client(bucket)
                    for obj in tool_builds.list_objects(prefix=prefix):
                        tool_builds.delete_object(obj["Key"])
```

- [ ] **Step 6: Run the full backend suite and check that it passes.** Run `docker run --rm --network none -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-portal-backend -c '/app/.venv/bin/python -m unittest discover -s tests -t .'`. Expected: OK. That's the 152-test baseline plus this plan's new tests, with the same 9 skipped.

- [ ] **Step 7: Checkpoint.** If the user has authorised commits, commit with `feat(portal): deploy a gui workflow tool's backend and clean it up with its workflow`.

---

### Task 10: The frontend Tool Hub lists gui workflow tools

Before starting, record the frontend baseline: run the Node 20 `yarn build` command from the Global constraints and note the `error TS` count.

**Files:**
- Modify: `services/portal/frontend/src/models/types.ts` (`ToolResponse`, about lines 149-184)
- Modify: `services/portal/frontend/src/bootstrap/tool_api.ts` (`useToolHub`, about 120-129; add two functions)
- Create: `services/portal/frontend/src/views/upload-dataset/components/__tests__/tool_hub.spec.ts`

**Interfaces:**
- Consumes: `GET /api/workflow/gui-tools` (Task 8) and `GET /api/workflow/{id}/deploy` (Task 9).
- Produces:
  - the `ToolResponse.kind?: "workflow"` and `ToolResponse.workflowName?: string` fields
  - `useWorkflowGuiTools(): Promise<ToolResponse[]>`
  - `useDeployWorkflowTool(workflowId: string)`
  - `useToolHub()` returns portal tools, then workflow tools, then platform-only tools; a platform tool's dataset is hidden when a workflow tool row already carries its uuid

- [ ] **Step 1: Write the failing test.**

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, dtGet, fetchWithLatestBuild } = vi.hoisted(() => ({
  get: vi.fn(), dtGet: vi.fn(), fetchWithLatestBuild: vi.fn(),
}));
vi.mock("@/bootstrap/http", () => ({ default: { get }, dtApi: { get: dtGet } }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(), fetchWithLatestBuild }));
vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: vi.fn(), getKeycloak: vi.fn() }));

import { useToolHub } from "@/bootstrap/tool_api";

const kindOf = (t: any) => t.kind ?? (t.platformOnly ? "platform" : "portal");

describe("useToolHub", () => {
  beforeEach(() => {
    fetchWithLatestBuild.mockResolvedValue([{ id: "t1", uuid: "tool-a", name: "portal tool" }]);
    dtGet.mockResolvedValue({ datasets: [
      { datasetUuid: "tool-v", datasetName: "tool_volview", toolType: "gui" },
      { datasetUuid: "tool-x", datasetName: "tool_other", toolType: "script" },
    ] });
  });

  it("lists a gui workflow's tool once, instead of its platform dataset", async () => {
    get.mockResolvedValue([{ id: "w1", kind: "workflow", uuid: "tool-v", name: "tool_volview" }]);

    const hub = await useToolHub();

    expect(get).toHaveBeenCalledWith("/workflow/gui-tools");
    expect(hub.map((t) => [t.name, kindOf(t)])).toEqual([
      ["portal tool", "portal"], ["tool_volview", "workflow"], ["tool_other", "platform"],
    ]);
  });

  it("still lists the other tools when the workflow tools can't be fetched", async () => {
    get.mockRejectedValue(new Error("502"));

    const hub = await useToolHub();

    expect(hub.map((t) => t.name)).toEqual(["portal tool", "tool_volview", "tool_other"]);
  });
});
```

- [ ] **Step 2: Run the test and check that it fails.** Run `npx vitest run src/views/upload-dataset/components/__tests__/tool_hub.spec.ts`. Expected: the first test fails because `get` was not called and `tool_volview` is listed as `platform`.

- [ ] **Step 3: Implement.** In `types.ts`, add these to `ToolResponse` after `platformOnly`:

```ts
    // A gui SDS workflow's tool (GET /api/workflow/gui-tools): built, approved and deleted with its workflow.
    kind?: "workflow"
    workflowName?: string
```

In `tool_api.ts`, replace `useToolHub` and add the two functions:

```ts
/** gui SDS workflows' tools as Tool Hub rows; their workflow builds them (GET /api/workflow/gui-tools). */
export async function useWorkflowGuiTools(): Promise<ToolResponse[]> {
  return http.get<ToolResponse[]>("/workflow/gui-tools");
}

/** The Tool Hub: portal tools, gui workflows' tools, then platform-only tools (each source can fail on its own). */
export async function useToolHub(): Promise<ToolResponse[]> {
  const [tools, workflowTools] = await Promise.all([
    useWorkflowTools(),
    useWorkflowGuiTools().catch((err) => {
      console.warn("Failed to list gui workflow tools:", err);
      return [] as ToolResponse[];
    }),
  ]);
  const known = new Set([...tools, ...workflowTools].map((t) => t.uuid).filter((u): u is string => !!u));
  const platform = await usePlatformTools(known).catch((err) => {
    console.warn("Failed to list platform tools:", err);
    return [] as ToolResponse[];
  });
  return [...tools, ...workflowTools, ...platform];
}

export async function useDeployWorkflowTool(workflowId: string) {
  return http.get(`/workflow/${workflowId}/deploy`);
}
```

- [ ] **Step 4: Run the tests and check that they pass.** Run `npx vitest run`. Expected: all pass (50 + 2).

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit with `feat(portal): list gui workflow tools in the Tool Hub`.

---

### Task 11: ToolCard and the Tool Hub handle a gui workflow's tool

**Files:**
- Modify: `services/portal/frontend/src/views/upload-dataset/components/ToolCard.vue` (meta chips, about lines 24-25; `menuItems`, about 124-145; `onDeploy`, about 202-205)
- Modify: `services/portal/frontend/src/views/upload-dataset/workflow-tool/ToolsOverallView.vue` (the `@deploy` binding, about line 43; imports, about 76-83; `handleDeploy`, about 257-270)
- Test: `services/portal/frontend/src/views/upload-dataset/components/__tests__/cards.spec.ts`

**Interfaces:**
- Consumes: `ToolResponse.kind` and `workflowName`, plus `useDeployWorkflowTool` and `useWorkflowGuiTools` (Task 10).
- Produces: ToolCard emits `deploy` as `(id, kind)`.

- [ ] **Step 1: Write the failing tests.** In `cards.spec.ts`, add after `PLATFORM_TOOL`:

```ts
const WORKFLOW_TOOL = { ...TOOL, id: "w1", label: "GUI", kind: "workflow", workflowName: "workflow_volview",
  name: "tool_volview", uuid: "tool-v" };
```

…and add these tests to `describe("ToolCard", …)`:

```ts
  it("tags a gui workflow's tool with its workflow, which owns rebuild, approval and delete", () => {
    const w = mount(ToolCard, { props: { tool: WORKFLOW_TOOL as any }, global: { plugins } });

    expect(w.text()).toContain("from workflow workflow_volview");
    expect(w.text()).not.toContain("in platform");
    expect(menu(w)).toEqual([]);
    const launch = w.findAll("button").find((b) => b.text().includes("Launch"))!;
    expect(launch.attributes("disabled")).toBeUndefined();
  });

  it("runs a workflow tool's backend like a tool's", () => {
    const tool = { ...WORKFLOW_TOOL, hasBackend: true, deployStatus: "completed", latestDeployId: "d1", latestBuildId: "b1" };
    const w = mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Deploy backend", "Compose up", "Compose down", "View logs"]);
    menu(w)[0].onClick();
    expect(w.emitted("deploy")?.[0]).toEqual(["w1", "workflow"]);
  });
```

- [ ] **Step 2: Run the tests and check that they fail.** Run `npx vitest run src/views/upload-dataset/components/__tests__/cards.spec.ts`. Expected: both new tests fail. The text has no "from workflow", and the menu is the portal tool's ("Rebuild tool", …).

- [ ] **Step 3: Implement ToolCard.** Replace the two chip lines for `platformOnly` and `inPlatform` with:

```vue
      <span v-if="tool.kind === 'workflow'" class="aurora-chip" :style="{ '--chip': '#7fb2f0' }">
        from workflow {{ tool.workflowName }}
      </span>
      <span v-else-if="tool.platformOnly" class="aurora-chip" :style="{ '--chip': '#9fb4bf' }">platform upload</span>
      <span v-else-if="inPlatform" class="aurora-chip" :style="{ '--chip': '#6fd49a' }">in platform</span>
```

At the top of the `menuItems` computed, before the `platformOnly` branch, add:

```ts
  // A gui workflow's tool: its workflow (Workflow Hub) rebuilds, approves and deletes it; only its backend runs here.
  if (tool.value.kind === 'workflow') {
    const items: UCardMenuItem[] = []
    if (tool.value.hasBackend) items.push({ label: 'Deploy backend', icon: 'mdi-server-network', onClick: onDeploy })
    if (tool.value.deployStatus === 'completed') {
      items.push({ label: 'Compose up', icon: 'mdi-play-circle-outline', onClick: onDockerComposeUp })
      items.push({ label: 'Compose down', icon: 'mdi-stop-circle-outline', onClick: onDockerComposeDown })
    }
    if (hasViewLogs.value) items.push({ label: 'View logs', icon: 'mdi-console-line', onClick: onViewLogs })
    return items
  }
```

In `onDeploy`, change `emit("deploy", tool.value.id)` to `emit("deploy", tool.value.id, tool.value.kind)`.

- [ ] **Step 4: Implement ToolsOverallView.**
  - Change the binding to `@deploy="(id, kind) => handleDeploy(id, kind)"`.
  - Add `useWorkflowGuiTools` and `useDeployWorkflowTool` to the `@/bootstrap/tool_api` import.
  - Replace the first lines of `handleDeploy` with:

```ts
const handleDeploy = async (id: string, kind?: string) => {
  const isWorkflow = kind === 'workflow';
  const res = (isWorkflow ? await useDeployWorkflowTool(id) : await useDeployTool(id)) as any;
  const deployId: string = res?.deployId ?? res?.deploy_id ?? '';
  // Resolve tool name for the console title
  let toolName = id;
  try {
    const items = (isWorkflow ? await useWorkflowGuiTools() : await useWorkflowTools()) as ToolResponse[];
    toolName = items.find((t) => t.id === id)?.name ?? id;
  } catch { /* fallback to id */ }
```

Keep the rest of the function (opening the console, refresh) as it is.

- [ ] **Step 5: Run the tests and check that they pass.** Run `npx vitest run`. Expected: all pass.

- [ ] **Step 6: Checkpoint.** If the user has authorised commits, commit with `feat(portal): show and run a gui workflow's tool on its Tool Hub card`.

---

### Task 12: The Workflow wizard asks a gui SDS workflow how to build its tool

**Files:**
- Modify: `services/portal/frontend/src/models/types.ts` (`WorkflowInformationStep`, about lines 277-286)
- Modify: `services/portal/frontend/src/views/upload-dataset/components/BaseInformationStep.vue`. Touch the GUI block's `v-if` (line 78), add a computed, change `validate()` (about 375-379), and change the workflow payload in `handleSubmit` (about 453-465).
- Test: `services/portal/frontend/src/views/upload-dataset/components/__tests__/BaseInformationStep.spec.ts`

**Interfaces:**
- Consumes: `POST /api/workflow/create`, which accepts the GUI fields (Task 3).
- Produces: the workflow create payload carries `hasBackend`, `frontendFolder`, `backendFolder` and `frontendBuildCommand`, but only for a gui SDS workflow.

- [ ] **Step 1: Make the repo-info mock controllable.** In `BaseInformationStep.spec.ts`, replace the `useGithubRepoInfo` mock with:

```ts
const repo = vi.hoisted(() => ({ info: null as any }));
vi.mock("@/composables/useGithubRepoInfo", async () => {
  const { ref } = await import("vue");
  repo.info = ref({ foldersInRoot: [], isSds: false, cwlExists: false });
  return { useGitRepoInfo: () => ({ info: repo.info, refresh: vi.fn() }) };
});
```

Add `beforeEach` to the vitest import, and at the top of the `describe` add `beforeEach(() => { repo.info.value = { foldersInRoot: [], isSds: false, cwlExists: false }; });`.

- [ ] **Step 2: Write the failing tests.** Add these to the `describe`:

```ts
  it("asks a gui SDS workflow how to build its tool, and sends it", async () => {
    repo.info.value = { foldersInRoot: ["backend", "frontend"], isSds: true, cwlExists: true };
    const w = mountStep("workflow");
    await pick(w, "gui");
    expect(w.text()).toContain("has backend?");

    Object.assign((w.vm as any).formData, { hasBackend: true, frontendFolder: "frontend", backendFolder: "backend" });
    expect(await submit(w)).toMatchObject({ workflowType: "gui", hasBackend: true, frontendFolder: "frontend",
      backendFolder: "backend", frontendBuildCommand: "npm run build:plugin" });
  });

  it("asks nothing more of a root-.cwl gui workflow", async () => {
    const w = mountStep("workflow");
    await pick(w, "gui");
    expect(w.text()).not.toContain("has backend?");
    expect(await submit(w)).not.toHaveProperty("hasBackend");
  });

  it("does not send a gui layout for another workflow type", async () => {
    repo.info.value = { foldersInRoot: ["frontend"], isSds: true, cwlExists: true };
    const w = mountStep("workflow");
    await pick(w, "script");
    expect(w.text()).not.toContain("has backend?");
    expect(await submit(w)).not.toHaveProperty("frontendBuildCommand");
  });
```

- [ ] **Step 3: Run the tests and check that they fail.** Run `npx vitest run src/views/upload-dataset/components/__tests__/BaseInformationStep.spec.ts`. Expected: the first test fails because "has backend?" is not shown.

- [ ] **Step 4: Implement.** In `types.ts`, add these to `WorkflowInformationStep`:

```ts
    // gui SDS workflows only: how to build the tool's frontend (folders under code/), as for GUI tools.
    hasBackend?: boolean;
    frontendFolder?: string;
    frontendBuildCommand?: string;
    backendFolder?: string;
```

In `BaseInformationStep.vue`:
- Change the GUI block to `<div v-if="(type === 'tool' && formData.label === 'GUI') || isGuiSdsWorkflow" class="w-100">`, and update its comment to `<!-- GUI tool, or a gui SDS workflow's tool: backend & folder fields -->`.
- After `const foldersInRoot = computed(...)`, add:

```ts
// A gui workflow packaged as SDS builds its one tool's frontend like a GUI tool (folders come from code/).
const isGuiSdsWorkflow = computed(() =>
  props.type === 'workflow' && formData.workflowType === 'gui' && !!repoInfo.value.isSds,
);
```

In `validate()`, replace the workflow branch with:

```ts
  if (props.type === 'workflow') {
    if (isGuiSdsWorkflow.value && formData.hasBackend) {
      const foldersOk = checkFolderInRoot(formData.frontendFolder ?? '') && checkFolderInRoot(formData.backendFolder ?? '');
      return valid && !!cwlCheck.value && foldersOk;
    }
    return valid && !!cwlCheck.value && !!formData.workflowType;
  }
```

In `handleSubmit`, add this after `workflowType: formData.workflowType,` in `workflowData`:

```ts
        ...(isGuiSdsWorkflow.value ? {
          hasBackend: formData.hasBackend,
          frontendFolder: formData.hasBackend ? formData.frontendFolder : undefined,
          backendFolder: formData.hasBackend ? formData.backendFolder : undefined,
          frontendBuildCommand: formData.frontendBuildCommand,
        } : {}),
```

- [ ] **Step 5: Run the tests, type check and build.** Run `npx vitest run`; expected: all pass. Then run the Node 20 `yarn build` command from the Global constraints; expected: the build succeeds with no more `error TS` than the baseline recorded before Task 10.

- [ ] **Step 6: Checkpoint.** If the user has authorised commits, commit with `feat(portal): ask a gui SDS workflow for its tool's frontend layout`.

---

### Task 13: Docs, artifacts and end-to-end verification

**Files:**
- Modify: `docs/artifacts/2026-10-02-155146-gui-workflow-tool-build/spec.md` (record the "Changes from the spec" above)
- Modify: `docs/decisions/2026-10-02-build-gui-workflow-tools.md` (Decision and Consequences: only SDS gui workflows build; existing ones build with the defaults on their next rebuild)
- Create: `docs/artifacts/2026-10-02-155146-gui-workflow-tool-build/walkthrough.md`
- Modify: `docs/artifacts/2026-10-02-155146-gui-workflow-tool-build/task.md`

- [ ] **Step 1: Update the spec and the ADR.**
  - In `spec.md`, add a "Changes during planning" section that lists items 1-5 from this plan's "Changes from the spec", and fix the two contradicting lines:
    - In section 1, "A gui workflow that isn't an SDS package fails its build" becomes "gui workflows that aren't SDS packages are unchanged".
    - The GUI fields are shown only for gui SDS sources.
  - In the ADR, add to Consequences: "Only gui **SDS** workflows build a frontend; root-`.cwl` gui workflows keep running separately built portal tools. A gui SDS workflow registered before this change builds with the defaults (no backend, `npm run build:plugin`) on its next rebuild."
  - Then sync: tick the matching item in `task.md`.

- [ ] **Step 2: Run every suite.** Run the portal backend command (full discovery), `npx vitest run`, the Node 20 `yarn build`, and `PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/test_workflow_assemble_tool.py tests/test_workflow_validation.py tests/test_datasets_workflows_api.py tests/test_dataset_uploads_workflows_api.py` (the API workflow tests that run offline; integration tests skip). Expected: all green, with no new `error TS`. Paste the summary lines into `walkthrough.md`.

- [ ] **Step 3: Manual end-to-end check on the local stack.** This needs the user's go-ahead, because it rebuilds and restarts the running services.
  1. `docker compose up -d --build portal-backend portal-frontend digitaltwins-api`, run from the directory holding the platform's compose file, with the same project name as today (`digitaltwins-platform`).
  2. Check the migration ran: from inside the portal-backend container, a read-only query lists `workflow_build_id` and the nullable `plugin_id` and `build_id` in `portal.plugin_deployments`, plus `ck_plugin_deployments_one_build`.
  3. In the Workflow Hub, **Rebuild** `workflow_volview`, and watch the npm output in the log console. (Risk: if VolView's own `build:plugin` fails, for example on itk-wasm assets, that is VolView packaging, not this feature. Report it with the log.)
  4. Check the Tool Hub: a `tool_volview` card tagged "from workflow workflow_volview" with Launch enabled. The old "platform upload" card stays until re-approval, because its tool uuid came from the old approval.
  5. Click Launch. VolView mounts, and the browser loads `/tool-builds/<expose>/primary/my-app.umd.js`.
  6. **Submit to approval** from the Workflow Hub card, and wait for completion. Then `curl -s -o /dev/null -w "%{http_code}" http://localhost/tools/<tool uuid>/primary/my-app.umd.js` prints `200`. The Tool Hub shows one `tool_volview` card, and Launch loads from `/tools/<tool uuid>/…`.

  Record the outcome, with any failure output, in `walkthrough.md`.

- [ ] **Step 4: Write `walkthrough.md`.** Cover what changed (per task, with file links), the test results, the end-to-end outcome, and the out-of-scope follow-ups (copied from the spec). Check for secrets (`gitleaks detect --source docs/artifacts/2026-10-02-155146-gui-workflow-tool-build --no-git`), then sync and tick `task.md`.

- [ ] **Step 5: Checkpoint.** If the user has authorised commits, commit the docs with `docs: record the gui workflow tool build decision, plan and walkthrough`. Per AGENTS.md, it goes in the same branch as the code.
