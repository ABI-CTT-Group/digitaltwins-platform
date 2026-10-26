# Populating data

This document outlines the steps to populate initial data into the Digital Twins Platform after deployment


## Manual Data Population

### 1. Create research object descriptions

Research objects can be created through the catalog service (SEEK) UI or via the API service.

#### Method 1: Using the Catalog Service (SEEK) UI

1. Open the SEEK UI at `<platform URL>/seek` (e.g. `http://localhost/seek`) and sign in with Keycloak
2. Create the following research objects
   - programme 
   - project 
   - investigation 
   - study 
   - assay 
   - Workflow
      - note: When creating a **Workflow** object, you **must** add the tag **"workflow"**.

> 💡 For detailed help, refer to the [SEEK’s help documentation](https://docs.seek4science.org/help/user-guide/programme-creation-and-management).

#### Link an assay to its workflow

The portal finds an assay's workflow through SEEK: Assay → SOP → Workflow. You don't need to build that link by hand. On the study dashboard, open the assay's **Configure assay** dialog, pick the workflow under **Select Workflow**, fill in the form and **Save**. Saving creates an SOP `Workflow link: <workflow title>` in the assay's project, visible to that project's members.

- The assay needs a type tag in SEEK: **gui**, **notebook** or **script**.
- The dropdown lists only workflows with the same type tag that belong to one of the assay's SEEK projects. The API refuses any other workflow (400).
- Only admins and researchers can link a workflow.
- Picking a different workflow later resets the form's inputs, outputs and cohort. On Save, the assay is detached from the old SOP (which stays in SEEK) and a new SOP is created.

See [the ADR](decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md) for why it works this way.

#### Method 2: Using SEEK's REST API

Research objects can also be created with SEEK's JSON:API, using a Keycloak token.
[`util/populate-cpu-burn-assay.sh`](../util/populate-cpu-burn-assay.sh) is a worked
example: it creates a Programme → Project → Investigation → Study → Assay chain,
registers a sample dataset and configures the assay. See
[seek-integration.md](seek-integration.md) for how the platform authenticates to SEEK.

### 2. Workflow upload (Airflow)

Register a script workflow dataset. When an admin registers or approves it, its
DAG is deployed to Airflow automatically. Otherwise an admin deploys it from the
portal's Workflows page (`/catalogue/workflows`, *Deploy DAG*) or with `POST /api/workflows/{dataset_uuid}/deploy`.
The DAG must name itself after its deploy folder (`dag_id=Path(__file__).parent.name`).
See [Writing and deploying a script workflow DAG](workflow-dag-authoring.md) and the
example dataset in `examples/workflow/workflow_image_conversion/`.

DAGs that are not workflow datasets are still copied by hand into
`services/airflow/dags/`, and `util/sync-dags.sh` copies the DAGs of another
deployment. Airflow picks up new files within 30 seconds; check the Airflow UI at
`<platform URL>/airflow/dags`. New DAGs start paused.

### 3. Upload measurement dataset

Measurement datasets can be uploaded using the following methods:

* Via the **API service**: from a terminal on the server, run `services/api/scripts/import-dataset.sh <folder|zip> --category measurements --fhir auto` ([guide](../services/api/docs/import-dataset.md)), or upload from Python with `UploadClient` (see the [API README](../services/api/README.md)).
* From the **portal**: admins and researchers upload measurement datasets on the
  catalogue's Measurements page (`/catalogue/measurements`).

## Copying data from another deployment

To move the data of an existing deployment to a new one, see
[Transferring data from one system to another](../util/README.md#transferring-data-from-one-system-to-another).
