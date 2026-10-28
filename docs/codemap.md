# Where code lives and how it connects

A map of the repository for anyone new to it, human or AI agent: which folder
holds which service, where each service's code starts, and how the services are
wired together. It doesn't repeat the diagrams in
[architecture.md](architecture.md). The [service view](architecture.md#service-view)
shows the calls between services, and the
[container view](architecture.md#container-view) shows every container. For
step-by-step traces of the main user journeys see
[request-flows.md](request-flows.md). For terms such as SDS, assay, SOP and
plugin see [glossary.md](glossary.md).

`make docs-check` fails if a folder in `services/` isn't named in this file, so
add a section here when you add a service.

- [Repository top level](#repository-top-level)
- [Services](#services)
- [Inactive and legacy](#inactive-and-legacy)
- [How the compose files fit together](#how-the-compose-files-fit-together)
- [Couplings](#couplings)
- [I want to change X: where do I look?](#i-want-to-change-x-where-do-i-look)

## Repository top level

| Path | What it is |
|---|---|
| [`services/`](../services/) | One folder per service. See [Services](#services). |
| [`docs/`](README.md) | Guides, indexed in [docs/README.md](README.md). [`docs/decisions/`](decisions/) holds the ADRs. [`docs/artifacts/`](artifacts/) holds dated design evidence (plans, task lists, walkthroughs), one folder per change, kept for audit. It is history, not current reference. |
| [`util/`](../util/) | Install, airgap, certificate, backup/restore, sync and SEEK admin scripts, the Ansible playbooks, the observability stack ([`util/observability/`](../util/observability/)), shell helpers ([`util/lib/`](../util/lib/)) and shell tests ([`util/tests/`](../util/tests/)). The runbook is [util/README.md](../util/README.md); every entry is indexed in [util/SCRIPTS.md](../util/SCRIPTS.md). |
| [`examples/`](../examples/) | An example script workflow dataset, [`examples/workflow/workflow_image_conversion/`](../examples/workflow/workflow_image_conversion/), and a sample CWL workflow. |
| [`tests/`](../tests/) | Empty (`.gitkeep`). Each service keeps its own tests. |
| [`.github/`](../.github/) | CI ([`workflows/ci.yml`](../.github/workflows/ci.yml)), a Docker volume backup workflow, and the issue and PR templates. |
| [`.agents/`](../.agents/) | `rules/main.md`, which points the Antigravity agent at [AGENTS.md](../AGENTS.md). |
| [`docker-compose.yml`](../docker-compose.yml) | The whole platform as one Compose project. See [How the compose files fit together](#how-the-compose-files-fit-together). |
| [`Makefile`](../Makefile) | `make test`, `make test-<suite>`, `make lint`, `make docs-check` and `make gitleaks`, each in a pinned container. See [testing.md](testing.md). |
| [`env.template`](../env.template) | The non-secret host inputs: `PLATFORM_PROTOCOL`, `PLATFORM_DOMAIN`, `REMOTE_COMPUTE`, `AIRFLOW_VAR_COMPUTE_QUEUE`, `AIRFLOW_WORKER_GPU`, and the platform admin's username and email. Copy it to `env` (git-ignored) and fill it in. |
| [`secrets.env.template`](../secrets.env.template) | The secret keys the platform needs, with no values. Copy it to `secrets.env` (git-ignored) and fill in every value. |
| [`.env.template`](../.env.template) | The template for the platform's `.env`, with `${VAR}` placeholders. [`util/gen-env.sh`](../util/gen-env.sh) renders `.env` from it, `env`, `secrets.env` and derived values such as `NGINX_MODE`, `SSL`, `AIRFLOW_UID`, `COMPOSE_FILE` and `NODE_IP`. Never hand-edit `.env`; re-run `gen-env.sh`. |
| [`digitaltwins-platform.service`](../digitaltwins-platform.service) | The systemd unit that runs `docker compose up -d` at boot. It reads `COMPOSE_FILE` from `.env`. |
| [`.gitmodules`](../.gitmodules) | One submodule: `services/seek/ldh-deployment`. |
| [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) | The `gitleaks` secret-scanning hook. |
| [`.aiexclude`](../.aiexclude), `.dockerignore`, `.gitignore`, `.gitattributes` | Files that AI tools, Docker builds and git should skip or treat specially. `.aiexclude` keeps `.env` and `secrets.env` away from AI tools. |
| [`AGENTS.md`](../AGENTS.md) | Instructions for AI agents working in this repo. |
| [`README.md`](../README.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), [`LICENSE`](../LICENSE) | Project overview, contribution guide, code of conduct, Apache 2.0 licence. |

## Services

Each section gives the compose service names, the in-network address other
containers use, where the code starts, and where its tests and docs are. The
gateway path is how a browser reaches the service.

### `services/airflow/`

Runs script workflows as Airflow 3 DAGs on Celery workers.

- **Compose:** [`docker-compose.yml`](../services/airflow/docker-compose.yml)
  plus [`network-override.yml`](../services/airflow/network-override.yml), both
  `include`d by the root. Services: `airflow-apiserver` (`airflow-apiserver:8080`:
  the UI, the REST API under `/airflow/api/v2` and the workers' execution API),
  `airflow-scheduler`, `airflow-dag-processor`, `airflow-worker`,
  `airflow-triggerer`, `redis` (the Celery broker), and the one-shot
  `airflow-init` and `minio-logs-init`. `airflow-cli` and `flower` start only
  with their profiles. Gateway path `/airflow`.
- **Image:** [`Dockerfile`](../services/airflow/Dockerfile), based on
  `apache/airflow:3.0.6`. It installs the `digitaltwins` package from PyPI at a
  pinned version, not from `services/api/`, and a `cwl_venv` that DAG tasks run
  their tool code in.
- **Code and config:**
  - [`dags/`](../services/airflow/dags/): the DAG folder. The API writes each
    deployed script workflow to `dags/workflow_<seek_id>/`; don't edit those by
    hand. The two tracked DAGs, `cpu_burn_primes.py` and `workflow_9000.py`,
    are CPU-burn test DAGs.
  - [`config/`](../services/airflow/config/): `airflow.cfg` and
    `webserver_config.py` (UI login through Keycloak, realm roles mapped to
    Airflow roles).
  - [`compute-worker/`](../services/airflow/compute-worker/): the compose file,
    env template and systemd unit for a remote compute node.
  - [`gpu.override.yml`](../services/airflow/gpu.override.yml) and
    [`remote-compute.override.yml`](../services/airflow/remote-compute.override.yml):
    optional overrides, merged through `COMPOSE_FILE`.
- **Tests:** none for DAGs or config. `util/tests/test_compose_file.sh` checks
  the GPU override (`make test-util`).
- **Docs:** [README.md](../services/airflow/README.md),
  [workflow-dag-authoring.md](workflow-dag-authoring.md),
  [compute-node-README.md](../util/compute-node-README.md).

### `services/api/`

The DigitalTWINS REST API (FastAPI), and the `digitaltwins` Python package it is
built on. It ties the platform together: datasets, assays, workflow deploy and
launch, and the SEEK, FHIR, MinIO, Airflow and JupyterHub integrations.

- **Compose:** `api`, from [`docker-compose.yml`](../services/api/docker-compose.yml),
  `include`d by the root. In-network `api:8000`. Gateway path `/api`: the
  gateway strips the prefix and uvicorn runs with `--root-path /api`, so no API
  route may itself start with `/api`.
- **Entry point:** [`app/main.py`](../services/api/app/main.py) (`app.main:app`).
  At startup it applies the Postgres migrations (a failed migration fails
  startup) and fails any ingest job a previous process left mid-flight.
- **Code:**
  - [`app/routers/`](../services/api/app/routers/): one module per resource.
    `datasets.py` (query, one-shot upload, download, delete),
    `dataset_uploads.py` (resumable upload sessions), `dataset_fhir.py`,
    `assays.py` (configure, run, workspace download and submit),
    `dashboard.py` (the portal's study dashboard), `workflows.py` (DAG deploy),
    `programs.py`, `projects.py`, `investigations.py`, `studies.py`, `tools.py`,
    `models.py`, `health.py`, and `auth.py` (token checks and the
    `require_upload_role` and `require_admin_role` guards). `dependencies.py`
    builds a per-request `Querier` that carries the caller's token.
  - [`app/schemas/`](../services/api/app/schemas/): Pydantic request models.
  - [`src/digitaltwins/`](../services/api/src/digitaltwins/): the package.
    - `core/`: the `Querier`, `Uploader`, `Downloader` and `Deleter` facades
      over Postgres, SEEK and MinIO; `keycloak_verifier.py`;
      `assay_workflow_link.py` (the assay-to-workflow SOP link).
    - `seek/`: `querier.py` (reads SEEK as the caller) and `writer.py`
      (registers tools and workflows as RO-Crates, creates SOPs).
    - `postgres/`: queries and inserts, `migrate.py`, `migration_runner.py` and
      the numbered [`migrations/`](../services/api/src/digitaltwins/postgres/migrations/)
      for the `public` schema.
    - `minio/`: S3 upload, download and delete.
    - `airflow/`: `workflow.py`, the Airflow REST client.
    - `workflows/`: workflow dataset ingest, `dag.py` (static DAG checks and the
      DAG folder layout) and `deploy.py` (writes the DAG folder and waits for
      Airflow).
    - `tools/`, `models/`: tool and model dataset ingest (validation, commit,
      FHIR).
    - `measurements/`: upload sessions, the chunk store, SPARC validation, the
      FHIR build and push, and the background commit jobs (`jobs.py`).
    - `jupyterhub/`: `hub.py` (the hub API, as the hub's `api` service) and
      `staging.py` (stages a notebook assay's workspace).
    - `cli/`: `import_dataset.py` (the terminal importer), `keycloak_login.py`,
      `repush_fhir_urls.py`.
    - `client.py`: `UploadClient`, resumable uploads over HTTP.
    - `resources/`: the SDS dictionary and the SDS-to-Postgres element mappings.
    - `gen3/`, `irods/`: present but not configured.
  - [`scripts/`](../services/api/scripts/): `import-dataset.sh`, `.command`,
    `.ps1` and `.bat`, which copy a dataset into the `api` container and run the
    importer.
  - [`tutorials/`](../services/api/tutorials/), [`examples/`](../services/api/examples/):
    using the package as a library.
- **Tests:** [`tests/`](../services/api/tests/), `make test-api`. Tests that
  need a live Postgres or MinIO are marked `integration` and are deselected.
- **Docs:** [README.md](../services/api/README.md),
  [docs/import-dataset.md](../services/api/docs/import-dataset.md).

### `services/builder/`

Builds and deploys the portal's tools, GUI workflows' tools and plugins. It is
the only service that runs untrusted build code against the host Docker socket,
so it is kept apart from the API
([ADR](decisions/2026-10-21-builder-as-its-own-service.md)).

- **Compose:** `builder`. The root defines it by `extends` of
  [`docker-compose.yml`](../services/builder/docker-compose.yml) and adds the
  `BUILDER_DB_*` settings and the dependency on `database`. In-network
  `builder:8000`. Gateway path `/api/builder`, which the gateway hands to
  `portal-frontend`, whose nginx proxies it to the builder.
- **Entry point:** [`app/main.py`](../services/builder/app/main.py)
  (`app.main:app`). Startup creates or migrates its tables and reconciles
  deployed plugins with the containers actually running; shutdown stops every
  plugin backend it started.
- **Code:**
  - [`app/router/`](../services/builder/app/router/): `workflow_tool_plugin.py`
    (`/api/builder/tools/...`) and `workflow_router.py` (`/api/builder/workflow/...`).
  - [`app/engine/`](../services/builder/app/engine/): `build_tool.py` and
    `build_workflow.py` (source acquisition, Vite patching, npm/yarn builds,
    SPARC datasets), `deploy_tool.py` (`docker compose` deploys, plugin nginx
    routes and the nginx reload), live log streaming.
  - [`app/services/`](../services/builder/app/services/): the approval handoff,
    which uploads a build to the API as the approving user.
  - [`app/models/db_model.py`](../services/builder/app/models/db_model.py) and
    [`app/database/`](../services/builder/app/database/): the `portal` schema
    and its numbered SQL migrations.
  - [`app/client/`](../services/builder/app/client/): Keycloak, MinIO and HAPI
    FHIR clients. `keycloak_verifier.py` is a verbatim copy of the API's.
  - [`app/utils/`](../services/builder/app/utils/): `auth.py` (token and role
    checks), `workflow_tool_utils.py` (`run_deployment`).
  - [`app/cli/`](../services/builder/app/cli/): one-off commands.
- **Tests:** [`tests/`](../services/builder/tests/), `make test-builder`. Never
  run them inside the live `builder` container: they drop and recreate every
  table.
- **Docs:** [README.md](../services/builder/README.md),
  [plugin-system-architecture.md](../services/portal/docs/plugin-system-architecture.md).

### `services/hapi-fhir/`

HAPI FHIR R4 server for clinical metadata: measurement annotations, models as
`Device`, tools as `ActivityDefinition`, workflows as `PlanDefinition`.

- **Compose:** `hapi-fhir` (container name `hapi-fhir`), defined in the root by
  `extends` of [`docker-compose.yml`](../services/hapi-fhir/docker-compose.yml).
  In-network `hapi-fhir:8080`. Gateway path `/fhir`.
- **Config:** [`application.yaml`](../services/hapi-fhir/application.yaml).
  The compose file's `SPRING_DATASOURCE_*` settings override its datasource to
  use the shared Postgres `hapi` database. `HealthCheck.class` is the
  container's health check.
- **Code and tests:** none of its own; the API and builder are its clients.
- **Docs:** [README.md](../services/hapi-fhir/README.md).

### `services/jupyterhub/`

Interactive analysis: one notebook server per user, and the place notebook
assays are staged.

- **Compose:** [`docker-compose.yml`](../services/jupyterhub/docker-compose.yml),
  `include`d by the root. `jupyterhub` (fixed container name
  `digitaltwins-platform-jupyterhub`, in-network port 8000) and `singleuser`,
  which only builds the per-user image and exits. Gateway path `/jupyter`. It
  mounts the Docker socket for DockerSpawner.
- **Config:** [`jupyterhub_config.py`](../services/jupyterhub/jupyterhub_config.py):
  Keycloak login (`GenericOAuthenticator`, client `jupyterhub`), DockerSpawner,
  `base_url` `/jupyter/`, and the `api` service whose token is
  `JUPYTERHUB_API_TOKEN`. Images: [`Dockerfile`](../services/jupyterhub/Dockerfile)
  (hub) and [`Dockerfile.singleuser`](../services/jupyterhub/Dockerfile.singleuser).
- **Tests:** [`tests/`](../services/jupyterhub/tests/), `make test-jupyterhub`.
- **Docs:** [README.md](../services/jupyterhub/README.md).

### `services/keycloak/`

Identity and access management (OIDC), realm `digitaltwins`.

- **Compose:** `keycloak`, from [`docker-compose.yml`](../services/keycloak/docker-compose.yml),
  `include`d by the root. In-network `keycloak:8080`, served under `/auth`
  (`KC_HTTP_RELATIVE_PATH`). Gateway path `/auth`. It stores its data in the
  shared Postgres `keycloak` database.
- **Config:** [`digitaltwins-realm.json.template`](../services/keycloak/digitaltwins-realm.json.template).
  [`util/gen-realm.sh`](../util/gen-realm.sh) renders it into `import/`
  (git-ignored), and Keycloak imports it on first boot only.
  [`digitaltwins-login-theme/`](../services/keycloak/digitaltwins-login-theme/)
  is the login page theme.
- **Tests:** none.
- **Docs:** [README.md](../services/keycloak/README.md),
  [REALM.md](../services/keycloak/REALM.md) (clients, secrets, roles, groups, users).

### `services/minio/`

S3 object storage for datasets, tool bundles, assay workspaces and Airflow logs.

- **Compose:** [`docker-compose.yml`](../services/minio/docker-compose.yml),
  `include`d by the root. `minio` (in-network S3 at `minio:9000`, console at
  `minio:9001`) and the one-shot `minio-init`. Gateway path `/minio` (the
  console only). The console signs in through Keycloak (client `minio`).
- **Code:** [`init-minio.sh`](../services/minio/init-minio.sh) creates the
  buckets `measurements`, `models`, `workflows`, `tools` (public),
  `tool-builds` (anonymous download) and `airflow-workspace`. Airflow's
  `minio-logs-init` creates `airflow-logs`.
- **Tests:** none.
- **Docs:** [README.md](../services/minio/README.md).

### `services/nginx/`

The edge gateway: the only public entry (ports 80 and 443), TLS termination and
path routing.

- **Compose:** `gateway` (container `${PROJECT_NAME}-gateway`), defined in the
  root by `extends` of [`docker-compose.yml`](../services/nginx/docker-compose.yml).
  Stock `nginx` image with bind-mounted config: change a route with
  `nginx -t` and `nginx -s reload`, no rebuild. It has the network alias
  `${PLATFORM_DOMAIN}`, so containers that resolve the public host name reach
  the gateway.
- **Config:** [`conf/http/`](../services/nginx/conf/http/) and
  [`conf/ssl/`](../services/nginx/conf/ssl/) are server shells, picked by
  `NGINX_MODE`. Both include [`snippets/`](../services/nginx/snippets/):
  `platform-routes.conf` (every platform route), `portal-fallback.conf` and
  `portal-proxy.conf` (everything else goes to `portal-frontend`) and
  `http-level.conf`. `gen-env.sh` also writes `snippets/minio-discovery.json`,
  the OIDC discovery document MinIO reads. Certificates go in `certs/`
  (git-ignored contents); `acme/` is the Let's Encrypt webroot.
- **Tests:** none; check a change with `nginx -t`.
- **Docs:** [README.md](../services/nginx/README.md),
  [gateway-pathway-access.md](gateway-pathway-access.md),
  [util/README.md §7](../util/README.md#7-gateway-proxy-routes-reference).

### `services/pacs/`

Medical imaging: two Orthanc PACS instances that de-identify DICOM on receipt.

- **Compose:** [`docker-compose.yml`](../services/pacs/docker-compose.yml),
  `include`d by the root. `orthanc-1` and `orthanc-2` (in-network web on 8042,
  DICOM on 4242), each with an `orthanc-auth-service-1` or `-2` that signs in
  to Keycloak with the `admin-cli` service account. Gateway paths `/orthanc-1`
  and `/orthanc-2`.
- **Code and config:** [`Dockerfile`](../services/pacs/Dockerfile),
  [`orthanc.json`](../services/pacs/orthanc.json),
  [`permissions.json`](../services/pacs/permissions.json), and
  [`scripts/deidentification.py`](../services/pacs/scripts/deidentification.py),
  the Orthanc Python plugin that de-identifies each instance before it is
  stored.
- **Tests:** [`tests/`](../services/pacs/tests/) are scripts run by hand
  against a running Orthanc; they are not part of `make test`.
- No platform code calls Orthanc. Users reach it through the gateway, and DICOM
  modalities send to its DICOM port.
- **Docs:** [README.md](../services/pacs/README.md).

### `services/portal/`

The web portal: a Vue 3 single-page app, served by an nginx that also proxies
the builder, the public tool buckets and the plugin backends.

- **Compose:** `portal-frontend` (container `${PROJECT_NAME}-portal-frontend`),
  defined in the root by `extends` of
  [`docker-compose.yml`](../services/portal/docker-compose.yml). In-network
  `portal-frontend:80`. Gateway path `/`, which also carries `/api/builder`,
  `/tools`, `/tool-builds` and `/plugin/*`. The Keycloak settings
  (`VITE_KEYCLOAK_URL=/auth`, realm, client `portal-frontend`) are build
  arguments, baked into the image.
- **Entry point:** [`frontend/src/main.ts`](../services/portal/frontend/src/main.ts)
  initialises Keycloak, then mounts the app.
- **Code** (under [`frontend/src/`](../services/portal/frontend/src/)):
  - `bootstrap/`: `keycloak.ts` (sign-in, token refresh, idle timeout),
    `http.ts` (axios clients that add the bearer token: the default one for
    `/api/builder`, `dtApiAxios` for `/api`), and one `*_api.ts` client per area.
  - `router/index.ts`: routes and their `requiresAuth` / `requiresRoles` meta.
  - `views/`: `dashboard/` (study and clinician dashboards, assay config and
    launch), `catalogue/`, `upload-dataset/` (the measurements, models, tools
    and workflows hubs), `tool-plugin/` (`/tool-view`, where GUI tools run),
    `home/`, `tutorial/`.
  - `components/`, `composables/`, `store/`, `services/`, `models/`, `utils/`.
    `components/RemoteComponentApp.vue` loads a plugin's UMD bundle.
  - [`frontend/nginx.conf.template`](../services/portal/frontend/nginx.conf.template):
    the portal nginx (`/api/builder` to the builder, `/tools/` and
    `/tool-builds/` to MinIO, and `include` of the generated plugin routes).
- **Tests:** `__tests__/` folders beside the code (Vitest), `make test-frontend`;
  `make lint-frontend` for eslint and vue-tsc.
- **Docs:** [README.md](../services/portal/README.md) (using the study
  dashboard), [docs/](../services/portal/docs/).

### `services/postgres/`

The shared PostgreSQL 16 database.

- **Compose:** `database`, defined in the root by `extends` of
  [`docker-compose.yml`](../services/postgres/docker-compose.yml). In-network
  `database:5432`. No gateway path.
- **Init scripts**, run only when the data volume is empty:
  [`digitaltwins_schema.sql`](../services/postgres/digitaltwins_schema.sql)
  (the baseline `public` schema; later changes are the API's migrations),
  `airflow_init.sql`, `keycloak_init.sql`, `hapi_init.sql` (their databases and
  roles), and [`portal_init.sh`](../services/postgres/portal_init.sh) (the
  builder's `portal` role and schema; run it by hand on an existing volume).
- **Databases:** `digitaltwins` (schema `public` for the API, `portal` for the
  builder), `airflow`, `keycloak`, `hapi`. See
  [architecture.md](architecture.md#data-stores).
- **Tests:** none of its own. The API's integration tests load the baseline
  schema.
- **Docs:** [README.md](../services/postgres/README.md).

### `services/seek/`

The data catalogue: SEEK, as the NFDI4Health Local Data Hub (LDH).

- **Compose:** [`ldh-deployment/`](../services/seek/ldh-deployment/) is a git
  submodule; the root `include`s its `docker-compose.yml` plus
  [`network-override.yml`](../services/seek/network-override.yml). Services:
  `seek` (in-network `seek:3000`, mounted at `/seek`), `workers`, `db`
  (MySQL 8.4), `solr`, and `exporter` (profile only). Gateway path `/seek`.
  SEEK's container settings also come from the submodule's
  `docker-compose.env`, rendered separately from `MYSQL_*` secrets.
- **Code:** the Keycloak glue lives in the submodule: `keycloak_jwt_auth.rb`
  (verifies the JWTs the API forwards and provisions users) and
  `keycloak_oidc.rb` (browser login).
- **Changing it:** change the submodule's own repo first, then bump the pointer
  here. See [util/README.md](../util/README.md#working-with-the-submodule-seek).
- **Docs:** [README.md](../services/seek/README.md),
  [seek-integration.md](seek-integration.md).

## Inactive and legacy

None of these start with the platform.

### `services/irods/`

An empty placeholder (`.gitkeep`). The API's iRODS client
(`src/digitaltwins/irods/`) is still in the package, and the `IRODS_*`
settings in `.env.template` are commented out. See its [README](../services/irods/README.md).

### `services/jupyterlab/`

A single-user JupyterLab, replaced by JupyterHub. Its `include` in the root
`docker-compose.yml` is commented out. See its [README](../services/jupyterlab/README.md).

### `services/pacs_pretend_external/`

An Orthanc stand-in for an external PACS, for testing DICOM transfers. Its
`include` in the root `docker-compose.yml` is commented out. See its
[README](../services/pacs_pretend_external/README.md).

### Other leftovers

| What | Why it doesn't run |
|---|---|
| [`services/api/docker/`](../services/api/docker/) (`orthanc/` and `postgres/` compose files) | Old standalone stacks for the API; nothing in the platform references them. |
| `minio`, `minio-init`, `hapi-fhir` and `hapi-fhir-postgres` in [`services/portal/docker-compose.yml`](../services/portal/docker-compose.yml), and [`services/portal/hapi/`](../services/portal/hapi/) | The portal's standalone dev stack. The root `extends` only `portal-frontend`. |
| [`services/portal/docker-compose.override.yml`](../services/portal/docker-compose.override.yml) | Publishes port 80 for the standalone portal. `extends` reads only the file it names, so the platform never loads it. |
| `pgadmin` in [`services/postgres/docker-compose.yml`](../services/postgres/docker-compose.yml) | The root `extends` only `database`. |
| [`services/keycloak/docker-compose-https.yml`](../services/keycloak/docker-compose-https.yml) | Keycloak serving TLS itself. Nothing references it; Keycloak now sits behind the gateway. |
| [`services/api/.env.template`](../services/api/.env.template) | An older copy of the root `.env.template` that has drifted (it lacks newer keys such as `BUILDER_URL`). The platform renders only the root `.env`. |
| `src/digitaltwins/gen3/` in the API | Gen3 support. The `GEN3_*` settings are commented out. |

## How the compose files fit together

The root [`docker-compose.yml`](../docker-compose.yml) builds one Compose
project from the service folders in two ways:

- **`extends`** for `gateway`, `builder`, `portal-frontend`, `hapi-fhir` and
  `database`. `extends` copies one named service from another file and ignores
  the rest of that file, which is why the extra services in the portal and
  postgres files never start. The root can add to an extended service: it gives
  `builder` its `BUILDER_DB_*` settings and its dependency on `database`. Named
  volumes those services use are declared in the root.
- **`include`** for Keycloak, Airflow, SEEK, MinIO, PACS, the API and
  JupyterHub. Each `include` sets `project_directory` to the service folder, so
  relative paths in that file resolve there. For example, the API's
  `../airflow/dags` mount is `services/airflow/dags`.

All containers join one bridge network named `${PROJECT_NAME}`. Every compose
file declares it (`networks: digitaltwins-platform: name: ${PROJECT_NAME}`). The
Airflow and SEEK compose files come from upstream, so their
`network-override.yml` files attach each of their services to it. Containers
find each other by compose service name (`api`, `builder`, `database`,
`keycloak`, `minio`, `hapi-fhir`, `airflow-apiserver`, `redis`, `seek`,
`portal-frontend`, `orthanc-1`, ...). A few fixed container names matter too:
the builder reloads nginx in `${PROJECT_NAME}-portal-frontend`, and the API's
default hub address uses `digitaltwins-platform-jupyterhub`.

There is one `.env`, at the root, rendered by `util/gen-env.sh`; no service
folder has its own. It also sets `COMPOSE_FILE`, which decides the files the
stack merges. [`util/lib/compose-file.sh`](../util/lib/compose-file.sh) adds
[`services/airflow/remote-compute.override.yml`](../services/airflow/remote-compute.override.yml)
when `REMOTE_COMPUTE=true` (it publishes Redis for a remote worker), and
[`services/airflow/gpu.override.yml`](../services/airflow/gpu.override.yml)
when `AIRFLOW_WORKER_GPU` resolves to `true` (it gives the Airflow worker the
host GPU). A `COMPOSE_FILE` set in the `env` file wins. Because the systemd unit
and manual `docker compose` commands both read `.env`, they merge the same
files.

## Couplings

Settings and files that two or more services must agree on. Only names are
given here; values live in `env`, `secrets.env` and the rendered `.env`.

| From | To | Mechanism | Set in | What breaks if it's wrong |
|---|---|---|---|---|
| gateway | every user-facing service | Path routes to compose service names, resolved per request (`set $var` plus Docker DNS). `/api/` strips its prefix; `/api/builder/` and everything unmatched go to `portal-frontend`. | `services/nginx/snippets/platform-routes.conf`, `portal-fallback.conf`, `portal-proxy.conf` | A wrong name or port gives a 502 on that route. A literal `proxy_pass` host stops nginx starting when that service is down. See [services/nginx/README.md](../services/nginx/README.md). |
| gateway | each app's path prefix | Each app is told its prefix: `RAILS_RELATIVE_URL_ROOT` (SEEK), `AIRFLOW__API__BASE_URL`, `c.JupyterHub.base_url`, `KC_HTTP_RELATIVE_PATH`, uvicorn `--root-path /api` | each service's compose file or config | 404s, or redirects that escape to `/`. Changing a prefix needs the app restarted, not just nginx reloaded. |
| every OIDC client | Keycloak issuer | `KC_HOSTNAME`, `KEYCLOAK_PUBLIC_URL` and `ORTHANC_KEYCLOAK_URL` name the same public `/auth` address, all derived from `PLATFORM_PROTOCOL` and `PLATFORM_DOMAIN` | `.env.template` | Issuer mismatch: logins and token checks fail across the platform. |
| each service | its Keycloak client | Client id plus a secret variable that must match the realm import (for example `KEYCLOAK_CLIENT_SECRET` for `api`, `JUPYTERHUB_CLIENT_SECRET`, `AIRFLOW_KEYCLOAK_CLIENT_SECRET`) | `secrets.env`, `services/keycloak/digitaltwins-realm.json.template` | That service's login fails. The realm is imported on first boot only. See [architecture.md](architecture.md#keycloak-clients) and [REALM.md](../services/keycloak/REALM.md). |
| portal (browser) | Keycloak | Public client `portal-frontend`; `VITE_KEYCLOAK_URL`, `VITE_KEYCLOAK_REALM`, `VITE_KEYCLOAK_CLIENT_ID` | `services/portal/docker-compose.yml` (build arguments) | Baked in at build time: rebuild the image after changing them. |
| api | Keycloak | `KEYCLOAK_BASE_URL` (internal), `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`. Accepts tokens issued to `portal-frontend` or `api` only. | `services/api/docker-compose.yml`, `.env` | 503 when Keycloak is unreachable; 401 for other clients' tokens; Basic auth and `/login` fail if the secret is wrong. |
| api | postgres | `POSTGRES_HOST` (`database`), `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `services/api/docker-compose.yml`, `.env` | The API fails to start: it runs its migrations at startup. |
| api | SEEK | `SEEK_BASE_URL` (`http://seek:3000/seek`); every call forwards the caller's Keycloak JWT, which SEEK verifies (client `seek`) | `services/api/docker-compose.yml`; `keycloak_jwt_auth.rb` in the submodule | Empty dashboards or 401s. Users see only what their SEEK user may see. See [seek-integration.md](seek-integration.md). |
| api | Airflow | `AIRFLOW_ENDPOINT` (token from `/auth/token`, DAG runs at `/api/v2/dags/{id}/dagRuns`); `AIRFLOW_API_URL` (required by the package's Airflow client, used by DAG deploy); `AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD`, the local Airflow user that `airflow-init` creates from the same variables; `AIRFLOW__API__BASE_URL` for monitor links | `services/api/docker-compose.yml`, `services/airflow/docker-compose.yml` | Assay launch returns 503; DAG deploy fails. |
| api | Airflow DAG folder | Bind mount `../airflow/dags` at `/airflow-dags` (`AIRFLOW_DAGS_DIR`); Airflow mounts the same folder. The DAG processor rescans every 30 s; the API waits up to `AIRFLOW_DAG_DEPLOY_TIMEOUT`. | `services/api/docker-compose.yml`, `services/airflow/docker-compose.yml` | Deploys fail or time out. The DAG id must equal its folder name, `workflow_<seek_id>`. |
| api | builder | `BUILDER_URL`; `GET /api/builder/workflow/gui-tool` as the caller | `services/api/docker-compose.yml`, `.env` | GUI assays can't launch (502 "Builder unreachable"). |
| builder | api | `API_BASE_URL` and `API_PORT`; approval uploads through `/datasets/uploads` as the approving user | `services/builder/docker-compose.yml`, `.env` | Tool and workflow approvals stall. |
| api, builder | HAPI FHIR | `FHIR_ENDPOINT` (`hapi-fhir:8080/fhir`); the API also uses `API_PUBLIC_URL` in FHIR file links | both compose files, `.env` | `fhir_status` goes to `failed`; FHIR links point to the wrong host. |
| api | JupyterHub | `JUPYTERHUB_API_TOKEN` must be the same on both sides: the hub registers it for its `api` service (admin role), the API sends it. The API reaches the hub at `JUPYTERHUB_INTERNAL_URL`, by default the hub's fixed container name. | `secrets.env`, both compose files, `jupyterhub_config.py` | Compose refuses to start without it; a mismatch makes notebook assays fail. |
| api, builder, Airflow | MinIO | Clients sign in with `MINIO_SERVER_ACCESS_KEY` and `MINIO_SERVER_SECRET_KEY` (the builder and Airflow get them as `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`; Airflow logging as `AIRFLOW_CONN_MINIO_LOGS`). MinIO accepts only `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`, and `init-minio.sh` creates no other user. | `.env.template`, `secrets.env` | If `MINIO_SERVER_SECRET_KEY` differs from `MINIO_ROOT_PASSWORD` (or the access key from `MINIO_ROOT_USER`), every S3 call returns 403: uploads, assay runs, Airflow logs. |
| builder | postgres | `BUILDER_DB_HOST`, `BUILDER_DB_PORT`, `BUILDER_DB_NAME`, `BUILDER_DB_USER` (`portal`), `BUILDER_DB_PASSWORD`; schema `portal`. Set only in the root compose. `portal_init.sh` creates the role from the same password. | root `docker-compose.yml`, `services/postgres/portal_init.sh`, `secrets.env` | Without them the builder falls back to SQLite on its volume. A password mismatch stops it connecting; on an existing volume, run `05_portal.sh` by hand. |
| Airflow, Keycloak, HAPI FHIR | postgres | Their own databases (`airflow`, `keycloak`, `hapi`), created by `services/postgres/*_init.sql` on first initialisation. Airflow connects with `AIRFLOW_DB_*`, Keycloak with `KEYCLOAK_DB_*`, HAPI as `POSTGRES_USER`. | `services/postgres/`, each service's compose file | `airflow_init.sql` and `keycloak_init.sql` create their roles with fixed passwords, not from these variables. Unclear how an install that sets other values reconciles them. |
| builder | Docker socket | `/var/run/docker.sock` mounted in the builder (and in JupyterHub, for DockerSpawner), never in the API | `services/builder/docker-compose.yml` | Builds and deploys fail. Mounting it in the API breaks the security boundary; `tests/test_service_separation.py` checks this. |
| builder | (none: separation) | The builder's environment must hold none of the API's credentials (`POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*`, `API_PUBLIC_URL`, `KEYCLOAK_CLIENT_SECRET`), because plugin builds and plugin compose files see it | `services/builder/docker-compose.yml`, root `docker-compose.yml` | `services/builder/tests/test_service_separation.py` fails; in production, untrusted plugin code could read them. |
| builder | api (code) | Verbatim copies: `app/database/migration_runner.py` and `app/client/keycloak_verifier.py` must equal the API's `postgres/migration_runner.py` and `core/keycloak_verifier.py` | both files | `services/builder/tests/test_shared_with_api.py` fails. Change both together. |
| builder | portal-frontend | Shared volume `nginx_plugin_configs` (builder `/nginx-plugins-conf`, portal `/etc/nginx/conf.d/plugins`); the builder writes `<expose>.conf` and runs `docker exec` on `NGINX_CONTAINER_NAME` (`${PROJECT_NAME}-portal-frontend`) to reload nginx | builder and portal compose files | `/plugin/<expose>/` returns 404, or the new route isn't loaded. |
| portal-frontend | builder | `/api/builder/` (and the upload and log-stream locations) proxied to `builder:${BUILDER_PORT}` | `services/portal/frontend/nginx.conf.template` | Every Tool Hub and workflow builder call fails. `services/builder/tests/test_frontend_nginx_template.py` checks the template. |
| portal-frontend | MinIO | `/tools/` and `/tool-builds/` proxied to `minio:9000` (anonymous-read buckets) | `nginx.conf.template`, `services/minio/init-minio.sh` | Plugin bundles don't load in the browser. |
| Airflow DAGs | Keycloak, api | DAGs can get a client-credentials token as client `api` (`KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`) and call the API (`API_BASE_URL`, `API_PORT`) | `services/airflow/docker-compose.yml` | DAG tasks that call the API get 401s. |

## I want to change X: where do I look?

Run tests through the `make` targets, which use throwaway containers. Never run
them inside a live container: the builder's tests drop and recreate every table.

| I want to... | Edit | Check with | Read |
|---|---|---|---|
| Add or change an API endpoint | A router in [`services/api/app/routers/`](../services/api/app/routers/) (register a new one in [`app/main.py`](../services/api/app/main.py)); request models in `app/schemas/`; logic in `src/digitaltwins/`. Guard it with `validate_credentials`, `require_upload_role` or `require_admin_role`. | `make test-api`, with a new `tests/test_<area>_api.py` | [services/api/README.md](../services/api/README.md), [ADR: API prefix](decisions/2026-10-20-api-prefix-and-portal-builder-split.md) |
| Add a migration to the API's `public` schema | Add the next `NNNN_<name>.sql` to [`src/digitaltwins/postgres/migrations/`](../services/api/src/digitaltwins/postgres/migrations/). Never edit one that has shipped. The API applies it at startup. | `make test-api` (`tests/test_migrate.py`); integration tests need a live Postgres | [ADR: platform schema migrations](decisions/2026-09-28-platform-schema-migrations.md) |
| Add a migration to the builder's `portal` schema | Change [`app/models/db_model.py`](../services/builder/app/models/db_model.py) and add the next file to [`app/database/migrations/`](../services/builder/app/database/migrations/), names qualified with `portal.` | `make test-builder`; run `tests/test_postgres_integration.py` by hand against a throwaway `postgres:16` | [builder README](../services/builder/README.md#database-migrations), [ADR](decisions/2026-10-21-builder-numbered-sql-migrations.md) |
| Add a portal page or component | A view in [`frontend/src/views/`](../services/portal/frontend/src/views/), registered in [`src/router/index.ts`](../services/portal/frontend/src/router/index.ts) with `requiresAuth` / `requiresRoles`; API calls in `src/bootstrap/*_api.ts` | `make test-frontend` (specs in `__tests__/`), `make lint-frontend` | [services/portal/README.md](../services/portal/README.md) |
| Change a gateway route | [`services/nginx/snippets/platform-routes.conf`](../services/nginx/snippets/platform-routes.conf) (TLS and domain: `conf/ssl/default.conf`). A prefix change also needs the app's own setting. | `nginx -t` in the gateway container, then `nginx -s reload` | [services/nginx/README.md](../services/nginx/README.md), [gateway-pathway-access.md](gateway-pathway-access.md) |
| Write or deploy a script workflow DAG | The workflow dataset's `code/` folder, with `dag_id` = `Path(__file__).parent.name`. Deploy from the portal or `POST /api/workflows/{dataset_uuid}/deploy`. Never edit `services/airflow/dags/workflow_<id>/` by hand. | Run the DAG locally from any folder; the deploy's static checks are in `src/digitaltwins/workflows/dag.py` (`tests/test_workflow_dag.py`) | [workflow-dag-authoring.md](workflow-dag-authoring.md), [the example](../examples/workflow/workflow_image_conversion/), [ADR](decisions/2026-10-13-deploy-script-workflow-dags.md) |
| Change how an assay launches | [`app/routers/assays.py`](../services/api/app/routers/assays.py) (`run_assay`, `_discover_samples`, `_trigger_dag`), [`app/routers/dashboard.py`](../services/api/app/routers/dashboard.py) (`launch_assay`), `src/digitaltwins/jupyterhub/staging.py` | `make test-api` (`tests/test_assay_*.py`, `tests/test_dashboard_api.py`) | [request-flows.md](request-flows.md#launch-an-assay), [ADR: GUI launch](decisions/2026-10-05-gui-assay-launch-input-handoff.md), [ADR: notebook staging](decisions/2026-10-16-stage-notebook-assay-workspace.md) |
| Change dataset upload or import | [`app/routers/dataset_uploads.py`](../services/api/app/routers/dataset_uploads.py), `app/routers/datasets.py`; `src/digitaltwins/measurements/`, `tools/`, `workflows/`, `models/`; the importer `src/digitaltwins/cli/import_dataset.py` | `make test-api` (`tests/test_dataset_uploads_*.py`, `tests/test_import_dataset_cli.py`) | [import-dataset.md](../services/api/docs/import-dataset.md), [ADR: unified ingest](decisions/2026-09-28-unified-dataset-ingest-in-digitaltwins-api.md) |
| Change FHIR annotations | `src/digitaltwins/measurements/fhir_service.py`, `tools/fhir.py`, `workflows/fhir.py`, `models/fhir.py`; [`app/routers/dataset_fhir.py`](../services/api/app/routers/dataset_fhir.py) | `make test-api` (`tests/test_*fhir*.py`) | [ADR: model Device](decisions/2026-10-12-model-fhir-device.md) |
| Change the Keycloak realm (clients, roles, mappers) | [`services/keycloak/digitaltwins-realm.json.template`](../services/keycloak/digitaltwins-realm.json.template), then `util/gen-realm.sh`. The import runs on first boot only: also apply the change live, or re-import into an empty Keycloak database. | no unit test | [REALM.md](../services/keycloak/REALM.md), [development.md](development.md#change-type-playbook) |
| Change the SEEK integration | API side: `src/digitaltwins/seek/querier.py`, `writer.py`, `core/assay_workflow_link.py`. SEEK side: the [`ldh-deployment`](../services/seek/ldh-deployment/) submodule; change its repo first, then bump the pointer. | `make test-api` (`tests/test_seek_writer.py`, `tests/test_assay_workflow_link.py`) | [seek-integration.md](seek-integration.md), [ADR: SOP link](decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md) |
| Change how GUI tools or plugins build and deploy | [`services/builder/app/engine/`](../services/builder/app/engine/) (`build_tool.py`, `deploy_tool.py`), [`app/router/workflow_tool_plugin.py`](../services/builder/app/router/workflow_tool_plugin.py); portal side `src/bootstrap/tool_api.ts`, `src/components/RemoteComponentApp.vue` | `make test-builder`, `make test-frontend` | [builder README](../services/builder/README.md), [plugin-system-architecture.md](../services/portal/docs/plugin-system-architecture.md) |
| Add an environment variable or secret | [`.env.template`](../.env.template), and [`env.template`](../env.template) (host inputs) or [`secrets.env.template`](../secrets.env.template) (secrets); pass it in the service's compose file. Never give the builder an API credential. | Run `util/gen-env.sh`: it fails on a placeholder with no value. `make test-builder` if the builder's environment changed. | [development.md](development.md#change-type-playbook) |
| Add a util script | Add it to [`util/`](../util/) and name it, in backticks, in [`util/SCRIPTS.md`](../util/SCRIPTS.md) | `make docs-check` fails if it isn't listed; shell tests go in `util/tests/` (`make test-util`) | [util/README.md](../util/README.md) |
| Add a service | `services/<name>/docker-compose.yml` on the `${PROJECT_NAME}` network; `include` (or `extends`) it in the root [`docker-compose.yml`](../docker-compose.yml); a gateway route and a Keycloak client if users reach it; its variables in the templates. Add a section to this file and update [architecture.md](architecture.md). | `make docs-check` fails until this file names the folder | [architecture.md](architecture.md), [ADR template](decisions/TEMPLATE.md) |
