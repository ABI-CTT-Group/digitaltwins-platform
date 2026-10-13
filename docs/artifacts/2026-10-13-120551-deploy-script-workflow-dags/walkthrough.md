# Walkthrough: deploy script workflow DAGs

Written for: platform developers reviewing the change.

## What changed

A script workflow's DAG no longer needs to know its SEEK id. The author writes
`dag_id=Path(__file__).parent.name`. An admin deploys the registered workflow,
and the platform writes `code/` to `dags/workflow_<seek_id>/`, waits for
Airflow to load it, unpauses it, and records the outcome.

| Area | Files |
|---|---|
| Schema | `services/api/src/digitaltwins/postgres/migrations/0005_workflow_dag_status.sql` (`dataset.dag_status`, `dag_error`) |
| Registration | `workflows/pipeline.py` `_link_workflow` marks script workflows `pending` |
| Static check + folder | `workflows/dag.py` (`find_dag_file`, `write_dag_folder`, `remove_dag_folder`, `dag_id_for`) |
| Airflow wait + deploy | `workflows/deploy.py` (`wait_for_dag`, `deploy_workflow`) |
| Endpoint | `app/routers/workflows.py` `POST /workflows/{dataset_uuid}/deploy`, `app/routers/auth.py` `require_admin_role` |
| Delete | `core/deleter.py` `_remove_dag_folder` |
| Compose | API mounts `services/airflow/dags` at `/airflow-dags` (`AIRFLOW_DAGS_DIR`, `AIRFLOW_DAG_DEPLOY_TIMEOUT`); Airflow `REFRESH_INTERVAL` 30 s |
| Portal | `deploy · <status>` chip, admin-only *Deploy DAG* menu item, calls the API directly (`platform_api.deployWorkflowDag`) |
| Example | `examples/workflow/workflow_image_conversion/` (tracked) and the local `my_workspace` copy |
| Docs | `docs/workflow-dag-authoring.md`, ADR `2026-10-13-deploy-script-workflow-dags.md`, pointers in `populating_data.md`, ADR 2026-10-02, `services/airflow/README.md` |

## Design details worth knowing

- **Atomic folder write.** The folder is staged as `dags/.deploy-<hex>/` with an
  `.airflowignore` of `*`, then renamed into place. The final `.airflowignore`
  (`*.py` plus `!/<dag file>`) hides tool modules from the dag-processor. This
  was verified against Airflow 3.0.6's own file walker.
- **Redeploy.** A deploy counts as loaded only when the DAG's
  `last_parsed_time` is after the deploy started. Import errors count only when
  their timestamp is after the start too.
- **Ownership.** Files are chowned to the owner of the dags folder, so the host
  user can still manage them.
- **Example DAG.**
  - Its tools are imported from its own folder.
  - It stages under `DAG_ID`, which fixes the hardcoded `workflow_1` prefix.
  - It no longer passes MinIO credentials in `op_kwargs`, which Airflow shows
    in its UI. Tasks inherit them from the worker environment, on both the
    local and the remote worker.

## Verification

- **API tests.** The new and changed tests pass: `test_workflow_dag.py`,
  `test_workflow_deploy_api.py` (including auto-deploy), `test_import_dataset_cli.py`,
  `test_auth_roles.py`, `test_migrate.py`, `test_datasets_workflows_api.py` and
  `test_delete_dataset_cleanup.py`. The rest of the suite is unchanged; its
  known harness failures in `test_delete_dataset_api`,
  `test_*_workspace_dataset_api` and `test_upload_dataset_api` remain.
- **Frontend tests.** The full vitest suite passes. `vue-tsc` reports the same
  errors as before, including the existing RegistryView slot-typing errors in
  `WorkflowsOverallView.vue`.

## Update: automatic deploy for admins

When an admin registers or approves a script workflow, its DAG is now
deployed straight away. This covers the REST upload, upload-session finalize
and approve, and therefore the portal's approval. A researcher's registration
stays `pending` until an admin deploys it.

- `deploy.auto_deploy` runs in the background after the commit. It never fails
  the registration. If deploying isn't set up, or the error is unexpected, the
  workflow stays `pending`.
- `auth.has_admin_role` decides whether the caller is an admin.
- `jobs.run_commit_and_push` gained a `deploy_dag` flag.
- The CLI importer (`digitaltwins.cli.import_dataset`) follows the same rule.
  It sets `deploy_dag` when the signed-in user is an admin
  (`keycloak_login.is_admin`). It then prints whether the DAG was deployed,
  failed, or is waiting for an admin. A failed deploy doesn't change the exit
  code.

## Follow-ups (not done)

- `run_assay` still swallows a missing-DAG 404 per sample.
- The legacy non-SDS approval builds `sparc-workflow-$<uuid>` (stray `$`).
- The portal route requires admin, but the backend also allows researcher.
- Rotate the MinIO root credential. Gitignored runtime DAG files used to
  hardcode it as a fallback.
- Remote compute workers still need `util/sync-compute-dags.sh` after a deploy.
