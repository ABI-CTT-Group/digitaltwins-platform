# REST API Refactor — Task Checklist

## Step 1: Shared Dependencies Module
- [x] Create `app/routers/dependencies.py` with `get_querier()`, `get_uploader()`, `get_downloader()`, `get_deleter()`
- [x] Sync artifacts

## Step 2: Pydantic Schemas Module
- [x] Create `app/schemas/__init__.py`
- [x] Create `app/schemas/assay.py` with `AssayInputModel`, `AssayOutputModel`, `AssayDataModel`
- [x] Sync artifacts

## Step 3: ~~Service Layer Extraction~~ — SKIPPED
- [x] ~~Create `app/services/__init__.py`~~ — not needed; helpers stay as private functions in `assays.py`
- [x] ~~Create `app/services/assay_service.py`~~ — reverted
- [x] Sync artifacts

## Step 4: Resource-Based Routers — Datasets
- [x] Create `app/routers/datasets.py` — consolidate endpoints from query.py, upload.py, download.py, delete.py
- [x] Sync artifacts

## Step 5: Resource-Based Routers — Assays
- [x] Create `app/routers/assays.py` — consolidate endpoints from query.py, upload.py, assay.py
- [x] Sync artifacts

## Step 6: Resource-Based Routers — Simple Resources
- [x] Create `app/routers/programs.py`
- [x] Create `app/routers/projects.py`
- [x] Create `app/routers/investigations.py`
- [x] Create `app/routers/studies.py`
- [x] Create `app/routers/workflows.py`
- [x] Create `app/routers/tools.py`
- [x] Sync artifacts

## Step 7: Update main.py & Router Init
- [x] Update `app/main.py` — replace old router imports with new resource-based modules
- [x] Update `app/routers/__init__.py`
- [x] Sync artifacts

## Step 8: Cleanup & Verification
- [x] Delete old files: `query.py`, `upload.py`, `download.py`, `delete.py`, `assay.py`
- [x] Run import verification: `python -c "from app.main import app"`
- [x] Sync artifacts
- [x] Create walkthrough.md
