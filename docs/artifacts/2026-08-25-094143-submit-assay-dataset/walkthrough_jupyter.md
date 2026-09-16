# Jupyter/Notebook Assay Dataset Upload Walkthrough

The `upload_workspace_datasets` endpoint in the `digitaltwins-api` has been successfully updated to natively support fetching outputs from Jupyter Server. 

## What was changed

1. **Jupyter Internal URL:** Added `JUPYTERHUB_INTERNAL_URL` to `assays.py` to allow the API to communicate with JupyterHub from inside the backend docker network.
2. **Jupyter Integration (`_download_jupyter_folder`)**: Added a helper function to recursively fetch output folders via the Jupyter Server REST API:
   - Uses the `GET /api/contents/{path}` endpoint to walk the folder structure.
   - Uses the `GET /files/{path}` endpoint to download raw files natively.
   - Requires the user's Keycloak token for Authorization.
3. **Assay Type Detection**: The handler now reads the assay's tags from `querier.get_assay()`. If it detects the `"notebook"` tag, it fetches outputs from Jupyter. Otherwise, it defaults to the standard MinIO / Airflow flow.
4. **Testing**: 
   - Refactored `test_upload_workspace_dataset_api.py` to properly use FastAPI's `dependency_overrides` for injecting the `get_querier` mock.
   - Added a new unit test `test_upload_workspace_datasets_jupyter` that mocks the Jupyter API calls and verifies the new branch handles directory walking correctly.

> [!NOTE] 
> The temporary directory (`tmp_dir`) is properly deleted in a `finally` block in the existing code (`shutil.rmtree(tmp_dir, ignore_errors=True)`), ensuring that datasets do not pile up on the API server's file system after successful (or failed) uploads.

## Next Steps

To test this locally:
1. Rebuild and restart the API container:
   ```bash
   cd services/api/digitaltwins-api
   docker compose --env-file ../../../.env up -d --build digitaltwins-api
   ```
2. Test submitting Assay 1 (ID 32) in the portal frontend, ensuring it has output data inside its `outputs` folder in your Jupyter workspace.
