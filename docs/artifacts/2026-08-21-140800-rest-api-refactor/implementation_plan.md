# REST API Structure Refactor

Restructure the `digitaltwins-api` routers from verb-based organization (upload/download/delete/query) to resource-based organization (datasets/assays), standardize imports, add type annotations, replace `print()` with `logging`, and move Pydantic models to a `schemas/` module.

## Scope Summary (from interview)

| Decision | Outcome |
|---|---|
| Router organization | ✅ Restructure verb → resource-based |
| API versioning (`/api/v1`) | ❌ Skip (internal API) |
| Service layer extraction | ❌ Skip (helpers stay as private functions in router) |
| Response models | ❌ Skip (keep raw dicts) |
| Logging | ✅ Replace `print()` with `logging` |
| URL path consistency | ❌ Leave as-is (platform-wide dependency) |
| Import path consistency | ✅ Standardize to `from digitaltwins import ...` |
| Path parameter types | ✅ Add type annotations |
| Async conversion | ❌ Leave sync handlers |
| Error handling | ✅ Standardize pattern (lightweight) |
| Pydantic schemas | ✅ Move to `schemas/` module |
| Config consolidation | ❌ Keep `os.getenv()` as-is |
| CORS hardening | ❌ Leave as-is |

## Proposed Changes

### 1. Router Restructuring (verb → resource-based)

> [!IMPORTANT]
> This is the highest-impact change. All existing URL paths will remain the same — only the file organization changes.

**Current structure (by verb):**
```
app/routers/
├── query.py      # GET endpoints for programs, projects, investigations, studies, assays, workflows, tools, datasets
├── upload.py     # POST /dataset, POST /assay, POST /assays/{id}/workspace/dataset/upload
├── download.py   # GET /datasets/{uuid}/download
├── delete.py     # DELETE /datasets/{uuid}
├── assay.py      # POST /assays/{id}/run, GET /assays/{id}/workspace/dataset/download
├── auth.py       # POST /login, POST /token, GET /verify_token
└── health.py     # GET /health
```

**Proposed structure (by resource):**
```
app/routers/
├── datasets.py      # All dataset endpoints (list, get, samples, sample-types, upload, download, delete)
├── assays.py        # All assay endpoints (list, get, configure, run, workspace upload/download)
├── programs.py      # GET /programs, GET /programs/{id}
├── projects.py      # GET /projects, GET /projects/{id}
├── investigations.py # GET /investigations, GET /investigations/{id}
├── studies.py       # GET /studies, GET /studies/{id}
├── workflows.py     # GET /workflows, GET /workflows/{id}
├── tools.py         # GET /tools, GET /tools/{id}
├── auth.py          # POST /login, POST /token, GET /verify_token (unchanged)
└── health.py        # GET /health (unchanged)
```

#### [NEW] [datasets.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/datasets.py)
Consolidates all dataset endpoints from `query.py`, `upload.py`, `download.py`, and `delete.py`:
- `GET /datasets` — from query.py
- `GET /datasets/{dataset_uuid}` — from query.py
- `GET /datasets/{dataset_uuid}/sample-types` — from query.py
- `GET /datasets/{dataset_uuid}/samples` — from query.py
- `POST /dataset` — from upload.py
- `GET /datasets/{dataset_uuid}/download` — from download.py
- `DELETE /datasets/{dataset_uuid}` — from delete.py

#### [NEW] [assays.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)
Consolidates all assay endpoints from `query.py`, `upload.py`, and `assay.py`:
- `GET /assays` — from query.py
- `GET /assays/{assay_id}` — from query.py
- `POST /assay` — from upload.py (configure_assay)
- `POST /assays/{assay_id}/run` — from assay.py
- `GET /assays/{assay_id}/workspace/dataset/download` — from assay.py
- `POST /assays/{assay_id}/workspace/dataset/upload` — from upload.py

#### [NEW] [programs.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/programs.py)
- `GET /programs` — from query.py
- `GET /programs/{program_id}` — from query.py

#### [NEW] [projects.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/projects.py)
- `GET /projects` — from query.py
- `GET /projects/{project_id}` — from query.py

#### [NEW] [investigations.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/investigations.py)
- `GET /investigations` — from query.py
- `GET /investigations/{investigation_id}` — from query.py

#### [NEW] [studies.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/studies.py)
- `GET /studies` — from query.py
- `GET /studies/{study_id}` — from query.py

#### [NEW] [workflows.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/workflows.py)
- `GET /workflows` — from query.py
- `GET /workflows/{workflow_id}` — from query.py

#### [NEW] [tools.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/tools.py)
- `GET /tools` — from query.py
- `GET /tools/{tool_id}` — from query.py

#### [DELETE] [query.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/query.py)
All endpoints distributed to resource-specific modules. The `get_querier` dependency will move to a shared `dependencies.py`.

#### [DELETE] [upload.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/upload.py)
Dataset upload → `datasets.py`, assay configure/workspace upload → `assays.py`.

#### [DELETE] [download.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/download.py)
Dataset download → `datasets.py`.

