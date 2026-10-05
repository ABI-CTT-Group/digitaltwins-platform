# Populating data

This document outlines the steps to populate initial data into the Digital Twins Platform after deployment


## Manual Data Population

### 1. Create research object descriptions

Research objects can be created through the catalog service (SEEK) UI or via the API service.

#### Method 1: Using the Catalog Service (SEEK) UI

1. Access the SEEK UI at `http://localhost:8001`
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

#### Method 2: Using the API service

* [**TODO:** Implementation details for populating data via the DigitalTWINS platform API.]

### 2. Workflow upload (Airflow)

1. Have your workflow code in [Airflow Dags](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) format and place in `services/airflow/dags/`. You can use the example workflows in `./example/airflow` for testing
   
   ```bash
   cp -r ./examples/workflow/airflow/* ./services/airflow/dags/
   ```
   
2. Restart the Airflow service to load the new workflows

   ```bash
   sudo docker compose --env-file ./.env --project-directory services/airflow restart
   ```

3. Verify if the workflow is visible in the Airflow UI: `http://localhost:8002/dags`

### 3. Upload measurement dataset

Measurement datasets can be uploaded using the following methods:

* Via the **API service**. [todo. add details]
* Directly from the **portal**. [todo. future implementation]

## Automated Data Population

From existing Docker Volumes
