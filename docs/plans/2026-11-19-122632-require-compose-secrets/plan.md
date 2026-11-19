# Require every platform secret in the compose files

## Context

While removing `services/api/.env.template` (PR #411), I found that the Orthanc Keycloak client secret is a public
literal fallback in the PACS compose files. A scan of every compose file for the 29 variables in `secrets.env.template`
shows that this is a pattern, not a one-off:

| Form in compose | Count | What happens when the variable is missing |
|---|---|---|
| `${VAR:?msg}` (required) | 11 | Compose refuses to start. This is the rule set by ADR `2026-10-16-jupyterhub-service-token-secret.md`: "a deployment can never run on a default". |
| `${VAR:-<literal>}` | 22 | Runs on a public default (`POSTGRES_PASSWORD`, `MINIO_*`, `KC_BOOTSTRAP_ADMIN_PASSWORD`, `AIRFLOW_DB_PASSWORD`, `PGADMIN_DEFAULT_PASSWORD`, `ORTHANC_KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_DB_PASSWORD`). |
| `${VAR}` / `${VAR:-}` | 20 | Runs with an empty secret, after a warning (`ORTHANC_AUTH_*`, `MINIO_SERVER_SECRET_KEY`, `AIRFLOW_DB_PASSWORD`, `REDIS_PASSWORD`, `KEYCLOAK_CLIENT_SECRET`, `JUPYTERHUB_CRYPT_KEY`, `MINIO_KEYCLOAK_CLIENT_SECRET`). |

**Decision (user):** do the broad change in its own PR. Every secret reference becomes `${VAR:?...}`, and a test
guards against new fallbacks. The one exception is `KEYCLOAK_DB_PASSWORD`, which is recorded as debt:

- It is not in `.env.template`, so it never reaches `.env`. On every host Keycloak runs on the compose fallback,
  which matches the literal in `services/postgres/keycloak_init.sql`.
- Requiring it needs a credential rotation on every host (`ALTER ROLE`, plus converting the init SQL into a script).

**Why deploying this is safe:**
- `util/gen-env.sh` refuses to render `.env` if any variable the template references is unset or empty, and every
  affected variable except `KEYCLOAK_DB_PASSWORD` is referenced. `util/generate-compute-env.sh` does the same for the
  compute worker's `.env`.
- I tested this on a copy of the PACS compose file: with the variable set, `:-literal` → `:?` leaves
  `docker compose config --hash` unchanged, so no container is recreated.
- Risk: a host whose `.env` predates a variable fails every `docker compose` command, because the root file includes
  all service files. That is why each host is checked before deploy (see "Host check").

## Branch and evidence

- Start once PR #411 is merged, because this change removes the "Default credentials" debt item that #411 adds. If #411
  is still open, stop and ask.
- New branch `fix/require-compose-secrets` from `origin/main`.
- Plan folder `docs/plans/<YYYY-MM-DD-HHMMSS>-require-compose-secrets/`, holding `plan.md` and `tasks.md`. Tick each
  task as its check passes, and sync the folder after every edit.
- ADR `docs/decisions/2026-11-19-require-compose-secrets.md`, from `TEMPLATE.md`.
  - Alternatives: Orthanc only; every secret except `KEYCLOAK_DB_PASSWORD` (chosen); every secret including the
    Keycloak DB rotation.
  - It applies the 2026-10-16 ADR to every secret.
  - Status Proposed until the change is ready to merge, then Accepted.

## Steps

0. **Record the baseline.** On the new branch, before editing:
   `docker compose config --hash "*" > <scratchpad>/hash-before.txt`. This uses the local `.env`. Write the output to
   the scratchpad, not the repo; it holds only hashes, no values.
1. **Red: guard test.** Create `util/tests/test_secrets_required.sh`, following `util/tests/test_restart_policy.sh`
   (bash, awk and grep only).
   - Read the secret names from `secrets.env.template` (`^[A-Z0-9_]+=`).
   - Scan `docker-compose.yml` and every `services/**/*compose*.yml` except `services/seek/ldh-deployment/*`.
   - Fail with `FAIL <file>:<line> <VAR>: use ${VAR:?...}` for any `${VAR}`, `${VAR:-...}` or `${VAR-...}` of a secret.
   - Allow `KEYCLOAK_DB_PASSWORD` only, with a comment pointing to its debt item.
   - Never print values: report the file, line and variable name only.
   - Makefile `test-util`: also mount `secrets.env.template` and the root `docker-compose.yml`, read-only. Both are
     tracked and hold no secrets.
   → `make test-util` fails, listing 41 offenders (22 + 20, minus the excluded `KEYCLOAK_DB_PASSWORD` line).
2. **Green: compose files.** Change each offender to `${VAR:?set VAR in secrets.env}`, the existing Airflow message.
   In `services/airflow/compute-worker/docker-compose.yml`, use that file's existing message,
   `${VAR:?set in the node .env (same as platform)}`.
   - Files: the compose files of airflow, airflow/compute-worker, api, builder, hapi-fhir, jupyterhub, keycloak (both
     files), minio, pacs, pacs_pretend_external, portal and postgres.
   - The unused files (`keycloak/docker-compose-https.yml`, `pacs_pretend_external/`) change too, so the guard needs
     no further exceptions.
   → `make test-util` passes.
3. **Prove no container is recreated.** Run `docker compose config -q` (local `.env`). Then
   `docker compose config --hash "*"` must be identical to the baseline. With no `.env`
   (`docker compose --env-file /dev/null config -q`), Compose must fail on a missing secret.
4. **Docs.**
   - `docs/codemap.md` change playbook ("Add an environment variable or secret"): pass a secret with `${VAR:?...}`,
     never a default; `make test-util` enforces this.
   - `services/portal/README.md` standalone gotcha: the command also needs `MINIO_SERVER_SECRET_KEY`, because the
     standalone `minio` and `minio-init` no longer default it.
   - `docs/future_refactoring.md`:
     - Remove "Default credentials" item 1 (added by #411); this change resolves it.
     - Add an item: `KEYCLOAK_DB_PASSWORD` runs on the public default everywhere. Steps: add it to `.env.template`,
       make `keycloak_init.sql` a script that reads it, `ALTER ROLE keycloak` on each host, then remove the guard's
       exception.
     - Why skipped: it needs a coordinated rotation on every host.
   - ADR written as above.
   → `make docs-check` passes.
5. **Verify.**
   - `make test`, `make lint` (compared against `main`) and `make gitleaks` pass.
   - gitleaks finds nothing in the plan folder.
   - No secret value appears in the plan, the ADR, the commits or the PR.
6. **Finish.** Sync the plan, add an Outcome section if anything differed from the plan, and tick `tasks.md`. Commit
   only when asked. Proposed commits: test + compose + Makefile; docs + debt; ADR; plan.

## Host check (for you, before deploying to each host)

Prints only the names of missing or empty variables, never values:
```bash
cd ~/digitaltwins-platform
for v in KC_BOOTSTRAP_ADMIN_PASSWORD POSTGRES_PASSWORD PGADMIN_DEFAULT_PASSWORD MINIO_ROOT_PASSWORD MINIO_SERVER_SECRET_KEY \
         AIRFLOW_DB_PASSWORD JUPYTERHUB_CRYPT_KEY ORTHANC_AUTH_SERVICE_PASSWORD ORTHANC_AUTH_SECRET_KEY \
         ORTHANC_KEYCLOAK_CLIENT_SECRET KEYCLOAK_CLIENT_SECRET MINIO_KEYCLOAK_CLIENT_SECRET REDIS_PASSWORD; do
  grep -qE "^$v=.+" .env || echo "MISSING or empty: $v"
done
```
If nothing is printed, deploying is a no-op: no service's config hash changes. On a compute node, run the same check
against its own `.env` for `AIRFLOW_DB_PASSWORD`, `REDIS_PASSWORD` and `MINIO_SERVER_SECRET_KEY`.

## Not in this change

- Rotating any credential, or `KEYCLOAK_DB_PASSWORD` (debt item).
- Non-secret defaults such as `MINIO_SERVER_ACCESS_KEY:-minioadmin` and user names.
- The SEEK submodule's `docker-compose.env`.
- The `airflow` role password literal in `airflow_init.sql` (already noted in `services/postgres/README.md`).

## Verification summary

- The guard test goes from red (41 offenders) to green.
- Local `docker compose config --hash "*"` is identical before and after, so no container is recreated.
- Without a `.env`, Compose fails on a missing secret.
- `make test`, `make lint`, `make docs-check` and `make gitleaks` pass.

## Outcome: where implementation differed from the plan

- 40 offenders, not 41: the bare and empty forms were 19, not 20. The guard now reports 51 required references (11
  before, plus 40).
- No-`.env` check: with no env file at all, Compose stops first on `BUILDER_DB_PASSWORD`, which was already required.
  So the check ran with an env file holding only the previously required secrets (dummy values). This branch stops on
  `KC_BOOTSTRAP_ADMIN_PASSWORD`; `main` starts.
- `docker compose config --hash "*"` with the local `.env`: identical for all 27 services before and after.
- The "Default credentials" section in `docs/future_refactoring.md` keeps its heading. Its Orthanc item is replaced by
  the `KEYCLOAK_DB_PASSWORD` item, which the guard's exception comment points to by title.
- The ADR is written as Accepted: the decision was taken when the plan was approved.
