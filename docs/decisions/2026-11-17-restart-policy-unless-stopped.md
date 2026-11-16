# Use `restart: unless-stopped` for every long-running service

- **Date:** 2026-11-17
- **Status:** Accepted

## Context

The compose files used four different restart policies. `api` and `minio` had none, so after a crash or a
host reboot they stayed down while the rest of the platform came back. Airflow and redis used `always`,
copied from Airflow's upstream compose file. hapi-fhir used `on-failure` so it would retry until Postgres
was up. Everything else used `unless-stopped`.

The platform runs on shared hosts (staging, demo) and in production. There, operators sometimes stop a
single service on purpose, for maintenance or while investigating a problem.

## Alternatives Considered

### Option A: `always` everywhere
- Pros: a service comes back after a reboot even if someone stopped it by mistake.
- Cons: a service stopped on purpose also comes back after a reboot or a Docker daemon restart, possibly
  in the middle of maintenance.

### Option B: `unless-stopped` everywhere (one-shot jobs excepted)
- Pros: services recover from crashes and reboots; a deliberate `docker stop` survives a reboot. Matches
  what most services already used.
- Cons: a service stopped by mistake stays down after a reboot until someone notices.

### Option C: keep the mix
- Pros: no change.
- Cons: `api` and `minio` don't come back by themselves; behaviour differs per service for no reason.

## Decision

Option B. Every long-running service uses `restart: unless-stopped`. One-shot jobs (`airflow-init`,
`airflow-cli`, `minio-init`, `minio-logs-init`, and the `singleuser` image build) keep no policy or
`"no"`, because `unless-stopped` also restarts a container that exits cleanly, which would re-run an init
job forever. `util/tests/test_restart_policy.sh` (run by `make test-util`) enforces both rules.

## Consequences

- Airflow's compose file now differs from upstream on this point; keep the change when updating it.
- hapi-fhir still retries until Postgres is up, because `unless-stopped` restarts after any exit.
- A service stopped by hand stays down after a reboot. Monitoring has to notice a service that should be up.
- A restart policy only acts when the process exits. A container that hangs but keeps running is not
  restarted, healthcheck or not.
- `docker compose down` removes containers, so no policy brings them back; use `docker compose up -d`.
- A new service must set `restart: unless-stopped`, or be added to the test's one-shot list.
