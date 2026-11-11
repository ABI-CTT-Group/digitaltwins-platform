# Walkthrough: one Keycloak token verifier

Branch `feat/keycloak-verifier`, stacked on `feat/builder-sql-migrations`. Plan: [plan.md](plan.md). Decision: [ADR 2026-10-21-one-keycloak-token-verifier](../../decisions/2026-10-21-one-keycloak-token-verifier.md).

## What changed

### 1. `fix(api)`: credentials no longer reach the log
- `validate_credentials` printed both credential objects on every request: Basic-auth passwords, and bearer tokens.
- The prints are gone, and a test asserts that neither the password nor the token appears in stdout or the log.

### 2. `feat(api)`: the shared verifier
`services/api/src/digitaltwins/core/keycloak_verifier.py` needs only the standard library and PyJWT.
- **What it accepts:** RS256 access tokens (`typ: Bearer`) with `exp` and `iat`.
  - The signing key is chosen by `kid` from the realm key set, fetched over the internal URL.
  - `iss` must equal the issuer in Keycloak's discovery document.
  - `azp` must be in the caller's allowed set.
- **Fetching:** an unknown `kid` refetches at most once a minute, and if a refetch fails, the cached keys stay in use.
- **TLS:** verified by default. `KEYCLOAK_CA_CERT` names a CA bundle; `KEYCLOAK_VERIFY_SSL=false` turns verification off and logs a warning.
- **Errors:** `InvalidToken`, or `KeycloakUnavailable` when nothing is cached.

### 3. `refactor(api)!`: the API and CLI use it
- **Auth:** Bearer and Basic auth (`app/routers/auth.py`) and the CLI (`keycloak_login.verify_token`) accept the `portal-frontend` and `api` clients.
- **Errors:** a generic 401 with `WWW-Authenticate: Bearer`, or 503 when Keycloak is unreachable and nothing is cached.
- **Unchanged:** the user object, `{username, token, claims}`.
- **Removed:**
  - python-jose, replaced by PyJWT 2.15.1
  - `KEYCLOAK_ALGORITHM`, from the API's compose file and `.env.template`
  - the per-failure key refetch

### 4. `refactor(builder)!`: the builder uses it
- **The copy:** a verbatim copy at `app/client/keycloak_verifier.py`.
  - `tests/test_shared_with_api.py` now checks both shared files; this verifier and the migration runner.
  - The `Makefile` mounts the API's file, and CI's builder filter includes it.
- **`KeycloakClient`** keeps its interface. Inside, it checks each token once, filters the roles as before, and no longer swallows errors.
- **`get_current_user`:** 401 for an invalid token and 503 when Keycloak is unreachable. It used to return 401 for both.
- **Dependencies:** python-keycloak and python-jose are replaced by PyJWT.
- **Defaults:**
  - `KEYCLOAK_VERIFY_SSL` defaults to `true`, in the builder's compose file and `.env.template`.
  - The stale `KEYCLOAK_PUBLIC_URL` default, `https://130.216.216.243:8009`, which lacked `/auth`, becomes `http://localhost/auth`.

### 5. `docs`
- A new ADR.
- The 2026-10-20 ADR's follow-up is marked done.
- The builder README covers the verifier copy and the TLS variables.
- The identity test's new location is noted in the migrations ADR and the README.

## Deviations from the plan
- The identity test for the migration runner moved from `test_migration_runner.py` into `test_shared_with_api.py`, so one test now covers both shared files.
- `KeycloakClient.server_url` no longer ends with `/`. That slash was only needed for python-keycloak's URL joining.

## Verification
- **`make test-api`:** 391 passed, 1 skipped.
  - That's 28 more than before: 22 for the verifier and 6 for the API's auth.
  - The verifier tests serve a stand-in realm over HTTP and HTTPS on the loopback.
  - They cover each rejection case, an algorithm-confusion token, key rotation, the refetch cooldown, Keycloak being down with and without cached keys, and the CA bundle and opt-out.
- **`make test-builder`:** 221 passed, 11 skipped.
- **Mutation checks:** removing the `azp` check made a test fail, and so did removing the refetch cooldown.
- **Pre-commit `gitleaks`:** passed on every commit.
