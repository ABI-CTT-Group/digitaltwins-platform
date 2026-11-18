# API compose settings cleanup (future_refactoring "API settings leftovers" item 2)

## Context

`docs/future_refactoring.md` → "API settings leftovers" → item 2 lists four problems with the API's settings:

1. `services/api/docker-compose.yml:59` bind-mounts `./configs.ini:/api/configs.ini`. No code reads it. When the host file
   is missing, Docker creates an empty root-owned directory instead.
2. `AIRFLOW_PORT` (`docker-compose.yml:37`) is passed to the API, but the API never reads it. The Airflow port mapping
   and the compute worker read it from `.env`, not from the API.
3. `core/keycloak_verifier.py:121,125` reads `KEYCLOAK_CA_CERT` and `KEYCLOAK_VERIFY_SSL`, but the API's compose file doesn't pass them.
   So `KEYCLOAK_VERIFY_SSL` in `.env` never reaches the API. The builder already passes both
   (`services/builder/docker-compose.yml:55-56`).
4. `_coerce_value` in `src/digitaltwins/utils/config_loader.py` is unused.

The item was skipped earlier because any compose change recreates the `api` container. This change accepts that.

**Decision (user):** keep `ConfigLoader`. It is a public name in the PyPI package, and its only user is the Gen3
example `examples/export_metadata.py`. Move that note into the existing Gen3 debt item (item 1), so ConfigLoader is
removed together with the Gen3 example.

No ADR: these are removals and a pass-through that copies the builder, with no real alternative design.

## Branch and plan files

- New branch `refactor/api-compose-settings`, created from `main` after `git fetch` (the current branch
  `dev_chinchien` is at the merge of #408).
- Plan folder `docs/plans/<YYYY-MM-DD-HHMMSS>-api-compose-settings/`, holding `plan.md` (this plan) and `tasks.md`
  (one checkbox per step below, ticked as soon as its check passes). Sync it right after every edit to these files.

## Steps

1. **Red: compose test.** Create `services/api/tests/test_compose.py`. It loads `docker-compose.yml` with
   `yaml.safe_load`, as `services/builder/tests/test_keycloak_config.py` does. `yaml` is already a dependency of the
   API, and `make test-api` mounts `services/api`. The API's `environment` is a mapping, not a list.
   - `test_no_configs_ini_bind_mount`: no entry in `services.api.volumes` contains `configs.ini`.
   - `test_airflow_port_is_not_passed`: `"AIRFLOW_PORT" not in env`.
   - `test_keycloak_tls_settings_reach_the_api`: `env["KEYCLOAK_VERIFY_SSL"] == "${KEYCLOAK_VERIFY_SSL:-true}"` and
     `env["KEYCLOAK_CA_CERT"] == "${KEYCLOAK_CA_CERT:-}"`.
   → `make test-api PYTEST_ARGS="tests/test_compose.py"` fails all three tests.
2. **Green: compose.** In `services/api/docker-compose.yml`:
   - Remove the `./configs.ini:/api/configs.ini` volume line.
   - Remove the `AIRFLOW_PORT` line.
   - Under `# keycloak`, add `KEYCLOAK_VERIFY_SSL: ${KEYCLOAK_VERIFY_SSL:-true}` and `KEYCLOAK_CA_CERT: ${KEYCLOAK_CA_CERT:-}`,
     with the same defaults as the builder.
   → All three tests pass. `docker compose config api` (read-only) shows the change.
3. **Remove `_coerce_value`** from `config_loader.py`. Keep `is_truthy`, `ConfigLoader` and the `json` import, which ConfigLoader still uses.
   → `grep -rn _coerce_value services/` finds nothing.
4. **Docs.**
   - `services/api/README.md`: remove the `configs.ini` gotcha (lines 319-320). In the "Connects to" Keycloak row, add
     `KEYCLOAK_VERIFY_SSL` and `KEYCLOAK_CA_CERT`.
   - `.env.template:44-45`: the comment says "used by portal" and "stays false", but the value is `true`. Change it to
     say the builder and the API use it, and that it matters only when they reach Keycloak over https.
   - `docs/production.md:70`: change "(builder)" to "(builder, API)".
   - `util/sync-runtime.sh:44`: keep the exclude, because existing hosts still have the root-owned directory. Change its
     comment to say the directory was left by the API's old bind mount.
   - `docs/future_refactoring.md`: remove "API settings leftovers" item 2. Add one sentence to item 1 (Gen3): "`ConfigLoader`
     in `utils/config_loader.py` is used only by the Gen3 example `examples/export_metadata.py`; remove it with that
     example."
   → `make docs-check` passes.
5. **Verify.** Run `make test` and `make lint`, and compare the lint output against `main`. Run `make gitleaks`.
6. **Live check (local only).** Rebuild and restart only the API: `docker compose up -d --build api`.
   - `docker compose exec api printenv KEYCLOAK_VERIFY_SSL` prints `true`.
   - `docker compose exec api printenv AIRFLOW_PORT` prints nothing.
   - `/api/docs` returns 200, and a signed-in request still works (e.g. list datasets in the portal).
7. **Finish.** Sync the plan, add an "Outcome" section if anything differed from the plan, and tick `tasks.md`.
   Commit only when you ask: one commit for the code and tests, one for the docs, one for the plan.

## Behaviour on deployed hosts

- Recreates the `api` container (the reason the item was skipped). Deploy with `docker compose up -d --build api` only.
- TLS: on the platform the API reaches Keycloak over internal http (`KEYCLOAK_BASE_URL=http://keycloak:8080/auth`), so
  `KEYCLOAK_VERIFY_SSL` and `KEYCLOAK_CA_CERT` change nothing there. They take effect only if `KEYCLOAK_BASE_URL` is https.
  - `KEYCLOAK_CA_CERT` is a path inside the container, the same as in the builder. Neither service mounts a CA file, so a
    host that sets it also needs a mount. That is not in this change.
- The root-owned `services/api/configs.ini/` directory stays on existing hosts. It is harmless, and sync-runtime keeps excluding it.

## Noticed, then fixed at the user's request

- `docs/production.md:70` said `KEYCLOAK_VERIFY_SSL` is "currently `false`", but the root `.env.template` and both
  compose defaults say `true`. That checklist item is reworded.
- `services/portal/.env.template` sets `KEYCLOAK_VERIFY_SSL=false` and nothing reads it. It is recorded as debt
  (Repository layout item 6) and not removed here.

## Verification summary

- `tests/test_compose.py` goes from red to green.
- `make test`, `make lint` (compared against `main`), `make docs-check` and `make gitleaks` pass.
- The API container is rebuilt and restarted, `printenv` shows the expected variables, and `/api/docs` responds.

## Outcome: where implementation differed from the plan

- Step 6 (live check) was not run. `docker compose config api` confirmed the rendered service:
  `KEYCLOAK_VERIFY_SSL: "true"`, `KEYCLOAK_CA_CERT: ""`, no `AIRFLOW_PORT` and no `configs.ini` mount.
- The `.env.template` comment no longer mentions `KEYCLOAK_INTERNAL_URL`. The builder and the API, the only readers of
  `KEYCLOAK_VERIFY_SSL`, reach Keycloak through `KEYCLOAK_BASE_URL`; other services still read `KEYCLOAK_INTERNAL_URL`.
- `make test`, `make lint`, `make docs-check` and `make gitleaks` passed. `make gitleaks` scanned 0 commits because
  nothing was committed yet, so `gitleaks detect --no-git` was also run on the plan folder: no leaks.
