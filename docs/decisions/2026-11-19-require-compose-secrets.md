# Require every platform secret in the compose files

- **Date:** 2026-11-19
- **Status:** Accepted

## Context

[Make the JupyterHub service token a per-deployment secret](2026-10-16-jupyterhub-service-token-secret.md) set the
rule that a deployment can never run on a default secret: `gen-env.sh` refuses to render without it, and compose uses
`${VAR:?...}`. Only some secrets followed that rule. In the compose files, the variables in `secrets.env.template`
appeared in three forms:

| Form | Count | When the variable is missing |
|---|---|---|
| `${VAR:?...}` | 11 | Compose refuses to start. |
| `${VAR:-<literal>}` | 22 | The service runs on a default that is public, since this repository is public. |
| `${VAR}` or `${VAR:-}` | 19 | The service runs with an empty secret, after a warning. |

The defaults covered the Postgres superuser, MinIO, Keycloak's bootstrap admin, the Airflow database, pgAdmin and the
Orthanc client secret. On a deployment rendered by `util/gen-env.sh`, every one of these variables is set, because the
script refuses to render an unset or empty variable that `.env.template` references. The defaults only take effect on
a hand-made or outdated `.env`, which is exactly where a public default does harm.

`KEYCLOAK_DB_PASSWORD` is different. `.env.template` doesn't reference it, so it never reaches `.env`. Every host runs
Keycloak on its compose default, which matches the role password in `services/postgres/keycloak_init.sql`.

## Alternatives Considered

### Option A: Fix only the Orthanc client secret
- Pros: smallest change.
- Cons: leaves 40 other references on public defaults or blanks, with nothing to stop new ones.

### Option B: Require every secret except `KEYCLOAK_DB_PASSWORD`, and guard it with a test
- Pros:
  - Applies the 2026-10-16 rule everywhere.
  - On a rendered deployment, every service's resolved config, and so its compose config hash, is unchanged, so
    deploying recreates no container.
  - A test stops new defaults.
- Cons: a host whose `.env` lacks one of these variables can't run any `docker compose` command until it's added,
  because the root file includes every service file. Each host needs a check before deploying.

### Option C: Option B plus rotating `KEYCLOAK_DB_PASSWORD`
- Pros: no exceptions.
- Cons: needs a coordinated change on every host, in this order: set the variable, run `ALTER ROLE keycloak` on the
  existing database, then deploy. A missed step takes Keycloak, and sign-in, down.

## Decision

Option B. Every reference to a variable in `secrets.env.template` from a compose file is
`${VAR:?set VAR in secrets.env}`. In the Airflow compute worker's file it is
`${VAR:?set in the node .env (same as platform)}`, the message that file already used.
`util/tests/test_secrets_required.sh` (`make test-util`) fails on any other form. It allows `KEYCLOAK_DB_PASSWORD`
only, which is tracked in `docs/future_refactoring.md` ("Keycloak's database password is a public default").

## Consequences

- A missing or empty secret stops `docker compose` with a message that names it, instead of starting on a public
  default or a blank.
- A new secret must be added to `secrets.env.template` and `.env.template`, and used with `:?`; the test enforces the
  compose side.
- The portal's standalone stack and other stacks run outside the platform must be given their secrets explicitly.
- `KEYCLOAK_DB_PASSWORD` stays on its public default until the rotation is done.
