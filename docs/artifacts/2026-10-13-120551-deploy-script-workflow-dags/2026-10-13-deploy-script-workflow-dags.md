# Deploy script workflow DAGs from the platform, named after their deploy folder

- **Date:** 2026-10-13
- **Status:** Accepted

## Context

A script workflow carries an Airflow DAG in `code/`. Registration
([2026-10-02-workflow-dataset-ingest.md](2026-10-02-workflow-dataset-ingest.md))
stores it but never deploys it. Running an assay triggers the DAG
`workflow_<seek_id>` (`services/api/app/routers/assays.py`), where `seek_id`
is the SEEK Workflow id assigned *at registration*.

So the DAG an author writes must already contain an id that does not exist
yet, and that changes on every re-registration. In practice authors registered
first, read the SEEK id, hand-edited `dag_id="workflow_<id>"`, copied the file
into `services/airflow/dags/` and unpaused it. The example dataset drifted
(registered as SEEK 67, then 72, while its DAG said `workflow_89`).

Forces:
- Airflow needs a literal, unique dag_id when it parses the file.
- The platform finds the DAG only through `workflow_<seek_id>`; assays store
  `workflow_seek_id`, so changing that lookup touches every existing assay.
- DAG code runs inside the Airflow dag-processor and workers with Airflow's
  environment (MinIO and Keycloak credentials), so deploying is a trust
  decision. Registration is open to `researcher` as well as `admin`.
- New DAGs start paused (`DAGS_ARE_PAUSED_AT_CREATION=true`) and the
  dag-processor rescans every 300 s by default.

## Alternatives Considered

### dag_id

#### Option A: Folder-derived id (chosen)
The platform deploys `code/` to `dags/workflow_<seek_id>/`; the DAG declares
`dag_id=Path(__file__).parent.name`.
- Pros: one fixed line for authors; `run_assay` and stored assays unchanged;
  runs locally under any folder name.
- Cons: implicit — a hardcoded id would silently never match. Mitigated by a
  static check that rejects any other dag_id at deploy time.

#### Option B: Generated wrapper DAG
Author exposes `build_dag(dag_id)`; the platform generates a launcher that
imports it by path and passes `workflow_<seek_id>`.
- Pros: explicit, checkable contract.
- Cons: generated code, path-based module loading and name clashes, extra
  traceback layer; authors must restructure a normal `@dag` into a factory.

#### Option C: Author-declared id stored by the platform
Author picks any id; the platform parses and stores it; `run_assay` reads it.
- Pros: author fully in control of the name.
- Cons: uniqueness to enforce across authors; changes the run-time lookup
  and every stored assay.

#### Option D: Rewrite the literal at deploy time
- Cons: string surgery on user code; fragile.

### Delivery

- **API writes the shared dags volume (chosen):** simplest; same mount the
  Airflow services already use. Remote compute workers still need
  `util/sync-compute-dags.sh`.
- **Airflow 3 S3/MinIO DAG bundle:** no shared mount and reaches remote
  workers, but adds a provider, bundle config and versioning semantics.
- **Manual copy (status quo):** the problem being solved.

### Gate

- **Auto-deploy when an admin registers or approves it, plus an admin-only
  deploy endpoint (chosen):** an admin's approval is the deploy; a
  researcher's registration stays `pending` until an admin deploys it.
  Registration stays self-service, and running code in Airflow still needs an
  admin.
- **Admin-only deploy endpoint only:** the first version. It made admins
  approve a workflow and then deploy it as a second step.
- **Auto-deploy on every registration:** would let any researcher run code in
  Airflow.
- **Make registration admin-only:** removes researcher self-service.

### Verification

- **Blocking poll in the deploy request (chosen):** one call returns
  deployed/failed with the import error; the scan interval is lowered to 30 s
  so the default 120 s budget is enough.
- **Client polls a status endpoint:** more moving parts for the same result.

## Decision

- dag_id is folder-derived (Option A). `POST /workflows/{dataset_uuid}/deploy`
  (admin only) downloads the workflow's `code/` from MinIO, statically checks
  that exactly one DAG exists at the top of `code/` and that its dag_id is
  `Path(__file__).parent.name`, writes it atomically to
  `dags/workflow_<seek_id>/` with an `.airflowignore` that hides the tool
  modules, waits for Airflow to load it (or report an import error), unpauses
  it and records `dataset.dag_status` (`pending | deployed | failed`) and
  `dag_error`.
- Registration records `dag_status='pending'` for script workflows. When the
  caller is an admin (REST upload, upload-session finalize or approve, which
  includes the portal's approval, or the CLI importer), the DAG is then
  deployed: in the background for the API, straight after the commit for the
  CLI.
  A failed deploy never fails the registration; it is recorded in
  `dag_status`, or left `pending` when deploying is not set up.
- Deleting the workflow removes its DAG folder.
- The portal Workflow Hub shows a `deploy · <status>` chip and an admin-only
  "Deploy DAG" action that calls the API directly with the user's token.
- Airflow's `[dag_processor] refresh_interval` is lowered to 30 s.

## Consequences

- Authors never need to know the SEEK id; the same file works locally and
  deployed. The contract is documented in `docs/workflow-dag-authoring.md`.
- Deployed workflows are self-contained: tools ship next to the DAG and are
  imported from its folder, not from the shared `dags/tool/`.
- An admin registering, approving or deploying a workflow is the only control
  on code that runs with Airflow's credentials.
- The static check runs on the API's Python (3.11); a DAG using syntax newer
  than that is rejected even though Airflow (3.12) could load it.
- Re-registering creates a new SEEK id and a new `pending` DAG; assays linked
  to the old workflow keep pointing at the old id (pre-existing behaviour).
- Deleting a workflow leaves its run history in Airflow as a stale DAG.
- A missing DAG at run time is still swallowed per sample by `run_assay`;
  surfacing it is a follow-up.
