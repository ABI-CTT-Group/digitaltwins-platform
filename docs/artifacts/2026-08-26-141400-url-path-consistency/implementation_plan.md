# URL Path Consistency Refactor

This plan addresses the technical debt identified in the REST API to ensure consistent, standard RESTful resource paths (plural nouns) across the platform.

Specifically, we are migrating:
- `POST /assay` to `POST /assays`
- `POST /dataset` to `POST /datasets`

## User Review Required

> [!WARNING]
> **Hard Cutover Selected**: Based on our discussion, we will be performing a hard cutover by directly renaming these endpoints without keeping backwards-compatible redirect aliases. This means all clients must be updated in tandem to prevent downtime or failures.

## Proposed Changes

### API Service (`services/api/digitaltwins-api`)

#### [MODIFY] [assays.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)
- Change `@router.post("/assay", ...)` to `@router.post("/assays", ...)`

#### [MODIFY] [datasets.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/datasets.py)
- Change `@router.post("/dataset", ...)` to `@router.post("/datasets", ...)`

#### [MODIFY] API Tests
- **[test_assay_api.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/tests/test_assay_api.py)**: Update `client.post("/assay", ...)` to `client.post("/assays", ...)`.
- **[test_upload_dataset_api.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/tests/test_upload_dataset_api.py)**: Update `client.post("/dataset", ...)` to `client.post("/datasets", ...)`.

---

### Portal Backend (`services/portal/DigitalTWINS-Portal/backend`)

#### [MODIFY] [dashboard.py](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/backend/app/router/dashboard.py)
- Line 373: Change `res = await client.post(f"/assay", assay_data)` to use `f"/assays"`.

---

### Jupyter Workspace (`my_workspace/pilot-2`)
The user Jupyter workspace notebooks contain hardcoded references to the `/dataset` URL.

#### [MODIFY] [cohort_selection.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%201%20-%20Cohort%20selection/cohort_selection.ipynb)
- Change `API_URL = f"{API_BASE_URL}/dataset"` to `API_URL = f"{API_BASE_URL}/datasets"`

#### [MODIFY] [upload_clinical_report.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/RATA/Assay%201%20-%20Clinical%20Report%20Curation/scripts/upload_clinical_report.ipynb)
- Change `API_URL = f"{API_BASE_URL}/dataset"` to `API_URL = f"{API_BASE_URL}/datasets"`

#### [MODIFY] [clinical_report_curation.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/RATA/Assay%201%20-%20Clinical%20Report%20Curation/clinical_report_curation.ipynb)
- Change `API_URL = f"{API_BASE_URL}/dataset"` to `API_URL = f"{API_BASE_URL}/datasets"`

#### [MODIFY] [mri_curation.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%202%20-%20MRI%20curation/mri_curation.ipynb)
- Change `API_URL = f"{API_BASE_URL}/dataset"` to `API_URL = f"{API_BASE_URL}/datasets"`

## Verification Plan

### Automated Tests
- Run `pytest` within `services/api/digitaltwins-api` to ensure that API tests pass and properly hit the renamed `/assays` and `/datasets` paths.
- Run `pytest` within `services/portal/DigitalTWINS-Portal/backend` to ensure no regression in portal endpoints.

### Manual Verification
- Start the API and verify the OpenAPI docs at `/docs` correctly reflect `POST /assays` and `POST /datasets`.
- Ensure there are no remaining usages of `"/assay"` (with quotes) or `"/dataset"` in the API and Portal codebases by doing a final global grep.
