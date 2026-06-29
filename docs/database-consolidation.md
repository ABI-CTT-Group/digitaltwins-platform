# Database Consolidation Plan

## Current State

The platform currently runs **two separate PostgreSQL instances** and one embedded database:

| Service | Image | Database | Used by |
|---------|-------|----------|---------|
| `database` | postgres:16 | `digitaltwins` | Platform API, portal backend |
| `postgres` | postgres:13 | `airflow` | Airflow (scheduler, workers, API) |
| `keycloak` (embedded H2) | n/a | H2 file store | Keycloak identity |

This is unnecessarily complex:
- Two Postgres containers to manage, monitor, and back up separately
- Airflow's Postgres is postgres:13 while the platform uses postgres:16
- Keycloak's H2 database is not easily backed up, not portable across Keycloak versions, and invisible to standard backup tooling

## Target State

One PostgreSQL instance (postgres:16) hosting three databases:

| Database | Owner | Used by |
|----------|-------|---------|
| `digitaltwins` | `admin` | Platform API, portal backend (unchanged) |
| `airflow` | `airflow` | Airflow scheduler, workers, API server |
| `keycloak` | `keycloak` | Keycloak identity and realm data |

Benefits:
- Single `pg_dump` backs up everything
- One container to manage
- Consistent Postgres version across the platform
- Simpler backup and restore

---

## Migration Steps

### Prerequisites

Before starting, export all existing data from the systems being migrated.

**Export Keycloak realm (from running system):**
```bash
docker exec keycloak /opt/keycloak/bin/kc.sh export \
  --dir /tmp/keycloak-export \
  --realm digitaltwins \
  --users realm_file
docker cp keycloak:/tmp/keycloak-export ./keycloak-export
```
Keep this JSON — it's needed to re-import the realm after switching to Postgres.

**Export Airflow database:**
```bash
docker compose exec postgres pg_dump -U airflow airflow > airflow_backup.sql
```

---

### Step 1 — Add init scripts to platform Postgres

Add two init SQL files to `services/postgres/`:

**`services/postgres/02_airflow_db.sql`**
```sql
CREATE USER airflow WITH PASSWORD :'airflow_password';
CREATE DATABASE airflow OWNER airflow;
```

**`services/postgres/03_keycloak_db.sql`**
```sql
CREATE USER keycloak WITH PASSWORD :'keycloak_password';
CREATE DATABASE keycloak OWNER keycloak;
```

Mount them in `services/postgres/docker-compose.yml`:
```yaml
volumes:
  - ./digitaltwins_schema.sql:/docker-entrypoint-initdb.d/01_schema.sql:ro
  - ./02_airflow_db.sql:/docker-entrypoint-initdb.d/02_airflow_db.sql:ro
  - ./03_keycloak_db.sql:/docker-entrypoint-initdb.d/03_keycloak_db.sql:ro
```

> **Note:** `docker-entrypoint-initdb.d` scripts only run on a **fresh volume**. For existing
> deployments, create the databases manually (see below).

**On existing deployments — create databases manually:**
```bash
docker compose exec database psql -U ${POSTGRES_USER} -c "CREATE USER airflow WITH PASSWORD 'yourpassword';"
docker compose exec database psql -U ${POSTGRES_USER} -c "CREATE DATABASE airflow OWNER airflow;"
docker compose exec database psql -U ${POSTGRES_USER} -c "CREATE USER keycloak WITH PASSWORD 'yourpassword';"
docker compose exec database psql -U ${POSTGRES_USER} -c "CREATE DATABASE keycloak OWNER keycloak;"
```

Add `AIRFLOW_POSTGRES_PASSWORD` and `KEYCLOAK_DB_PASSWORD` to `.env` if not already present.

---

### Step 2 — Point Airflow at platform Postgres

In `services/airflow/docker-compose.yml`, update the connection strings in the common
environment block to point at `database` (the platform Postgres service name) instead of `postgres`:

```yaml
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:${AIRFLOW_POSTGRES_PASSWORD}@database:5432/airflow
AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:${AIRFLOW_POSTGRES_PASSWORD}@database:5432/airflow
```

Remove the `postgres` service block and its volume from `services/airflow/docker-compose.yml`.

Restore the Airflow database:
```bash
docker compose exec -T database psql -U airflow airflow < airflow_backup.sql
```

---

### Step 3 — Point Keycloak at platform Postgres

In `services/keycloak/docker-compose.yml`, add:

```yaml
environment:
  KC_DB: postgres
  KC_DB_URL: jdbc:postgresql://database:5432/keycloak
  KC_DB_USERNAME: keycloak
  KC_DB_PASSWORD: ${KEYCLOAK_DB_PASSWORD}
  # ... existing env vars ...
```

Remove the `keycloak_data` volume (H2 store) — it is no longer needed once Keycloak
is using Postgres. On first startup with `--import-realm`, Keycloak will initialise its
schema in Postgres and import the realm JSON.

Copy the exported realm JSON to the import directory before restarting:
```bash
cp keycloak-export/digitaltwins-realm.json \
   services/keycloak/import/digitaltwins-realm.json
```

Then restart Keycloak:
```bash
docker compose restart keycloak
```

---

### Step 4 — Update backup script

Once consolidated, `backup_data.sh` needs only one Postgres dump covering all three databases:

```bash
pg_dumpall -U ${POSTGRES_USER} > postgres_all.sql
```

Or dump each database separately for finer-grained restore:

```bash
pg_dump -U ${POSTGRES_USER} digitaltwins > digitaltwins.sql
pg_dump -U ${POSTGRES_USER} airflow      > airflow.sql
pg_dump -U ${POSTGRES_USER} keycloak     > keycloak.sql
```

---

### Step 5 — Update the remote compute worker

The compute worker `docker-compose.yml` connects to Airflow Postgres via:
```
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:${AIRFLOW_POSTGRES_PASSWORD}@${MAIN_VM_IP}:${AIRFLOW_POSTGRES_PORT}/airflow
```

`AIRFLOW_POSTGRES_PORT` currently maps to the Airflow Postgres container's external port (8013).
After consolidation this should map to the platform Postgres external port (8003) instead.
Update `generate-compute-env.sh` and the compute worker `.env.template` accordingly.

Also update `ufw_for_walled_garden.sh` if port 8013 is no longer needed.

---

## New Deployments

For a fresh deployment after this change, `airgap_build_step3.yml` needs to create
the `airflow` and `keycloak` databases in Postgres before starting those services.
The init scripts handle this automatically on a fresh volume.

---

## Related Files

| File | Change required |
|------|----------------|
| `services/postgres/docker-compose.yml` | Add init script mounts |
| `services/postgres/02_airflow_db.sql` | New file |
| `services/postgres/03_keycloak_db.sql` | New file |
| `services/airflow/docker-compose.yml` | Update connection strings, remove postgres service |
| `services/keycloak/docker-compose.yml` | Add KC_DB* env vars |
| `buildout/util/backup_data.sh` | Consolidate Postgres dumps |
| `buildout/util/generate-compute-env.sh` | Update AIRFLOW_POSTGRES_PORT |
| `buildout/util/ufw_for_walled_garden.sh` | Remove port 8013 if no longer needed |
| `services/airflow/compute-worker/docker-compose.yml` | Update Postgres port |
| `.env.template` | Add KEYCLOAK_DB_PASSWORD |
