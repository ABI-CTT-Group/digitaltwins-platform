# Future Refactoring Tasks

This document tracks technical debt, refactoring tasks, and improvements that were identified but skipped in previous iterations. They are documented here for future consideration.

Resolved items are removed; git history and `docs/plans/` keep the record.

## REST API (`api`)

The following items were identified during the REST API restructuring (`docs/plans/2026-08-21-140800-rest-api-refactor`):

### [ ] 1. Action-style paths under `/dashboard`
* **Description**: The resource routes use plural paths (`/assays`, `/datasets`), but the clinician dashboard's routes in `services/api/app/routers/dashboard.py` still use action-style names: `/dashboard/assay-details` (GET and POST), `/dashboard/assay-launch`, `/dashboard/assay-gui-context`, `/dashboard/assay-results-submit`, `/dashboard/assay-download`, `/dashboard/dataset-detail` and `/dashboard/workflow-detail`. Rename them to resource paths. Callers to update: `services/portal/frontend/src/bootstrap/dashboard_api.ts` and the other portal files that build `/api/dashboard/...` URLs. Tool plugins also receive `/api/dashboard/assays/{id}/input-files/...` URLs in their launch context (`launch-context.example.json`), so keep that path, or the old paths as aliases, until plugins move.
* **Why skipped**: The REST API restructuring moved the resource routes to plural paths and removed the singular ones. The dashboard routes were outside that work.

### [ ] 2. API Versioning
* **Description**: Add a version to the API's route prefixes. The gateway strips `/api`, so clients would call `/api/v1/...` while the API's own routes start with `/v1/...` (see [services/nginx/README.md](../services/nginx/README.md)).
* **Why skipped**: Considered an internal API, so versioning was deemed unnecessary for the initial refactoring scope.

### [ ] 3. Response Models
* **Description**: The API returns raw Python dictionaries, and no route sets `response_model`. The only schema module, `services/api/app/schemas/assay.py`, describes request bodies. Add Pydantic response models (e.g., `DatasetResponse`, `AssayResponse`) for validation, OpenAPI docs and a stricter contract.
* **Why skipped**: To keep the scope focused on router reorganization.

### [ ] 4. Service Layer Extraction
* **Description**: `services/api/app/routers/assays.py` is about 990 lines and holds 13 private helpers (e.g., `_fetch_assay_configs`, `_discover_samples`, `_trigger_dag`, `_create_sds_output`, `_reconcile_manifest`). Move the business logic out of the router, into `src/digitaltwins/core/` or a new service module, so it can be tested without HTTP.
* **Why skipped**: Helpers were determined to be router-specific, and the `src/digitaltwins/core/` layer already acts as the primary service layer.

### [ ] 5. Async Handler Conversion
* **Description**: 60 of the API's 66 route handlers are `def`, not `async def`. FastAPI runs `def` handlers in a thread pool, so they don't block the event loop today. Changing them to `async def` while they still call `requests` and the synchronous Postgres driver would block the loop and make things slower. Convert a handler only after its I/O has moved to async clients (e.g., `httpx`, an async DB driver), and only where the thread pool is shown to be a bottleneck.
* **Why skipped**: Requires auditing underlying database and network dependencies (e.g., `requests`, synchronous DB drivers) to ensure they are async-compatible to prevent blocking the event loop.

### [ ] 7. CORS Hardening
* **Description**: `initialise` in `services/api/app/main.py` allows every origin (`allow_origins=["*"]`) with `allow_credentials=True` and all methods and headers. The portal calls the API through the gateway on the same origin, so check which clients, if any, make cross-origin calls. Then restrict the list to those origins, or drop the middleware.
* **Why skipped**: Left as-is for the initial refactor.

### [ ] 8. `GET /datasets/{uuid}/sample-types` fails for a dataset with no samples
* **Description**: `get_dataset_sample_types` in `services/api/src/digitaltwins/postgres/querier.py` builds `... WHERE sample_uuid IN ()` when the dataset has no samples. Postgres rejects that, so the endpoint returns 500 instead of an empty list. Return `[]` early for no samples. Both of its queries also format values into the SQL string (`dataset_uuid` in the first, the sample UUIDs in the second); pass them as query parameters instead.
* **Why skipped**: Found during the Dependabot work (`docs/plans/2026-11-03-151012-dependabot-alerts`); it predates it, and that work only changed dependency pins.

## Repository layout

Found while writing [codemap.md](codemap.md) (`docs/plans/2026-10-28-133109-repo-learnability`). The docs now explain these, but nothing was moved or renamed.

### [ ] 1. Inactive service folders
* **Description**: `services/jupyterlab/` and `services/pacs_pretend_external/` are commented out of the root `docker-compose.yml`, and `services/irods/` holds only a README and a `.gitkeep`. `services/api/docker/` (`orthanc/`, `postgres/`) and the services in `services/portal/docker-compose.yml` other than `portal-frontend` (MinIO, HAPI FHIR and its Postgres, `minio-init`) are left over from before those repos were merged in. Remove them, or move them under an `archive/` folder.
* **Why skipped**: The learnability work was docs-only.

### [ ] 2. Flat `util/` folder
* **Description**: `util/` holds about 70 scripts in one folder, indexed in [util/SCRIPTS.md](../util/SCRIPTS.md). Group them into subfolders (install, seek, keycloak, backup, sync), updating the Ansible playbooks, docs and the systemd unit that call them.
* **Why skipped**: Moving them breaks paths in playbooks and on running hosts.

