# MinIO

The platform's S3 object store: datasets, tool builds, Airflow workspaces and logs.

## Purpose

MinIO holds the files behind every dataset. Postgres holds the metadata and points into these
buckets by dataset UUID.

`init-minio.sh` creates these buckets:

| Bucket | Holds | Anonymous access |
|---|---|---|
| `measurements` | Measurement datasets | none |
| `models` | Model datasets | none |
| `workflows` | Workflow datasets and assay workspace outputs | none |
| `tools` | Tool datasets, including approved GUI tool bundles the browser loads | `public` |
| `tool-builds` | Portal test builds of tools not yet approved | `download` |
| `airflow-workspace` | Assay run inputs and outputs, staged per run | none |

Airflow creates one more, `airflow-logs`, for its remote task logs (`minio-logs-init` in
`services/airflow/docker-compose.yml`).

## Status

Active. The root `docker-compose.yml` includes this folder's `docker-compose.yml`.

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | `minio`, the server, and `minio-init`, a one-shot `mc` container that runs `init-minio.sh` once `minio` is healthy |
| `init-minio.sh` | Creates the buckets above and sets their anonymous policies. Idempotent (`--ignore-existing`) |

## Connects to

| Client | How |
|---|---|
| api | `MINIO_ENDPOINT` (`http://minio:9000`), `MINIO_SERVER_ACCESS_KEY`, `MINIO_SERVER_SECRET_KEY` |
| builder | `MINIO_ENDPOINT`, and `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`, which its compose file sets from `MINIO_SERVER_*`. It also passes `MINIO_SERVER_*` on to plugin compose files |
| Airflow | DAG tasks get `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` from `MINIO_SERVER_*`. Remote logging uses `AIRFLOW_CONN_MINIO_LOGS`, built from the same two values |
| Remote compute node | Host port 8011, through the `.env` that `util/generate-compute-env.sh` writes |
| portal-frontend | Its nginx serves the `tools` and `tool-builds` buckets to browsers at `/tools/` and `/tool-builds/` |
| gateway | `/minio/` → the console on port 9001; `/minio-discovery.json` (below) |
| Keycloak | Console sign-in through the `minio` client. MinIO reads the realm's discovery document from `MINIO_OIDC_CONFIG_URL` and maps the token's `policy` claim to a MinIO policy |

The host publishes the S3 API on port 8011 and the console on port 8012.

## Configuration

Set in the root `.env` (rendered from `.env.template`); the secrets come from `secrets.env`.

| Variable | Use |
|---|---|
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | The credentials MinIO itself checks. `minio-init` uses them too |
| `MINIO_SERVER_ACCESS_KEY`, `MINIO_SERVER_SECRET_KEY` | The credentials every platform client sends (api, builder, Airflow) |
| `MINIO_BROWSER_REDIRECT_URL` | The console's public URL; must end in `/minio`, the gateway route |
| `MINIO_OIDC_CONFIG_URL` | Where MinIO fetches the OIDC discovery document. `util/gen-env.sh` defaults it to the gateway's `/minio-discovery.json` |
| `MINIO_KEYCLOAK_CLIENT_SECRET` | Secret of the realm's `minio` client |

## Run & test

No automated tests. To start it on its own: `docker compose up -d minio minio-init`, from the
repository root.

## Gotchas

- **`MINIO_SERVER_SECRET_KEY` must equal `MINIO_ROOT_PASSWORD`, and `MINIO_SERVER_ACCESS_KEY` must
  equal `MINIO_ROOT_USER`.** MinIO accepts only its root credentials, and `init-minio.sh` creates no
  other account, but every platform client sends `MINIO_SERVER_*`. If they differ, every S3 call from
  the api, the builder and Airflow fails with 403. `secrets.env.template` lists the two secrets as
  separate keys, so set them to the same value.
- **`tools` is anonymously writable as well as readable.** In `mc`, the `public` policy allows
  anonymous reads and writes; `download` (used for `tool-builds`) allows reads only.
- **A new bucket goes in `init-minio.sh`**, which runs each time the `minio-init` container starts.
  Airflow's `airflow-logs` is the exception, created by Airflow's own init container.
- **The discovery document is generated.** `util/gen-env.sh` writes
  `services/nginx/snippets/minio-discovery.json` (git-ignored): browser endpoints on the public
  domain, token and key endpoints on `keycloak:8080`. It exists because MinIO can't reach the public
  domain from inside the Docker network. Re-run `gen-env.sh` after changing the domain.
- `services/portal/docker-compose.yml` defines its own `minio` and `minio-init` for the portal's
  standalone stack. The platform never starts those.
