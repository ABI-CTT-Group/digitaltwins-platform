# Deploy script (Airflow) workflow DAGs + resolve the dag_id problem

## Context

Script workflows can be registered through the portal (`/upload-workflow-dataset`) or the REST API, but the DAG inside `code/` is **stored, never deployed** (ADR 2026-10-02, line 133). Running an assay triggers `workflow_<seek_id>` ([assays.py:544](services/api/app/routers/assays.py#L544)), so today an author must:
1. register first to learn the SEEK id,
2. hand-edit `dag_id="workflow_<id>"` into the DAG,
3. hand-copy the file into `services/airflow/dags/` and unpause it.

That is a chicken-and-egg problem: the id the DAG needs does not exist until after registration, and it changes on every re-registration (the example has drifted: SEEK ids 67, 72, while the DAG says `workflow_89`).

**Outcome:** an author writes a DAG with a fixed one-line convention and never needs to know the id; an admin clicks **Deploy DAG** (or calls the API) and the platform validates, deploys, unpauses and verifies it in Airflow.

### Decisions (from interview)
| Topic | Decision |
|---|---|
| dag_id | Folder-derived. Author writes `DAG_ID = Path(__file__).parent.name`; platform deploys `code/` to `dags/workflow_<seek_id>/`. `run_assay` unchanged. |
| Validation | Reject at deploy: static AST check (no execution). Post-deploy: poll Airflow for the DAG or an import error. |
| Delivery | digitaltwins-api writes to the shared Airflow dags volume. |
| Gate | Registration unchanged (researchers OK) and records `dag_status='pending'`. New **admin-only** `POST /workflows/{uuid}/deploy`. |
| Layout | Self-contained: the whole `code/` folder deploys; the DAG imports tools from its own folder. |
| Cleanup | Workflow delete removes `dags/workflow_<seek_id>/`. |
| Example | Fix `my_workspace/data/workflow_image_conversion` as the reference. |

## Review findings (current implementation)

1. **dag_id coupling** — described above. Also the legacy example comment "this id must match the workflow dataset id" ([example_workflow.py:8](examples/workflow/airflow/example_workflow/example_workflow.py#L8)) is outdated.
2. **No deployment path** — nothing writes to the dags folder or unpauses; new DAGs boot paused (`DAGS_ARE_PAUSED_AT_CREATION=true`).
3. **Missing DAG is silent** — `run_assay` swallows `_trigger_dag` 404s per sample and still returns 200 ([assays.py:575-583](services/api/app/routers/assays.py#L575-L583)). Not changed by this plan; listed as a follow-up.
4. **Example DAG hardcodes `"dag_id": "workflow_1"`** for the download_samples staging prefix (line 270), so every run stages under `workflow_1/...`.
5. **Example is not self-contained** — imports `tool.tool_*` from shared `services/airflow/dags/tool/`; `tool_download_samples.py` is missing from `code/`.
6. **Hardcoded MinIO secret default** remains in the runtime copies under `services/airflow/dags/` (`workflow_image_conversion_test.py`, `tool/tool_download_samples.py`). Gitignored, but should be removed.
7. **Example metadata is template/stale** — README "change this line", dataset_description says "Curated MRI dataset", manifest lists 450 `.dcm` files that don't exist, CWL `run.sh` calls `dicom_to_nifti.py` while files are `tool_*.py` (validation only checks CWL file names, so cosmetic).
8. **Role mismatch** — portal route requires `admin`, backend accepts researcher; "approval" is not an admin gate (portal approval and REST registration both open to researchers).
9. **Legacy non-SDS approval** builds `f"sparc-workflow-${uuid.uuid4()}"` — stray `$` ([workflow_router.py](services/portal/backend/app/router/workflow_router.py) ~line 640). Out of scope; note only.
10. **Airflow scan interval is 300 s** (`[dag_processor] refresh_interval`), so a new DAG can take 5 min to appear.
11. **No tests** for `run_assay` / `_trigger_dag` / the dag_id rule.

## Author contract (what goes in the authoring guide)

```python
from pathlib import Path
DAG_ID = Path(__file__).parent.name      # becomes "workflow_<seek_id>" once deployed
TOOL_DIR = str(Path(__file__).parent)    # tools ship next to the DAG

@dag(dag_id=DAG_ID, dag_display_name="Image conversion", schedule=None, ...)
def image_conversion(): ...
```
- Exactly one DAG, in a file directly in `code/`. dag_id must be that expression (inline or via a module-level name). Missing (`@dag()` → function name) or literal ids are rejected with a message showing the line.
- Pass `TOOL_DIR` / `DAG_ID` via `op_kwargs` (ExternalPythonOperator copies only the callable source, so `__file__` isn't available inside it); callables do `sys.path.insert(0, tool_dir)` then `from tool_x import run`.
- Locally, the DAG takes whatever folder name it sits in.

## Implementation steps (TDD: failing test first each step)

0. **ADR + artifacts first.** Write `docs/decisions/2026-10-13-deploy-script-workflow-dags.md` from `TEMPLATE.md` (alternatives: shared volume vs Airflow S3 DAG bundle vs manual; folder-derived id vs generated wrapper vs literal rewrite; admin endpoint vs auto-deploy; blocking poll vs client polling). Sync this plan to `docs/artifacts/2026-10-13-<HHMMSS>-deploy-script-workflow-dags/` (redacted, no local paths).

1. **Migration** `services/api/src/digitaltwins/postgres/migrations/0005_workflow_dag_status.sql`: add `dataset.dag_status varchar(20)`, `dag_error text`; backfill `'pending'` for existing script workflows. Statuses: `pending | deployed | failed` (no stored transient state). Test: `tests/test_migrate.py`.

2. **Registration records pending** — `_link_workflow` in [pipeline.py](services/api/src/digitaltwins/workflows/pipeline.py) sets `dag_status='pending'` for script, NULL otherwise. Test: extend `tests/test_datasets_workflows_api.py`.

3. **Pure DAG helpers** — new `services/api/src/digitaltwins/workflows/dag.py`:
   - `find_dag_file(code)` — AST rule above; candidate files = `*.py` containing "airflow" and "dag" (same as Airflow safe mode). Raises `ValueError` with user-facing message.
   - `write_dag_folder(code, dags_dir, dag_id, dag_file)` — stage in `dags/.deploy-<hex>/` with `.airflowignore` = `*`, copy, `rmtree` old target, `os.rename`, then atomically replace `.airflowignore` with `*.py` + `!/<dag_file>` (hides tool files from the DAG processor; e.g. `tool_download_samples.py` contains "airflow"+"dag"). Clean staging on failure.
   - `remove_dag_folder(dags_dir, seek_id)` (idempotent), `dags_dir()` from `AIRFLOW_DAGS_DIR`, `dag_id_for(seek_id)` (digits only — prevents path injection).
   - Tests: new `tests/test_workflow_dag.py` (model on `tests/test_workflow_validation.py`) — accept/reject matrix, ignore-file contents, redeploy replace, no leftover staging.

4. **Admin dependency** — `require_admin_role` beside `require_upload_role` in [auth.py](services/api/app/routers/auth.py). Test: `tests/test_auth_roles.py`.

5. **Deploy logic** — new `services/api/src/digitaltwins/workflows/deploy.py`:
   - `_airflow(method, path)` — single Airflow HTTP seam, reusing the token logic in `src/digitaltwins/airflow/workflow.py`.
   - `wait_for_dag(dag_id, rel_file, started, timeout)` — loop: `GET /api/v2/dags/{id}` 200 → `PATCH {"is_paused": false}` → deployed; else match `GET /api/v2/importErrors` by filename + timestamp ≥ start → failed with stack trace; else timeout (`AIRFLOW_DAG_DEPLOY_TIMEOUT`, default 120 s) → failed "deploy again to re-check".
   - `deploy_workflow(conn, uuid)` — load row (404 / 409 not script), download `<uuid>/code/` from MinIO `workflows` bucket via `MinioDownloader`, `find_dag_file`, `write_dag_folder`, `wait_for_dag`, store status/error.

6. **Endpoint** — `POST /workflows/{dataset_uuid}/deploy` in [workflows.py](services/api/app/routers/workflows.py), `Depends(require_admin_role)`. Errors: 404 / 409 / 422 (static check, row set failed) / 503 (no dags dir or Airflow unreachable). Airflow-side outcome returned as 200 `{dag_id, dag_status, dag_error}`. Status is also visible via existing `GET /datasets` (`SELECT *`). Tests: new `tests/test_workflow_deploy_api.py` (integration; fixtures from `test_datasets_workflows_api.py`, fake `_airflow`) — deployed, 403 researcher, 409 gui, 404, 422 literal, import error, timeout, redeploy.

7. **Delete cleanup** — `_remove_dag_folder(seek_id, workflow_type)` in [deleter.py](services/api/src/digitaltwins/core/deleter.py) after `_remove_local_copies`; best-effort, logged. Test: case in `tests/test_delete_dataset_cleanup.py`.

8. **Compose**
   - `services/api/docker-compose.yml`: volume `../airflow/dags:/airflow-dags`, env `AIRFLOW_DAGS_DIR=/airflow-dags`, `AIRFLOW_DAG_DEPLOY_TIMEOUT`.
   - `services/airflow/docker-compose.yml` common env: `AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL: '30'` (was 300 via airflow.cfg).
   - chown written tree to the dags dir owner so the host user can still manage it.

9. **Portal frontend** — Deploy button for admins on script workflow cards.
   - ⚠️ *Adjustment:* the frontend calls digitaltwins-api **directly** via the existing `dtApi` client (same as `deletePlatformDataset`), not a portal-backend proxy. A proxy keyed by portal workflow id couldn't deploy workflows registered via the REST API. No portal backend change.
   - `platform_api.ts`: `deployWorkflowDag(uuid)`; carry `dagStatus`/`dagError` through `withPlatformWorkflows`. `types.ts`: fields on `WorkflowResponse`.
   - `cardTags.ts`: `deployTag()` chip `deploy · <status>` (error in tooltip), matching ADR 2026-10-12 vocabulary.
   - `WorkflowCard.vue`: `canDeploy` prop, "Deploy DAG" menu item for script workflows in the platform. `WorkflowsOverallView.vue`: pass `authStore.hasAdminRole`, handle `deploy-dag` (show `deploying`, toast result, refresh).
   - Vitest: `cards.spec.ts`, `cardTags.spec.ts`, `platform_api.spec.ts`.

10. **Reference example** (`my_workspace/` is gitignored → local change)
    - DAG: `DAG_ID`/`TOOL_DIR` convention, `"dag_id": DAG_ID` (fixes `workflow_1`), `from tool_x import run` (drop `tool.` prefix), drop `_test` from the filename, remove any credential defaults.
    - Add `code/tool_download_samples.py` (copy of shared one, secret default removed).
    - Fix CWL `run.sh` names, README, dataset_description, regenerate manifest.
    - ⚠️ *Adjustment:* also commit a tracked copy (DAG + tool scripts + CWLs, minimal metadata) under `examples/workflow/workflow_image_conversion/` so the authoring guide can link to something in git. *(Implemented there rather than under `examples/workflow/airflow/`, which `docs/populating_data.md` copies wholesale into the dags folder.)*

11. **Docs** — `docs/workflow-dag-authoring.md` (contract above, one DAG at `code/` top level, `cwl_venv` libraries, `compute_queue` + `util/sync-compute-dags.sh` for remote workers, deploy statuses, where to read import errors, Python 3.11-parseable). One-line pointer in ADR 2026-10-02 line 133 and `services/airflow/README.md`. Sync artifacts after each doc change.

## Verification

1. API tests (throwaway container per memory recipe — never against live Postgres):
   `pytest tests/test_workflow_dag.py tests/test_auth_roles.py tests/test_migrate.py tests/test_workflow_deploy_api.py tests/test_datasets_workflows_api.py tests/test_delete_dataset_cleanup.py`
2. Frontend: `npx vitest run src/views/upload-dataset/components/__tests__ src/bootstrap/__tests__/platform_api.spec.ts`
3. Rebuild/restart:
   ```
   docker compose up -d --build digitaltwins-api   # code, volume, env; migration 0005 at startup
   docker compose up -d                            # airflow-* pick up refresh_interval
   docker compose up -d --build portal-frontend
   ```
4. End-to-end: upload the fixed example via `/upload-workflow-dataset` as a researcher → approve → card shows `deploy · pending`; log in as admin → **Deploy DAG** → `deploy · deployed`; `http://localhost/airflow/dags/workflow_<seek_id>` exists, unpaused, staging prefix is `workflow_<seek_id>/run_0/...`. Repeat via `curl -X POST .../digitaltwins-api/workflows/<uuid>/deploy` with an admin token; researcher token → 403. Upload a DAG with a literal dag_id → 422 message. Link an assay, run it, confirm both outputs land. Delete the workflow → `dags/workflow_<seek_id>/` gone.
5. `gitleaks detect --source docs/artifacts/ --no-git` before staging.

## Risks / out of scope
- Deploy runs author code with Airflow's environment (MinIO, Keycloak secrets). The admin gate is the only control — stated in ADR and guide.
- API image is Python 3.11, Airflow is 3.12: 3.12-only syntax fails the static check.
- Remote compute worker still needs a manual `util/sync-compute-dags.sh`.
- Deleting a workflow leaves Airflow's run history as a stale DAG (could add `DELETE /api/v2/dags/{id}` later).
- Re-approval creates a new SEEK id; existing assays keep pointing at the old one (pre-existing behaviour).
- Follow-ups not in scope: surface the swallowed 404 in `run_assay`; the `$` uuid bug; portal route role mismatch.
