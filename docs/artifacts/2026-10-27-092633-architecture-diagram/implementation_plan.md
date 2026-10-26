# Plan: updated platform architecture diagram + README

## Context

`README.md:46` embeds `docs/images/architecture_diagram.png` (added 2025-11-27, `c68bbda4`). It no longer matches the stack:
- It shows JupyterLab, but the platform now runs JupyterHub.
- It has no gateway, builder, plugin containers, HAPI FHIR route or Grafana.
- It doesn't show which Postgres databases each service owns, the Keycloak OIDC clients, or the optional remote Airflow compute node.

Goal: a maintainable, text-based (Mermaid) architecture doc covering every service and how they connect, and a README that links to it. The old PNG is kept and renamed as legacy.

Decisions from the interview:
- **Format:** Mermaid, which GitHub renders inline.
- **Views:** two, a service-level view and a container-level view.
- **Old PNG:** keep it, rename it as legacy, stop embedding it.
- **README:** a new Architecture section with a short table and a link to the doc.

## Deliverables

### 1. New `docs/architecture.md` (the diagram file)

**Sections:**
1. **Overview.** One paragraph:
   - It is a single Docker Compose project on one bridge network, `${PROJECT_NAME}`.
   - The nginx `gateway` is the only public entry (80/443).
   - Keycloak (realm `digitaltwins`) provides OIDC to every app.
