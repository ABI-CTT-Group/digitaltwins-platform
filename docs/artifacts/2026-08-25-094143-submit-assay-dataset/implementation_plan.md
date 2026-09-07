# Upload Assay Workspace Dataset

This implementation plan outlines the changes required to enable submitting (uploading) assay workspace datasets from the Airflow/script-based Minio storage directly to the DigitalTWINS Platform via the portal UI.

## User Review Required

- Ensure the endpoints correctly align with the existing `dashboard.py` design patterns for routing API requests from the frontend to the `digitaltwins-api`.
- Confirm that handling long-running upload requests synchronously with a frontend loading spinner is acceptable, as this may time out on the reverse proxy (e.g. Nginx) if the upload takes very long.

## Open Questions
*Note for user: I checked the portal backend and there is no existing endpoint for submitting assay results or datasets in the `dashboard.py` router or any other router. So we will need to create the new proxy endpoint as proposed below.*

## Proposed Changes

---
### Backend API Updates (digitaltwins-api)

Rename the existing workspace dataset upload endpoint to better reflect its purpose of submitting assay execution results.

#### [MODIFY] [assays.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)
- Change the endpoint path from `POST /assays/{assay_id}/workspace/dataset/upload` to `POST /assays/{assay_id}/results/submit`.
- Rename the function from `upload_workspace_datasets` to `submit_assay_results`.

---
### Backend API Updates (Portal Backend)

Add a new proxy endpoint in the portal's backend to route the submit request to the `digitaltwins-api` endpoint.

#### [MODIFY] [dashboard.py](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/backend/app/router/dashboard.py)
- **Add endpoint `POST /assay-results-submit`**:
  - Accept `seek_id` via query parameters.
  - Forward the request to `client.post(f"/assays/{seek_id}/results/submit")` using the existing `DigitalTWINSAPIClient`.
  - Handle exceptions and return the standard JSON response from `digitaltwins-api`.

---
### Frontend Updates (Portal Frontend)

Integrate the new API endpoint with the existing `submit` workflow in `useAssayActions.ts`. Update wording to clearly state it's submitting "assay results".

#### [MODIFY] [dashboard_api.ts](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/frontend/src/bootstrap/dashboard_api.ts)
- Add function `useDashboardSubmitAssayResults(seekId: string)`.
- Use `http.post` to hit `/dashboard/assay-results-submit?seek_id={seekId}`.

#### [MODIFY] [useAssayActions.ts](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/frontend/src/composables/useAssayActions.ts)
- Implement `submit(seekId: string)`:
  1. Open `submitDialog.value = true`.
  2. Set `submitState.value = "waiting"`.
  3. Await `useDashboardSubmitAssayResults(seekId)`.
  4. On success, set `submitState.value = "true"` and display success toast.
  5. On error, set `submitState.value = "false"`, print error to toast.

#### [MODIFY] [SubmitSheet.vue](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/frontend/src/components/domain/SubmitSheet.vue)
- Add `@click="dialog = false"` to the "Done" button so that users can manually close the popup and reset the visibility state. 
- Change text from "Submitting dataset to DigitalTWINS Platform" to "Submitting assay results to DigitalTWINS Platform" (and update success/failure text respectively).

## Verification Plan

### Manual Verification
- Start the backend API and frontend portal.
- Navigate to `http://localhost/study-dashboard?trail=5,11,8,9`.
- Find "Assay 3 - Image conversion" (seek id 38).
- Click the "Submit" action button.
- Ensure the `SubmitSheet.vue` popup opens, showing the progress spinner.
- Verify that `digitaltwins-api` successfully downloads the Minio dataset and uploads it into the platform.
- Ensure the popup updates to a success state and the "Done" button correctly closes the popup.