#### [DELETE] [delete.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/delete.py)
Dataset delete → `datasets.py`.

#### [DELETE] [assay.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assay.py)
All endpoints and helper functions → `assays.py`.

#### [MODIFY] [main.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/main.py)
Update `include_router` calls to use new resource-based modules.

---

### 2. Shared Dependencies Module

#### [NEW] [dependencies.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/dependencies.py)
Extract shared dependency-injection factories used across multiple routers:
- `get_querier()` — currently in query.py, imported by assay.py and upload.py
- `get_uploader()` — currently in upload.py
- `get_downloader()` — currently in download.py
- `get_deleter()` — currently in delete.py

---

### ~~3. Service Layer Extraction~~ — SKIPPED

The workflow helper functions (`_fetch_assay_configs`, `_discover_samples`, `_create_sds_output`, etc.) will remain as private functions inside `assays.py` rather than being extracted to a separate `services/` module. Rationale: they are only used within the assay router, and the `src/digitaltwins/core/` layer already serves as the true service layer.

---

### 4. Pydantic Schemas Module

#### [NEW] [schemas/](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/schemas/)
Move `AssayInputModel`, `AssayOutputModel`, `AssayDataModel` from upload.py:

```
app/schemas/
├── __init__.py
└── assay.py      # AssayInputModel, AssayOutputModel, AssayDataModel
```

---

### 5. Import Path Standardization

All routers will use `from digitaltwins import Querier, Uploader, Deleter, Downloader` (top-level re-exports) instead of the mixed `src.digitaltwins.core.*` / `digitaltwins.*` patterns.

**Files affected:**
- ~~`delete.py`~~ → `datasets.py`: `from src.digitaltwins.core.deleter import Deleter` → `from digitaltwins import Deleter`
- ~~`download.py`~~ → `datasets.py`: `from src.digitaltwins.core.downloader import Downloader` → `from digitaltwins import Downloader`
- ~~`upload.py`~~ → `datasets.py`/`assays.py`: `from src.digitaltwins.core.uploader import Uploader` → `from digitaltwins import Uploader`
- For submodule imports (e.g. `digitaltwins.minio.uploader`), use `from digitaltwins.minio.uploader import ...` (drop `src.` prefix)

---

### 6. Path Parameter Type Annotations

Add explicit types to all path parameters in query endpoints. Currently untyped with `=None` defaults:

```diff
-def get_program(program_id=None, ...):
+def get_program(program_id: int, ...):

-def get_project(project_id=None, ...):
+def get_project(project_id: int, ...):

-def get_investigation(investigation_id=None, ...):
+def get_investigation(investigation_id: int, ...):

-def get_study(study_id=None, ...):
+def get_study(study_id: int, ...):

-def get_assay(assay_id=None, ...):
+def get_assay(assay_id: int, ...):

-def get_workflow(workflow_id=None, ...):
+def get_workflow(workflow_id: int, ...):

-def get_tool(tool_id=None, ...):
+def get_tool(tool_id: int, ...):
```

---

### 7. Logging Standardization

Replace all `print()` and `traceback.print_exc()` calls with Python's `logging` module:

```python
import logging
logger = logging.getLogger(__name__)

# Before
print(f"[auth] Basic auth failed, Keycloak response: {result}")
traceback.print_exc()

# After
logger.warning("Basic auth failed, Keycloak response: %s", result)
logger.exception("Unexpected error while processing dataset upload")
```

**Files affected:** `auth.py`, `assay.py` (→ `assays.py` + `assay_service.py`)

---

### 8. Error Handling Standardization

Apply the `delete.py` pattern (granular exception types → specific HTTP status codes) consistently:

```python
# Standard pattern:
try:
    result = service.do_thing(...)
except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
except (RuntimeError, ConnectionError) as exc:
    raise HTTPException(status_code=500/503, detail=...) from exc
except Exception as exc:
    logger.exception("Unexpected error")
    raise HTTPException(status_code=500, detail="Unexpected error...") from exc
```

Most affected: `assays.py` `configure_assay` handler (currently catches only bare `Exception`).

---

## Resolved: Path Parameter Types

All resource IDs will be typed as `int`. Evidence from the codebase:
- [Postgres schema](file:///home/clin864/Projects/digitaltwins-platform/services/postgres/digitaltwins_schema.sql#L45-L46): `assay_seek_id integer`, `workflow_seek_id integer`
- [SEEK querier](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/seek/querier.py#L80): uses `str(program_id)` for URL construction (i.e. expects numeric)
- `assay_id: int` is already used in existing routers
- `dataset_uuid` remains `str` (it's a UUID, not a SEEK ID)

---

## Verification Plan

### Automated Tests
```bash
# Verify the app starts without import errors
cd services/api/digitaltwins-api
python -c "from app.main import app; print('App created successfully')"
```

### Manual Verification
- Verify OpenAPI docs render correctly at `/docs` with all endpoints present
- Confirm all existing URL paths are preserved (no breaking changes)
- Verify tags group endpoints correctly in Swagger UI