2. **View 1: service level** (Mermaid `flowchart`, UML-component style with «stereotype» labels, tier subgraphs like the old diagram).
   - **Actors:** browser user (researcher/clinician/admin), `digitaltwins` Python SDK/CLI, external DICOM modality, and the optional remote compute node (dashed).
   - **Edge tier:** gateway. Each route edge is labelled with its path: `/`, `/api`, `/api/builder`, `/seek`, `/airflow`, `/jupyter`, `/auth`, `/fhir`, `/minio`, `/orthanc-N`, `/grafana`.
   - **Presentation tier:** portal-frontend, a Vue SPA served by nginx. It proxies `/api/builder`, `/tools`, `/tool-builds` and `/plugin/*`.
   - **Application tier:** api, builder, Airflow, JupyterHub, Keycloak.
   - **Data tier:** Postgres, MinIO, SEEK, HAPI FHIR, PACS (Orthanc ×2).
   - **Outside compose:** plugin containers (started by the builder), per-user notebook containers (started by JupyterHub), Grafana in k3s.
   - **Key edges, each labelled with its protocol or purpose:**
     - **api →** Postgres `public`, MinIO S3, SEEK JSON:API (forwards the user's JWT), Airflow REST (trigger DAG runs), Airflow DAG folder (shared bind mount, dashed), JupyterHub hub API, HAPI FHIR, builder (gui-tool).
     - **builder →** Postgres `portal`, MinIO, api (dataset handoff), HAPI FHIR, Docker socket (plugins), `nginx_plugin_configs` → portal-frontend reload.
     - **Airflow →** Postgres `airflow`, MinIO (data + logs).
     - **Other →** jupyterhub → Docker (spawns notebook containers); external modality → Orthanc DICOM :4242; keycloak and hapi-fhir → Postgres.
     - **Auth:** dashed OIDC edges into Keycloak, kept visually light.
3. **View 2: container level** (Mermaid `flowchart`, one subgraph per compose project, host ports in the labels).
   - **gateway, portal, builder, api:** one container each.
   - **database:** one Postgres container.
   - **keycloak, hapi-fhir:** one container each.
   - **Airflow:** apiserver, scheduler, dag-processor, worker (GPU opt-in), triggerer, redis, init, minio-logs-init. flower and cli are profile-only and shown dashed.
   - **SEEK (submodule):** seek, workers, MySQL `db`, solr. exporter is profile-only and shown dashed.
   - **MinIO:** minio, minio-init.
   - **PACS:** orthanc-1/2 and orthanc-auth-service-1/2.
   - **JupyterHub:** jupyterhub plus the spawned `jupyter-<user>` containers.
4. **Tables.** I'll keep these short and link to existing reference docs instead of duplicating them:
   - **Services:** name, role, image or source dir, gateway path.
   - **Data stores:** Postgres DB/schema → owner service (`digitaltwins.public`→api, `digitaltwins.portal`→builder, `airflow`, `keycloak`, `hapi`); SEEK MySQL and Solr; JupyterHub SQLite; Orthanc storage; MinIO buckets.
   - **Keycloak clients → consumers:** from `services/keycloak/REALM.md`.
   - **Not deployed / legacy:** `services/jupyterlab`, `services/pacs_pretend_external`, `services/irods`, the Gen3/iRODS client code, and the ignored extra services in `services/portal/docker-compose.yml`, plus pgadmin.
   - **Links:** gateway routes in `util/README.md` §7, `docs/gateway-pathway-access.md`, `docs/seek-integration.md`, and the relevant ADRs (builder as its own service, portal DB in platform Postgres, API prefix split, Airflow GPU opt-in, SEEK MySQL 8.4).
5. **Legacy diagram.** One line linking `images/architecture_diagram_legacy.png`, marked "out of date, kept for history (Nov 2025)".

**Accuracy rules:**
- Draw only edges with code or config evidence. The exploration produced a `file:line` for each one.
- Omit edges that are configured but unused: Airflow DAGs → api/keycloak, SEEK's Docker socket mount, notebooks → MinIO.
- api → Orthanc does not exist (no code), so it is not drawn.

### 2. Rename the old PNG

`git mv docs/images/architecture_diagram.png docs/images/architecture_diagram_legacy.png`. `README.md:46` is the only reference outside `docs/artifacts/`, and it gets replaced.

### 3. README.md: Architecture section

- Replace the image at line 46 with a `## Architecture` section:
  - two sentences: gateway, Keycloak SSO, tiers;
  - a compact table: Service | Role | Path. Roughly 12 rows: portal, api, builder, Airflow, JupyterHub, Keycloak, SEEK, MinIO, HAPI FHIR, PACS, Postgres, gateway;
  - "See [docs/architecture.md](docs/architecture.md) for the service and container diagrams."
- Add "Architecture" to the table of contents.
- Leave the rest of the README untouched.

### 4. Agent artifacts (AGENTS.md)

- Create `docs/artifacts/2026-10-27-<HHMMSS>-architecture-diagram/` and copy this plan there as the first implementation step. Plan mode blocks writing it before approval.
- Add a short walkthrough at the end, using repo-relative paths only, with no local ops and no secrets.
- No ADR. Mermaid vs PlantUML is a documentation tooling choice, not an architecture decision.

## Out of scope (I'll mention these, not fix them)

These stale docs turned up during exploration:
- `services/nginx/README.md:133-157` says "Known gaps: none of the platform routes work yet".
- `docs/gateway-pathway-access.md:15` describes the portal as "FastAPI + React".
- `services/portal/docs/plugin-system-architecture.md` shows a SQLite registry box.
- `platform-routes.conf:44-45` has an Airflow "NOT live" note.

## Verification

1. **Mermaid syntax.** Render both diagrams with mermaid-cli (`docker run --rm -v <scratchpad>:/data minlag/mermaid-cli`, or `npx @mermaid-js/mermaid-cli`), extracting the blocks into the scratchpad. Both must render without errors. Then read the PNGs to check layout and legibility.
2. **Completeness.** Cross-check every service and container in the root `docker-compose.yml` and its includes against the diagram:
   `docker compose config --services`, read-only, using `--env-file env.template` or the current `.env` (no `up`).
3. **Links.** Every relative link in `docs/architecture.md` and `README.md` must resolve. A small grep/`test -e` loop is enough.
4. **Secrets.** Run `gitleaks detect --source docs/ --no-git` on the new and changed docs and artifacts.
5. **Containers.** No Docker rebuild is needed, because this is docs only. I'll say so in the summary.
6. Nothing is committed unless you ask.
