# Plan: one Keycloak token verifier, with stricter checks

Status: **approved 2026-10-21**. Branch `feat/keycloak-verifier`, stacked on `feat/builder-sql-migrations`.

## Context

This is the second consistency follow-up from [ADR 2026-10-20](../../decisions/2026-10-20-merge-portal-backend-into-api-codebase.md): "one Keycloak verifier". Three places check Keycloak access tokens today. All three use python-jose 3.3.0 with the realm's single public key.

| | API (`app/routers/auth.py`) | Builder (`app/client/keycloak.py`, `app/utils/auth.py`) | CLI (`digitaltwins/cli/keycloak_login.py`) |
|---|---|---|---|
| Key | Realm public key, cached; refetched on *every* failed token | Realm public key, cached for the process's life | Realm public key, fetched on every call |
| Checks | signature, `exp` | signature, `exp` | signature, `exp` |
| `iss` / `azp` / `typ` | not checked | not checked | not checked |
| TLS to Keycloak | always off | `KEYCLOAK_VERIFY_SSL` (default off), `KEYCLOAK_CA_CERT` | default |
| Keycloak down | 503 | 401 | exception |
| Bad token | 401 with the library's error text | generic 401 | exception |

**Problems found along the way:**
- **`validate_credentials` prints its incoming credentials on every request.** For Basic auth that means the user's **password** goes to the API's container log; for Bearer, the whole token.
- **python-jose 3.3.0 has two known CVEs:** CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWE decompression DoS).
- **Every bad or expired token makes the API refetch the realm key.** Anyone can make the API hit Keycloak once per request.
- **The builder's role extraction swallows errors** and decodes each token twice.

**Facts the design rests on** (checked against the live stack and the repo):
- **Issuer:** Keycloak runs with a fixed `KC_HOSTNAME`. Every token's `iss` is the public URL (`<public>/auth/realms/digitaltwins`), even when it was fetched over the internal URL. The internal discovery document reports the same issuer.
- **Key IDs:** tokens are RS256 and carry a `kid`. Access tokens have `typ: Bearer`.
- **`aud` never includes `api`:** no audience mapper exists. So the audience can't identify which backend a token is for.
- **Clients whose tokens reach the services:**
  - `portal-frontend`: the portal app and GUI plugins. It calls the API and the builder.
  - `api`: Basic auth, `/login`, `UploadClient`, the CLI and `util/populate-cpu-burn-assay.sh`. The API also relays these tokens to the builder.
  - No other client's tokens reach either service.

## Decisions

The first three are my recommendations, explained in chat; you can override any of them here.

1. **Library: PyJWT `[crypto]==2.15.1`** (released 2026-09-28), replacing python-jose in both services. The builder also drops `python-keycloak`, which it used only to fetch the key.
   - PyJWT is actively maintained.
   - Its key-set support selects the key by `kid`.
   - Its `issuer` and `require` options are built in.
2. **Issuer: read from Keycloak's discovery document**, `{KEYCLOAK_BASE_URL}/realms/{realm}/.well-known/openid-configuration`, over the internal URL. It is cached along with the keys.
   - No new configuration, and it can't drift from `KC_HOSTNAME`.
   - A misconfiguration fails loudly, with every token rejected, rather than quietly.
   - Rejected: building it from `KEYCLOAK_PUBLIC_URL`. The API would need a new variable, the builder's stale default would need fixing, and the template already warns that the value must match `KC_HOSTNAME`.
3. **Clients: accept `azp` ∈ {`portal-frontend`, `api`}** in both services, as a constant in each service's code.
   - This matches every caller in the repo.
   - `api` service-account tokens (`client_credentials`) still pass, but they have no upload or admin role, so they can only reach read routes.
   - Best practice is an audience check (RFC 9068), which needs Keycloak audience mappers on the live realm. It is recorded in the ADR as a follow-up.
