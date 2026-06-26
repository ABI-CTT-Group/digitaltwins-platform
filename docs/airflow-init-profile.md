# Airflow Init — Run Once, Not Every Time

## What changed

`airflow-init` has been moved behind the `init` profile. It no longer runs
automatically on every `docker compose up`.

**Before:** every `docker compose up` would block for ~60 seconds waiting for
`airflow-init` to complete DB migrations, chown volumes, and create the admin
user — even when nothing needed initialising.

**After:** `docker compose up -d` starts immediately. `airflow-init` only runs
when explicitly requested.

## When you need to run it

Run `airflow-init` on:
- **First deployment** — to migrate the database and create the Airflow admin user
- **After an Airflow version upgrade** — to run any new DB migrations

```bash
docker compose --profile init up airflow-init
```

Wait for it to complete (you'll see "admin user created" in the logs), then the
normal services will pick up from there.

## Why it's safe to skip

Airflow's DB migrations are idempotent — running them twice does no harm, but
they're also unnecessary if the schema is already current. The admin user
creation is also a no-op if the user already exists. There is no ongoing state
that `airflow-init` maintains; it's purely a setup step.
