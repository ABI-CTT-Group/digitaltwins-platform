# populating data

This document outlines the steps to populate initial data into the DigitalTWINS Platform after deployment


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

#### Method 2: Using the API service

* [**TODO:** Implementation details for populating data via the DigitalTWINS platform API.]

### 2. Database initialization

Create the necessary associations in the database using the **pgAdmin** interface: http://localhost:8004

* **Programme:** In the `programme` table, create an entry and add the corresponding **SEEK ID**.
* **Project:** In the `project` table, create an entry and add the corresponding **SEEK ID**.

### 3. Workflow upload (Airflow)

1. Have your workflow code in [Airflow Dags](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) format and place in `services/airflow/dags/`. You can use the example workflows in `./example/airflow` for testing
   
   ```bash
   cp -r ./examples/workflow/airflow/* ./services/airflow/dags/
   ```
   
2. Restart the Airflow service to load the new workflows

   ```bash
   sudo docker compose restart airflow-apiserver
   ```

3. Verify if the workflow is visible in the Airflow UI: `http://localhost:8002/dags`

### 4. Upload measurement dataset

Measurement datasets can be uploaded using the following methods:

* Via the **API service**. [todo. add details]
* Directly from the **portal**. [todo. future implementation]

## Automated Data Population

From existing Docker Volumes
