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
  - A **script–based workflow**, or  
  - A **Web GUI–based workflow**  
- After choosing a workflow, select the dataset and sample type for its inputs and outputs.  
- Finally, specify how many **cohorts** you want to execute for this assay.  
<img width="1599" height="1563" alt="image" src="https://github.com/user-attachments/assets/6799965c-2891-45f4-ae34-4b08c2013a51" />

---

### Step 3: Launch an Assay
After editing the assay, click the **`LAUNCH`** button.  

- **Script–based workflow**  
  The workflow will run in **Airflow**.  
- **Web GUI–based workflow**  
  A Web GUI will be displayed in the **DigitalTWINS Portal**.  

---

### Step 4: Monitor an Assay
If your assay uses a **script–based workflow**, the **`MONITOR`** button becomes available once the workflow starts running in Airflow.  
Click it to track the execution progress of the assay.  

---

### Step 5: Verify an Assay
For **script–based workflows**, once execution is complete in Airflow, click the **`VERIFY`** button to review the resulting dataset.  

---

### Step 6: Download a Dataset
For **script–based workflows**, after the execution finishes in Airflow, you can download the resulting dataset to your local machine.  

---

### Step 7: Submit a Dataset
For **script–based workflows**, once you are satisfied with the result dataset, you can upload it to the **DigitalTWINS platform** by clicking the **`SUBMIT`** button.  

---

## Registering a Plugin / Workflow

Plugins and CWL workflows can be registered into the portal in **two ways**:

| Source | When to use | What you provide |
|---|---|---|
| **Local folder / .zip** (default) | Private repo, in-progress code, or no GitHub at all | Drag a folder (or a `.zip` file) into the dropzone — uploaded directly to the portal |
| **Git URL** | Code already lives on a **public** GitHub repo | Paste `https://github.com/<owner>/<repo>` — portal reads `package.json`, root folders, and `.cwl` from the GitHub API |

In the registration form (*Catalogue → Tools* or *Catalogue → Workflows*), the **Source** radio at the top of the *Base Information* step starts on *Local Folder*; switch it to *Git URL* to register from a repository.

### Local upload constraints

- **Total size cap: 500 MB.** Both nginx and the builder reject anything bigger.
- The following directories are auto-skipped in both modes (folder / pre-made zip): `node_modules`, `.git`, `dist`, `build`. If you zip a project with a third-party tool, you do **not** need to manually clean these — they are filtered server-side on extract too.
- `package.json` is searched recursively; the shallowest match (outside the blacklist) provides the `version` / `author` autofill. Project root detection unwraps single-folder GitHub-style zips automatically.
- A `.zip` that you downloaded straight from GitHub ("Source code (zip)") works as-is — no need to unzip first.

---

## Importing a dataset from the server

Dataset ingest (measurements, models, tools and workflows) lives in the platform
REST API (`api`); the portal's Upload pages are clients of it. To import
a prepared dataset from the server terminal instead, use the importer that ships
with the platform API: `services/api/scripts/import-dataset.(sh|command|ps1|bat)`.
See its guide: `services/api/docs/import-dataset.md`.

---

## Release Notes

See [`docs/release-notes.md`](docs/release-notes.md).

---

## For developers

The portal is the Vue 3 + Vuetify single-page app behind `/`, served by its own nginx in the
`portal-frontend` container. Its server side is two other services: the builder
([services/builder](../builder/README.md)) at `/api/builder`, and the platform API
([services/api](../api/README.md)) at `/api`.

### Code map

| Path | What it is |
|---|---|
| `frontend/src/views/` | Pages: `home`, `dashboard` (study and clinician dashboards, assays), `catalogue`, `upload-dataset` (the measurement, model, tool and workflow wizards), `tool-plugin` (`/tool-view`, where a GUI tool runs), `tutorial` |
| `frontend/src/router/index.ts` | The routes |
| `frontend/src/bootstrap/` | Keycloak sign-in (`keycloak.ts`), the HTTP clients (`http.ts`) and one module per backend area (`platform_api.ts`, `tool_api.ts`, `workflow_api.ts`, `measurement_api.ts`, `model_api.ts`, `dashboard_api.ts`) |
| `frontend/src/components/` | Shared components, including `RemoteComponentApp.vue`, which mounts a plugin's bundle |
| `frontend/src/composables/`, `store/`, `services/`, `utils/` | Composables, Pinia stores, and helpers |
| `frontend/src/config/platform-links.ts` | The relative links to `/seek` and `/jupyter` |
| `frontend/src/testing/` | Vitest setup, and a Vuetify instance for mounting components in tests |
| `frontend/nginx.conf.template` | portal-frontend's nginx: the SPA, `/api/builder/` → the builder, `/tools/` and `/tool-builds/` → MinIO, and the builder's generated plugin routes |
| `frontend/Dockerfile` | Builds the SPA with Node 20 and Yarn 1, then serves it from `nginx:stable-alpine` |
| `docker-compose.yml` | `portal-frontend`, the only service the platform uses from this file. Its `minio`, `minio-init`, `hapi-fhir` and `hapi-fhir-postgres` are for the standalone stack only |
| `docker-compose.override.yml`, `hapi/` | Standalone stack only: host port 80, and HAPI's configuration |
| `docs/` | [Release notes](docs/release-notes.md), [how the plugin system works](docs/plugin-system-architecture.md), and a [historical deployment guide](docs/deployment-guide.md) |

### Run & test

From the repository root:

```bash
make test-frontend      # vitest: every frontend/src/**/__tests__/**/*.spec.ts
make lint-frontend      # eslint and vue-tsc
docker compose build portal-frontend && docker compose up -d portal-frontend   # rebuild under the platform
```

`make test-frontend` takes no arguments. A change to `frontend/nginx.conf.template` also runs the
builder's tests, which check that template.

### Gotchas

- **The steps under "Deploy locally" above predate the platform** (they name the old
  `DigitalTWINS-Portal` repository). Under the platform, build and start `portal-frontend` from the
  repository root as above. The standalone stack and the platform can't run at the same time: they
  share a container name, a network and port 80.
- **Field names change case on the wire.** The axios interceptors in `bootstrap/http.ts` turn the
  backends' snake_case into camelCase and back, on both clients. The exception is FHIR `descriptions`
  trees sent to the platform API, which pass through untouched.
- **The `VITE_KEYCLOAK_*` values are baked in at build time.** `VITE_KEYCLOAK_URL` is the relative
  `/auth`, so one image works on any host; changing the realm or client means rebuilding the image.
- **Every `proxy_pass` in `nginx.conf.template` goes through a `set` variable**, so a recreated
  builder is found again. The builder's `tests/test_frontend_nginx_template.py` enforces this.

### Related ADRs

- [Serve the platform API at /api; move the portal builder](../../docs/decisions/2026-10-20-api-prefix-and-portal-builder-split.md)
- [Launch a gui assay in /tool-view and hand its input files to the tool](../../docs/decisions/2026-10-05-gui-assay-launch-input-handoff.md)
- [One tag vocabulary for the dataset hub cards](../../docs/decisions/2026-10-12-card-tag-vocabulary.md)
- [Accept SDS-packaged tools in the portal tool wizard](../../docs/decisions/2026-10-01-accept-sds-packages-in-tool-wizard.md)
- [Relicense the portal under Apache 2.0](../../docs/decisions/2026-10-27-relicense-portal-apache-2.md)
