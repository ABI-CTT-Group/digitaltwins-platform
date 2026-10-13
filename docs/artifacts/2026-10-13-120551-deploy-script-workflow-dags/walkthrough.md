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

- **API tests.** The new and changed tests pass: `test_workflow_dag.py` (29),
  `test_workflow_deploy_api.py` (10), `test_auth_roles.py`, `test_migrate.py`,
  `test_datasets_workflows_api.py` and `test_delete_dataset_cleanup.py`. The
  full suite gives 435 passed, 6 failed and 1 error. The 6 failures and 1
  error are the known harness problems in `test_delete_dataset_api`,
  `test_*_workspace_dataset_api` and `test_upload_dataset_api`.
- **Frontend tests.** The full vitest suite passes, 138 tests. `vue-tsc`
  reports 14 errors, the same count as before. The two in
  `WorkflowsOverallView.vue` are the existing RegistryView slot-typing errors.
- **Rebuild.** `digitaltwins-api`, `portal-frontend` and the five `airflow-*`
  services were rebuilt or recreated. Migration 0005 was applied at startup.
- **Live end to end:**
  1. Registered the example through `POST /datasets` as admin, which gave
     SEEK id 104 with status `pending`.
  2. Deployed it through `POST /workflows/<uuid>/deploy`. The result was
     `deployed` after about 26 s.
  3. Airflow showed `workflow_104` as "Image conversion", unpaused, with no
     import errors and no tool modules listed as DAGs.
  4. Triggered one run with an earlier assay sample. All 4 tasks succeeded.
     Inputs were staged at `workflow_104/run_0/inputs/`, and the NIfTI and
     NRRD outputs were written. The scratch objects were then removed.
  5. Deleted the workflow with `delete_tools=true`.
     `dags/workflow_104/` was removed.
- **Not exercised live:**
  - A researcher token getting 403, and a literal dag_id getting 422. Both
    are covered by integration tests.
  - Clicking *Deploy DAG* in a browser. The rebuilt bundle contains the
    action, and component tests cover it.
  - The portal approval path.
  - A full assay run through `run_assay`.

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

## Operations on the local platform (2026-10-13)

1. Deployed the pending workflow 107 ("workflow_image_conversion - tmp") as
   `workflow_107`.
2. Changed the example DAG's display name to `workflow_image_conversion`, then
   registered it as an admin. It became SEEK workflow 116 and auto-deployed as
   `workflow_116`.
3. Relinked assay 42 from workflow 89 to workflow 116. Its cohort, input and
   outputs are unchanged. SEEK now links them through SOP 41; SOP 37 is
   detached but kept.
4. Deleted workflow 89 with its tool datasets. Its stored DAG hardcoded
   `workflow_38`, so it could not be deployed. Also removed the hand-placed
   DAG file that served `workflow_89`.
5. Verified with one run of `workflow_116` on assay 42's input. All 4 tasks
   succeeded, and the scratch outputs were removed afterwards.
6. Verified the CLI auto-deploy live: an admin import deployed as
   `workflow_119`. That test registration was then deleted, as were the test
   registrations 110 and 113.
7. Deleted workflow 107 ("workflow_image_conversion - tmp") with its tools,
   SEEK 105 and 106, and its DAG folder. It was the only workflow with no SOP
   or assay link. The registered script workflow left is 116. Workflows 38 and
   39 remain on hand-placed DAG files.

## Follow-ups (not done)

- `run_assay` still swallows a missing-DAG 404 per sample.
- The legacy non-SDS approval builds `sparc-workflow-$<uuid>` (stray `$`).
- The portal route requires admin, but the backend also allows researcher.
- `examples/workflow/airflow/example_workflow/example_workflow.py` has an
  outdated comment saying "id must match the workflow dataset id".
- Seven gitignored runtime files under `services/airflow/dags/` hardcoded the
  live MinIO root credential as a fallback. They are three DAGs and four tool
  modules. The fallbacks and the credential task arguments were removed on
  2026-10-13, and `workflow_89` was re-run successfully afterwards. Still to
  do: push the cleaned files to the remote node with
  `util/sync-compute-dags.sh`, and rotate the credential, because it appeared
  in a session log.
- Remote compute workers still need `util/sync-compute-dags.sh` after a deploy.
