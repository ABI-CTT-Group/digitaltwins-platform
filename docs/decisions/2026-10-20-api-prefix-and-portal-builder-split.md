# Serve the platform API at /api; move the portal builder to /api/portal

- **Date:** 2026-10-20
- **Status:** Accepted. Superseded in part by [2026-10-20-merge-portal-backend-into-api-codebase](2026-10-20-merge-portal-backend-into-api-codebase.md): the builder moved into the API's codebase as the `builder` service (Option D below), at `/api/builder`.

## Context

The platform REST API (`services/api`) was published at `/digitaltwins-api`, and its compose service, Docker DNS host, JupyterHub service and env vars (`DIGITALTWINS_API_*`) carried the same name. We want the shorter `/api` and the name `api` everywhere.

`/api/` was already owned by the portal backend. Its paths were:

- `/api/dashboard`: mostly a proxy to the API that reshapes responses.
- `/api/tools` and `/api/workflow`: the plugin/workflow builder. It needs `docker.sock`, Node and git, runs untrusted plugin builds, and has its own `portal.*` tables.
- Several unused login/auth/test/report-viewer routes.

The API's `GET /tools` would collide directly with the portal's `/api/tools/...`, and the API's `POST /login` with the portal's `POST /api/login`.

FHIR resources pushed to HAPI store absolute file URLs built from the API's public URL (`.../digitaltwins-api/datasets/<uuid>/files/primary/...`). The same URLs are also stored in `dataset_fhir_annotation` and in `fhir.json` in MinIO.

## Alternatives Considered

### Option A: API at /api/v1, portal keeps /api/*
- Pros: no portal changes; adds versioning.
- Cons: not the `/api` that was asked for; two services stay interleaved under `/api`.

### Option B: share /api by path (nginx routes each sub-path to its owner)
- Pros: no code moves.
- Cons: fragile; `/tools` and `/login` still clash and need renaming anyway.

### Option C: move all portal-backend code into the API container
- Pros: one service behind `/api`.
- Cons: the API container would get `docker.sock` (host root). Plugin builds would run with the API's environment, which holds the Postgres superuser password, the Keycloak client secret and the JupyterHub/Airflow credentials. It would also merge two DB/migration systems.

### Option D: same codebase, two containers
- Pros: isolates privileges.
- Cons: a large move for no routing benefit; the builder still needs its own prefix.

### Option E (chosen): move only the dashboard into the API; builder at /api/portal
- Pros:
  - The API gets a clean `/api`.
  - The dashboard's proxy hop disappears.
  - The privileged builder stays isolated.
  - Each route has exactly one owner.
- Cons:
  - Every builder path changes.
  - The dashboard's GUI-tool lookup needs data from the builder's tables.

For that GUI-tool lookup:
- **Option E1 (chosen):** the API calls a small builder endpoint (`GET /api/portal/workflow/gui-tool`) over the Docker network with the user's token.
- **Option E2:** the API reads the `portal` schema directly. This couples the two services at the database level.

For the stored FHIR URLs:
- **Option F1 (chosen):** a hard cut-over, then re-push every stale measurement dataset with the existing `run_fhir_push_job`, which recomputes URLs from `API_PUBLIC_URL`. No new FHIR logic.
- **Option F2:** a string rewrite in place. It keeps HAPI ids, but it is new code.
- **Option F3:** keep `/digitaltwins-api` as an alias. Rejected: we chose a hard cut-over.

## Decision

- The API is served at `/api`. The prefix stays outside the app (gateway rewrite plus uvicorn `--root-path /api`), and there is no alias for `/digitaltwins-api`.
- `/api/dashboard` moves into the API with the same paths and response shapes. It calls the API's own route functions in-process.
- The builder's routers move to `/api/portal/tools` and `/api/portal/workflow`. The gateway routes the more specific `/api/portal/` to the portal and everything else under `/api/` to the API.
- The unused portal routes are deleted rather than moved. Nothing in the repo calls them (the SPA authenticates with keycloak-js), and `/api/login` would collide with the API's own `/login`:
  - `/api/login`, `/api/refresh`, `/api/test`, `/api/auth/*`
  - `/api/report_viewer`
  - the disabled dashboard stubs and `/api/dashboard/health`
- Every `digitaltwins-api` identifier becomes `api`: the compose service and DNS name, the container label, the image workdir, the JupyterHub service and the gateway upstream. The env vars `DIGITALTWINS_API_*` become `API_*`. Links to the old standalone repo point at `services/api` in this repo.
- A one-off CLI (`python -m digitaltwins.cli.repush_fhir_urls`) re-pushes measurement datasets whose stored URLs don't match the current public base.

## Consequences

- Clients of `/digitaltwins-api/...` and of the old builder paths (`/api/tools/...`, `/api/workflow/...`) break. Old `/digitaltwins-api` URLs fall through to the portal SPA (HTML, status 200), not a 404.
- Existing deployments must regenerate `.env` and remote compute-worker envs (the `API_*` rename), remove the orphaned `digitaltwins-api` container, and run the FHIR re-push CLI. Re-pushing gives HAPI resources new ids and re-downloads each dataset from MinIO. Datasets not in `completed` state keep their old URLs until their next push.
- The JupyterHub startup token cleanup also covers the legacy `digitaltwins-api` service name, so a token left on the old service can't stay valid.
- The API now depends on the portal backend for one lookup (GUI assay launch). Script and notebook launches don't call it.
- The portal stack on its own (without the gateway) no longer serves `/api/dashboard`.
