# DigitalTWINS Portal

## Deploy locally

### Docker setup

- Clone the repo to your PC
```sh
# 1. start docker
cd DigitalTWINS-Portal

docker compose up --build -d
```

## How to Use the Study Dashboard

### Table of Contents
- [Step 1: Access the Study Dashboard in the DigitalTWINS Portal](#step-1-access-the-study-dashboard-in-the-digitaltwins-portal)
- [Step 2: Edit an Assay](#step-2-edit-an-assay)
- [Step 3: Launch an Assay](#step-3-launch-an-assay)
- [Step 4: Monitor an Assay](#step-4-monitor-an-assay)
- [Step 5: Verify an Assay](#step-5-verify-an-assay)
- [Step 6: Download a Dataset](#step-6-download-a-dataset)
- [Step 7: Submit a Dataset](#step-7-submit-a-dataset)

---

### Step 1: Access the Study Dashboard in the DigitalTWINS Portal
[Study Dashboard](http://130.216.216.26/dashboardstudy)  

Here you can find information about all **Programmes**, **Projects**, **Investigations**, **Studies**, and **Assays**.

You can click the **`EXPLORE`** button under the *Programmes*, *Projects*, *Investigations*, or *Studies* catalogues to view more details. 
<img width="1773" height="648" alt="image" src="https://github.com/user-attachments/assets/f228c509-dd40-471a-98e6-7cfcff369995" />


Once you enter the **Assays** page, you can:
- Edit an assay  
- Launch an assay  
- Monitor an assay  
- Verify an assay  
- Download a dataset  
- Submit a dataset

<img width="2163" height="591" alt="image" src="https://github.com/user-attachments/assets/03b3b1a7-9131-4664-8ef5-30e0c04a41c7" />

---

### Step 2: Edit an Assay
- Click the **`EDIT`** button on the assay page.  
- On the **Edit** page, you can configure the assay by selecting a workflow:  
  - A **CWL script–based workflow**, or  
  - A **Web GUI–based workflow**  
- After choosing a workflow, select the dataset and sample type for its inputs and outputs.  
- Finally, specify how many **cohorts** you want to execute for this assay.  
<img width="1599" height="1563" alt="image" src="https://github.com/user-attachments/assets/6799965c-2891-45f4-ae34-4b08c2013a51" />

---

### Step 3: Launch an Assay
After editing the assay, click the **`LAUNCH`** button.  

- **CWL script–based workflow**  
  The workflow will run in **Airflow**.  
- **Web GUI–based workflow**  
  A Web GUI will be displayed in the **DigitalTWINS Portal**.  

---

### Step 4: Monitor an Assay
If your assay uses a **CWL script–based workflow**, the **`MONITOR`** button becomes available once the workflow starts running in Airflow.  
Click it to track the execution progress of the assay.  

---

### Step 5: Verify an Assay
For **CWL script–based workflows**, once execution is complete in Airflow, click the **`VERIFY`** button to review the resulting dataset.  

---

### Step 6: Download a Dataset
For **CWL script–based workflows**, after the execution finishes in Airflow, you can download the resulting dataset to your local machine.  

---

### Step 7: Submit a Dataset
For **CWL script–based workflows**, once you are satisfied with the result dataset, you can upload it to the **DigitalTWINS platform** by clicking the **`SUBMIT`** button.  
