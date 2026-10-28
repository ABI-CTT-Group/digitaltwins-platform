# Future Refactoring Tasks

This document tracks technical debt, refactoring tasks, and improvements that were identified but skipped in previous iterations. They are documented here for future consideration.

## REST API (`api`)

The following items were identified during the REST API restructuring (`docs/artifacts/2026-08-21-140800-rest-api-refactor`):

### [x] 1. URL Path Consistency
* **Description**: The API paths currently use a mix of singular nouns and actions (e.g., `POST /assay`, `POST /dataset`). These should be updated to standard RESTful resource paths (e.g., `POST /assays`, `POST /datasets`).
* **Why skipped**: To avoid breaking existing platform tooling and frontend clients.
* **Mitigation Strategy**: Implement redirect aliases for old paths (e.g., `POST /assay` redirects to `POST /assays`) with deprecation warnings to ensure a smooth transition.

### [ ] 2. API Versioning
* **Description**: Add versioning to the API route prefixes (e.g., `/api/v1/...`).
* **Why skipped**: Considered an internal API, so versioning was deemed unnecessary for the initial refactoring scope.

### [ ] 3. Response Models
* **Description**: The API currently returns raw Python dictionaries for responses. These should be formalized into Pydantic models (e.g., `DatasetResponse`, `AssayResponse`) for automatic validation, OpenAPI documentation generation, and stricter contract enforcement.
* **Why skipped**: To keep the scope focused on router reorganization.

### [ ] 4. Service Layer Extraction
* **Description**: Route handlers in `assays.py` contain private helper functions (e.g., `_fetch_assay_configs`, `_discover_samples`, etc.). These could be extracted to a dedicated `services/` layer to decouple business logic from HTTP routing.
* **Why skipped**: Helpers were determined to be router-specific, and the `src/digitaltwins/core/` layer already acts as the primary service layer.

### [ ] 5. Async Handler Conversion
* **Description**: Many route handlers in the API are synchronous (`def` instead of `async def`). Converting them to `async` would improve concurrency and performance.
* **Why skipped**: Requires auditing underlying database and network dependencies (e.g., `requests`, synchronous DB drivers) to ensure they are async-compatible to prevent blocking the event loop.

### [ ] 6. Configuration Consolidation
* **Description**: Environment variables are currently accessed via scattered `os.getenv()` calls throughout the codebase. Consolidate these into a centralized configuration module (e.g., using `pydantic-settings`).
* **Why skipped**: Left as-is to minimize the scope of the routing refactor.

### [ ] 7. CORS Hardening
* **Description**: Review and restrict the Cross-Origin Resource Sharing (CORS) policy.
* **Why skipped**: Left as-is for the initial refactor.

## Repository layout

Found while writing [codemap.md](codemap.md) (`docs/artifacts/2026-10-28-133109-repo-learnability`). The docs now explain these, but nothing was moved or renamed.

### [ ] 1. Inactive service folders
* **Description**: `services/jupyterlab/`, `services/pacs_pretend_external/` and `services/irods/` (only a `.gitkeep`) aren't wired into the root `docker-compose.yml`. `services/api/docker/` and some services in `services/portal/docker-compose.yml` are left over from before those repos were merged in. Remove them, or move them under an `archive/` folder.
* **Why skipped**: The learnability work was docs-only.

### [ ] 2. Flat `util/` folder
* **Description**: `util/` holds about 70 scripts in one folder, indexed in [util/SCRIPTS.md](../util/SCRIPTS.md). Group them into subfolders (install, seek, keycloak, backup, sync), updating the Ansible playbooks, docs and the systemd unit that call them.
* **Why skipped**: Moving them breaks paths in playbooks and on running hosts.

### [ ] 3. Old names in code and comments
* **Description**: Names from before the portal and preprocessor were merged in are still around: `clinical-dashboard` in a comment in `services/builder/docker-compose.yml`, a comment in `services/airflow/compute-worker/docker-compose.yml`, and the `preprocessor` DAG URL that `services/api/src/digitaltwins/airflow/workflow.py` still calls. Check whether that code path is live, then remove or rename.
* **Why skipped**: The learnability work was docs-only, and the DAG URL is code.

### [ ] 4. Empty root `tests/` folder
* **Description**: `tests/` holds only a `.gitkeep`. Use it for end-to-end tests, or remove it.
* **Why skipped**: There are no end-to-end tests yet.

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

## Lint cleanup leftovers

Found while making `make lint` pass. The cleanup kept behaviour unchanged, so these were noted rather than changed.

### [ ] 1. Unused portal components and a stale lockfile
* **Description**: `services/portal/frontend/src/components/domain/DownloadSheet.vue` and `SubmitSheet.vue` aren't imported anywhere. `services/portal/frontend/package-lock.json` is stale: the image and `make test-frontend` install from `yarn.lock` only, and yarn warns about the second lockfile. Remove all three.
* **Why skipped**: Deleting files is outside a behaviour-neutral lint cleanup.

### [ ] 2. Duplicate vite and rollup copies in the portal
* **Description**: The portal installs vite 6.4.1, but vitest 3.2.7 brings its own vite 7.3.6, and the hoisted rollup (4.61, from workbox) differs from the one vite bundles (4.53). `vite.config.ts` works around the type clashes with an `as PluginOption` cast on `glslify(...)` and a `@ts-expect-error` on the `test` key. Align the versions (upgrade vite, or add `resolutions` in `package.json` and update `yarn.lock`), then remove both workarounds; the `@ts-expect-error` fails type-check once it's no longer needed.
* **Why skipped**: It's a dependency change with its own risk.

### [ ] 3. Broad exception handlers in `gen3/metadata_convertor.py`
* **Description**: Two former bare `except:` clauses are now `except Exception:`. The one around `data.get(key)` can't raise and prints `"test"`; remove it. The one around the mapping lookup should catch `(IndexError, KeyError)` only.
* **Why skipped**: Narrowing changes which errors propagate.

### [ ] 4. Imports of names `digitaltwins` no longer exports
* **Description**: `services/api/src/digitaltwins/core/uploader_gen3.py` imports `MetadataConvertor` and `MetadataUploader` from `digitaltwins`, and some files in `services/api/examples/` and the tutorials import `Auth`, `MetadataUploader`, `QuerierFactory` or `Connection`. Those exports are commented out in `digitaltwins/__init__.py`, so this code fails on import. Fix the imports or remove the code.
* **Why skipped**: Gen3 and these examples look unused; that needs checking first.

### [ ] 5. A promise that never rejects
* **Description**: `getRepoRootCWLContent` in `services/portal/frontend/src/views/upload-dataset/components/utils.ts` never calls `reject`, so a failing `getRepoContents` leaves the caller waiting forever. Reject on error.
* **Why skipped**: It changes behaviour; the lint cleanup only dropped the unused parameter.