4. **The CLI uses the shared verifier too** (your answer).
5. **Sharing:** the same pattern as the migration runner.
   - The verifier lives in `services/api/src/digitaltwins/core/keycloak_verifier.py`, needing only the standard library and PyJWT.
   - The builder carries a byte-identical copy, `services/builder/app/client/keycloak_verifier.py`.
   - A builder unit test compares the two, `make test-builder` mounts the API's file, and the CI builder filter includes it.
   - Each service keeps its own user object and role checks, so their callers don't change.

## The verifier

- **Construction:** `KeycloakVerifier(base_url, realm, allowed_clients, ssl_context)`, plus `from_env(allowed_clients, base_url=None)`.
  - `from_env` reads `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_VERIFY_SSL` and `KEYCLOAK_CA_CERT`.
  - The builder passes its own base URL, so its fallback to `KEYCLOAK_PUBLIC_URL` stays in the builder.
- **`verify(token) -> claims`** raises `InvalidToken` or `KeycloakUnavailable`.
- **Key:** taken from the realm key set at `{base}/realms/{realm}/protocol/openid-connect/certs`, built from the internal base URL. The `jwks_uri` that discovery advertises is public and can't be reached from inside the containers.
  - The key is selected by `kid`. Only RS256 is accepted, hardcoded, so `KEYCLOAK_ALGORITHM` is no longer read.
  - An unknown `kid` triggers a refetch, **at most once every 60 seconds**. An expired token, or one with a bad signature, never triggers a fetch.
- **Claims:**
  - required: `exp`, `iat`, `iss`, `azp`, `typ`
  - `iss` must equal the discovery issuer
  - `azp` must be in the allowed set
  - `typ` must be `Bearer`, so ID and refresh tokens are rejected
  - `aud` is not checked (see decision 3)
- **TLS:** verified by default. `KEYCLOAK_CA_CERT` sets the CA bundle, and `KEYCLOAK_VERIFY_SSL=false` opts out, with a warning in the log. On the platform, the internal URL is plain http, so nothing changes there.
- **Errors:**
  - `KeycloakUnavailable` only when Keycloak can't be reached and nothing usable is cached. The services answer 503.
  - Everything else is `InvalidToken`. The services answer 401 with a generic detail and `WWW-Authenticate: Bearer`.
  - The reason is logged server-side, never the token.

## Steps

Each step is test-first, and each numbered step is one atomic commit.

0. **Sync this plan.** Run `gitleaks`. Draft the ADR (below) alongside it.
1. **`fix(api)`: stop logging credentials.**
   - Red: a test sends Basic and Bearer requests, captures stdout and the log, and asserts neither the password nor the token appears.
   - Green: remove the two `print`s in `validate_credentials`. Also remove the one in `auth_basic` that prints Keycloak's failure response, if it can carry user input.