### [ ] 5. util scripts that look dead or duplicated
* **Description**: Found while writing [util/SCRIPTS.md](../util/SCRIPTS.md). Check each one, then remove it or document why it stays:
  * `realm_exporter` duplicates `export_realm_and_users`.
  * `get_token`, `get_token2` and `get_token3` hardcode an old test domain.
  * `patch_keycloak_realm.py` looks superseded by `gen-realm.sh`.
  * `fix_api_role.py` and `fix_admin_cli.py` look like one-off fixes.
  * `grant_api_permissions.rb` and `rollback_api_permissions.rb` belong to the removed API-service-account model.
  * `grant_project_access.rb` overlaps `add-seek-project-member.sh`.
  * `docker_archive_volumes.sh` and `docker_restore_volumes.sh` overlap `stage-dump.sh` and `portal-restore.sh`.
  * `util/legacy-buildout-utils.md` is out of date about `generate-compute-env.sh` and `ufw_for_remote_compute.sh`.
* **Why skipped**: The learnability work was docs-only.

### [ ] 6. Stale builder env template in `services/portal/`
* **Description**: `services/portal/.env.template` is headed "the builder", but the builder moved to `services/builder/`, and nothing reads this file: the platform renders only the root `.env`. It still sets `KEYCLOAK_VERIFY_SSL=false` and `KEYCLOAK_CLIENT_ID=api`, which contradict the root `.env.template` and the builder's compose defaults. Remove it, or move it to `services/builder/` and update it to match those.
* **Why skipped**: Found while passing `KEYCLOAK_VERIFY_SSL` to the API (`docs/plans/2026-11-19-113214-api-compose-settings`); the template is outside that change.

## Lint cleanup leftovers

Found while making `make lint` pass. The cleanup kept behaviour unchanged, so these were noted rather than changed.

### [ ] 1. Unused portal components
* **Description**: `services/portal/frontend/src/components/domain/DownloadSheet.vue` and `SubmitSheet.vue` aren't imported anywhere. Remove both.
* **Why skipped**: Deleting files is outside a behaviour-neutral lint cleanup.

### [ ] 3. Broad exception handlers in `gen3/metadata_convertor.py`
* **Description**: Two former bare `except:` clauses are now `except Exception:`. The one around `data.get(key)` can't raise and prints `"test"`; remove it. The one around the mapping lookup should catch `(IndexError, KeyError)` only.
* **Why skipped**: Narrowing changes which errors propagate.

### [ ] 4. Imports of names `digitaltwins` no longer exports
* **Description**: `services/api/src/digitaltwins/core/uploader_gen3.py` imports `MetadataConvertor` and `MetadataUploader` from `digitaltwins`. `services/api/examples/query_postgres.py`, `services/api/examples/gen3/submit_metadata.py` and `services/api/tutorials/vph/tutorial_digitaltwins_api.ipynb` import `Auth`, `MetadataUploader`, `QuerierFactory` or `Connection`. Those exports are commented out in `digitaltwins/__init__.py`, so this code fails on import. Fix the imports or remove the code.
* **Why skipped**: Gen3 and these examples look unused; that needs checking first.

## API settings leftovers

Found while moving the API's environment reads into `services/api/src/digitaltwins/settings.py` (`docs/plans/2026-11-18-155050-config-consolidation`).

### [ ] 1. Inactive iRODS and Gen3 backends in the API package
* **Description**: `services/api/src/digitaltwins/irods/`, `gen3/`, `core/uploader_gen3.py` and `core/querier_factory.py` aren't deployed: `IRODS_ENABLED` and `GEN3_ENABLED` are commented out of `.env.template`, and the `gen3` package isn't installed, so importing `digitaltwins.gen3` fails. They still read the environment themselves and are listed as exceptions in `services/api/tests/test_settings.py`. `core/querier.py`, `core/uploader.py` and `core/downloader.py` keep iRODS and Gen3 branches, and `core/uploader.py` imports `irods.uploader` on every import. Remove the backends and their branches, then drop the `gen3` and `irods` flags from `Enabled` in `settings.py` and the exceptions from the test. `ConfigLoader` in `utils/config_loader.py` is used only by the Gen3 example `services/api/examples/export_metadata.py`; remove it with that example.
* **Why skipped**: The settings change kept behaviour unchanged; removing backends is a separate decision, and the examples that use them need checking first (see "Imports of names `digitaltwins` no longer exports" above).

## API tutorials

Found while renaming "DigitalTWINS" to "Digital Twins".

### [ ] 1. Review the tutorials in `services/api/tutorials/`
* **Description**: The tutorials were written for the 12 LABOURS shared-drive setup and haven't been checked against the current platform. They still use example paths on that drive, such as `X:\DigitalTWINS\resources\latest\configs\configs.ini`, `L:\DigitalTWINS\...` and `/MOUNT_POINT/DigitalTWINS/...` (`tutorial_1_getting_started.md` and the notebooks for tutorials 2 to 5). Check whether that drive layout still exists, update or remove the paths, and check each tutorial still runs (see also "Imports of names `digitaltwins` no longer exports" above).
* **Why skipped**: The rename changed display text only; the paths name a real folder, so renaming them would point at a folder that may not exist.
