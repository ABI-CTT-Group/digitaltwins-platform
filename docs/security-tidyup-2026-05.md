# Security Tidy-Up — May 2026

A pass through the codebase to remove hardcoded secrets, consolidate credential
naming, and ensure all passwords are injected via environment variables.

---

## Secrets Removed from the Repository

### `buildout/dev/helm_mod`
A real Keycloak OAuth client secret (`GRAFANA_OAUTH_SECRET`) was committed in
plain text. The secret has been rotated in Keycloak. The file now uses a
`:?` bash guard that fails loudly if the variable is not set before running:

```bash
: ${GRAFANA_OAUTH_SECRET:?}
: ${GRAFANA_ADMIN_PASSWORD:?}
```

### `buildout/dev/observability/grafana-values.yaml`
Hardcoded `adminPassword: strongpassword` removed. Password is now set
exclusively via `--set adminPassword=$GRAFANA_ADMIN_PASSWORD` in `helm_mod`.

### `buildout/dev/observability/mimir-values.yaml`
Hardcoded `secret_access_key` and `rootPassword` removed. Both are now
injected at deploy time via the `values` override in the Deploy Mimir task
in `install_observability_airgap.yaml`, reading from environment variables
`MIMIR_MINIO_ROOT_USER` and `MIMIR_MINIO_SECRET_KEY`.

---

## Naming Consolidated

### `KC_CLIENT_SECRET` → `KEYCLOAK_CLIENT_SECRET`
Two contributors had independently named the same Keycloak API client secret
differently. `KC_CLIENT_SECRET` was used only by Ansible at deploy time;
`KEYCLOAK_CLIENT_SECRET` was used by all runtime services. The Ansible
playbook (`build_all_carvin.yaml`) now uses `KEYCLOAK_CLIENT_SECRET`
throughout, eliminating the duplicate.

---

## Hardcoded Passwords Replaced with Env Vars

### `services/airflow/docker-compose.yml`
| Was | Now |
|---|---|
| `postgresql+psycopg2://airflow:airflow@postgres/airflow` | `airflow:${AIRFLOW_POSTGRES_PASSWORD}@postgres/airflow` |
| `db+postgresql://airflow:airflow@postgres/airflow` | `airflow:${AIRFLOW_POSTGRES_PASSWORD}@postgres/airflow` |
| `redis://:@redis:6379/0` | `redis://:${REDIS_PASSWORD}@redis:6379/0` |

Redis now also starts with `--requirepass ${REDIS_PASSWORD}` and the
healthcheck authenticates with `-a ${REDIS_PASSWORD}`.

### `services/api/digitaltwins-api/docker/postgres/docker-compose.yml`
`POSTGRES_PASSWORD: postgres` → `${POSTGRES_PASSWORD:-postgres}`

### `buildout/dev/compute/docker-compose.yml`
| Was | Now |
|---|---|
| `airflow:airflow@${MAIN_VM_IP}` (×2) | `airflow:${AIRFLOW_POSTGRES_PASSWORD}@${MAIN_VM_IP}` |
| `redis://:@${MAIN_VM_IP}` | `redis://:${REDIS_PASSWORD}@${MAIN_VM_IP}` |
| `aws://minioadmin:minioadmin@?...` | `aws://${MINIO_ACCESS_KEY}:${MINIO_SECRET_KEY}@?...` |

---

## New Variables Required in `.env`

The following variables must be added to the main platform `.env`:

| Variable | Used by | Notes |
|---|---|---|
| `REDIS_PASSWORD` | Airflow broker, compute worker | Must match on main VM and all compute nodes |
| `AIRFLOW_POSTGRES_PASSWORD` | Airflow services, compute worker | Must match on main VM and all compute nodes |
| `SEEK_ADMIN_PASSWORD` | Ansible (`build_all_carvin.yaml`) | SEEK admin user created at deploy time |
| `MYSQL_ROOT_PASSWORD` | Ansible (`build_all_carvin.yaml`, `airgap_build_step3.yml`) | SEEK's internal MySQL root |
| `MYSQL_PASSWORD` | Ansible (same) | SEEK's MySQL app user |

The following are needed for the observability stack — source them before
running Ansible/Helm (see `buildout/data/ansible_secrets`):

| Variable | Used by |
|---|---|
| `GRAFANA_ADMIN_PASSWORD` | `helm_mod`, `install_observability_airgap.yaml` |
| `GRAFANA_OAUTH_SECRET` | `helm_mod`, `install_observability_airgap.yaml` |
| `MIMIR_MINIO_ROOT_USER` | `install_observability_airgap.yaml` |
| `MIMIR_MINIO_SECRET_KEY` | `install_observability_airgap.yaml` |

---

## Outstanding / Future Work

- **Redis auth on compute nodes** — `REDIS_PASSWORD` must be set in the
  compute node `.env` and kept in sync with the main VM.
- **MinIO service account** — all services currently use the MinIO root
  credentials (`MINIO_SERVER_ACCESS_KEY/SECRET_KEY`). In production, each
  service should use a scoped MinIO service account with minimal permissions.
- **`_AIRFLOW_WWW_USER_*` rename** — these variables are misused inside the
  preprocessor DAG to authenticate against the DigitalTWINS platform API.
  They should be renamed `DIGITALTWINS_API_USERNAME/PASSWORD` to reflect
  their actual purpose. See `docs/workflow-user-attribution.md`.
- **Workflow user attribution** — users who trigger workflows from the portal
  appear as `admin` in Airflow logs. See `docs/workflow-user-attribution.md`
  for full analysis and proposed fixes.