2. **`feat(api)`: add the shared verifier** (`digitaltwins/core/keycloak_verifier.py`) and swap python-jose for PyJWT in `requirements-prod.txt`.
   - Tests (`tests/test_keycloak_verifier.py`): a local RSA key, with a discovery document and key set served by a `http.server` thread on the loopback (works under `--network none`). Cases:
     - a valid token returns its claims
     - each of these is rejected: wrong `iss`, `azp` not allowed, `azp` missing, `typ` not `Bearer`, expired, `alg: none`, HS256 signed with the public key
     - a rotated key (new `kid`) is accepted after one refetch
     - unknown `kid`s within the cooldown cause no further fetches (count the server's hits)
     - Keycloak down with nothing cached raises `KeycloakUnavailable`; down with keys cached still verifies
     - TLS: a CA bundle is used, and the opt-out logs a warning
3. **`refactor(api)`: the API and the CLI use the verifier.**
   - `auth.py`:
     - `auth_bearer` and `auth_basic`, which checks the token it just obtained, call one lazily built verifier with `ALLOWED_CLIENTS = {"portal-frontend", "api"}`.
     - Errors map to 401 or 503 as above.
     - `get_keycloak_public_key`, the retry, and the `KEYCLOAK_ALGORITHM` read are removed.
     - The returned dict, `{username, token, claims}`, is unchanged.
   - `keycloak_login.verify_token` uses the same verifier and allowed clients.
   - `KEYCLOAK_ALGORITHM` is removed from `services/api/docker-compose.yml` and `.env.template`, since nothing reads it any more.
   - Tests:
     - `test_auth_roles.py` mints tokens with `iss`, `azp` and `typ`, and replaces the verifier's key source rather than `get_keycloak_public_key`.
     - New: a token from another client gets 401; the 401 detail is generic; Keycloak down gives 503.
     - `test_import_dataset_cli.py` follows the new `verify_token`.
4. **`refactor(builder)`: the builder uses the verifier.**
   - Copy the file, with an identity test like the migration runner's, the `Makefile` mount and the CI path filter.
   - `KeycloakClient` keeps its interface, `get_user_info` and `get_keycloak_client()`, so tests' `FakeKeycloak` and every caller are untouched.
     - Inside, one `verify()` per request.
     - Roles are still filtered to admin, researcher and clinician, and errors are no longer swallowed.
     - The key URL still comes from `KEYCLOAK_BASE_URL`, falling back to `KEYCLOAK_PUBLIC_URL`.
   - `get_current_user` maps `KeycloakUnavailable` to 503 and `InvalidToken` to a generic 401.
   - `requirements.txt`: PyJWT in; python-jose and python-keycloak out.
   - **Defaults:**
     - `KEYCLOAK_VERIFY_SSL` becomes `true` in `services/builder/docker-compose.yml` and in `.env.template` (the API doesn't set it, so it already verifies).
     - The builder's stale `KEYCLOAK_PUBLIC_URL` default, `https://130.216.216.243:8009`, which lacks `/auth`, becomes `http://localhost/auth`, matching `.env.template`.
   - Tests:
     - `get_current_user` gives 401, 503, and the role filtering
     - `test_keycloak_config.py` still covers the base URL choice
5. **`docs`:**
   - the ADR
   - mark the follow-up done in the 2026-10-20 ADR
   - the Keycloak rows in the builder README
   - the walkthrough, synced to artifacts, then `gitleaks`
6. **Live check: I'll ask before restarting** the builder, since that stops its plugin backends. After `docker compose up -d --build api builder`:
   - an `api` password-grant token is accepted by `/api/...` and `/api/builder/...`
   - a token from another client (the `airflow` direct grant) gets 401 from both
   - a tampered token gets 401
   - Keycloak stopped briefly, with keys still cached, keeps verifying
   - log in through the portal by hand to confirm `portal-frontend` tokens work. This one is for you, in the browser.

## Breaking changes for deployments

- **Tokens from clients other than `portal-frontend` and `api` are rejected** by the API and the builder.
- **`KEYCLOAK_ALGORITHM` is no longer read.** Only RS256 is accepted, which is the realm's algorithm.
- **The builder verifies Keycloak's TLS by default.** This matters only when it reaches Keycloak over https, standalone; set `KEYCLOAK_CA_CERT` or opt out.
- **Dependencies:** python-jose and python-keycloak are removed, and PyJWT is added. Rebuild both images.

## Draft ADR: `2026-10-21-one-keycloak-token-verifier.md`

- **Context:** the three verifiers and their gaps, and the facts listed above.
- **Options:**
  - Library: PyJWT (chosen) or python-jose bumped.
  - Issuer: discovery (chosen) or `KEYCLOAK_PUBLIC_URL`.
  - Who is accepted: an `azp` allowlist (chosen), an `aud` check with Keycloak audience mappers, or no check.
  - Sharing: a verbatim copy plus a test (chosen, as for the migration runner), or a shared package.
- **Decision:** as above.
- **Consequences:**
  - Other clients' tokens are rejected.
  - Key fetches are bounded.
  - Errors are generic.
  - The audience check is a follow-up that needs realm changes.
  - Two copies of the verifier must change together.

## Verification

- `make test-api` and `make test-builder` pass. Baselines: api 362 passed (1 skipped); builder 214 passed (11 skipped).
- The verifier tests run inside the normal unit suites. The loopback server needs no network.
- The live check in step 6.
