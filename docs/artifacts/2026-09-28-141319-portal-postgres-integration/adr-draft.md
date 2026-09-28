# Move the portal database from SQLite into the platform Postgres

- **Date:** 2026-09-28
- **Status:** Accepted

## Context

The portal backend keeps its plugin, workflow and measurement records in a private SQLite file (`plugin_registry.db` on the `plugin_database` volume). The rest of the platform (digitaltwins-api, Airflow, Keycloak, HAPI FHIR) already uses the shared `postgres:16` `database` service. Running a separate SQLite file means:

- a separate backup path
- no foreign-key enforcement, which has already hidden a wrong FK target on `plugin_deployments.build_id`
- no concurrent-writer safety for the backend's background build threads
- the data can't be seen in pgAdmin next to the platform data

Several design choices have to be made together:

- where the tables live
- which credentials the portal uses
- how the connection is configured
- how existing data is moved

One constraint shapes the credentials choice. The portal passes its whole environment to third-party plugin `docker compose` and build subprocesses.

## Alternatives Considered

### Where the tables live

#### Option A: a `portal` schema in the `digitaltwins` database (chosen)
- Pros:
  - Tables are namespaced away from the API's `public` tables.
  - The schema can be created without a new database, so existing volumes need only one idempotent script.
  - Joins or FKs to `dataset` remain possible later.
  - Everything is in one `pg_dump`.
- Cons:
  - Isolation is weaker than a separate database.
  - The `digitaltwins` database now has two owners.

#### Option B: a separate `portal` database (like airflow/keycloak)
- Pros: strongest isolation, and it follows the existing per-service pattern.
- Cons:
  - Cross-database joins with API data are impossible.
  - It is further from the request to merge into the *main* platform database.

#### Option C: the `public` schema of `digitaltwins`
- Pros: the simplest option.
- Cons:
  - It mixes two applications' tables.
  - Generic names such as `workflows` and `measurements` are likely to collide with future API tables.
  - Least privilege is hard to apply.

### Credentials

#### Option A: a dedicated `portal` role that owns only the `portal` schema (chosen)
- Pros: least privilege. If the credential leaks, the damage is limited to portal data.
- Cons: one extra secret (`PORTAL_DB_PASSWORD`), and a one-time manual step on existing volumes, because init scripts run only on empty volumes.

#### Option B: reuse the `POSTGRES_USER` admin superuser
- Pros: no new secret and no extra setup step.
- Cons: the portal would hold superuser access to every platform database, including Keycloak's, inside a process that spawns third-party plugin code.

### Moving existing data

#### Option A: an explicit one-off CLI with pre-flight and verification (chosen)
- Pros:
  - The operator controls it and it is auditable.
  - It checks the target is empty and the source FKs are intact, and verifies row counts after copying.
  - Nothing unexpected happens at startup.
- Cons: a manual runbook step on every deployment.

#### Option B: migrate automatically at startup
- Pros: no operator step.
- Cons:
  - It is implicit, and the risk of partial or duplicate copies has to be handled inside the boot path.
  - It is harder to audit in a regulated environment.

### Schema management

We keep the existing `create_all` + `migrate_add_missing_columns` mechanism, which works on Postgres, rather than introducing Alembic now. That keeps this change focused.

## Decision

The portal tables move into a `portal` schema in the `digitaltwins` database, owned by a dedicated `portal` role.

- **Connection:** the backend selects Postgres when `PORTAL_DB_HOST` is set and otherwise stays on SQLite, for standalone dev and unit tests. The Postgres URL is built from separate `PORTAL_DB_*` variables with `URL.create`, and the tables go into the `portal` schema through the connection's `search_path`, so the models don't change.
- **Plugin subprocesses:** `PORTAL_DB_*` variables are removed from the environment of plugin build and deploy subprocesses.
- **FK fix:** `plugin_deployments.build_id` is changed to reference `plugin_builds.build_id`, which is what the code actually stores.
- **Existing data:** it is moved with an explicit migration CLI.

## Consequences

- Portal data now has Postgres FK enforcement and concurrency, and is covered by the platform's Postgres backups and pgAdmin.
- Portal availability now depends on the `database` service (`depends_on: service_healthy`).
- `PORTAL_DB_PASSWORD` is a required secret: compose refuses to render the stack without it, rather than starting with an empty DB password.
- The portal role cannot create schemas, so the app creates the `portal` schema only if it is missing (standalone use with a superuser). On the platform, the init script creates it.
- Existing deployments need a one-time role/schema script and a migration run. The SQLite volume stays in place for one release as a rollback path; anything written after the cut-over is lost on rollback.
- Postgres text cannot store NUL, but plugin build logs captured from Vite output could contain it. Captured process output now has NUL removed, and the migration removes it from existing text and reports each affected column. This is the only change the migration makes to data values.
- The SQLite code path remains for standalone use. Two backends must stay supported until it is removed.
- Schema changes still rely on add-missing-columns. Renames, type changes and drops will need Alembic, which is a later decision.
