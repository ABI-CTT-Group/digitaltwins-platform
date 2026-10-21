# One Keycloak token verifier for the API, its CLI and the builder

- **Date:** 2026-10-21
- **Status:** Accepted. Done as a follow-up of [2026-10-20-merge-portal-backend-into-api-codebase](2026-10-20-merge-portal-backend-into-api-codebase.md) ("one Keycloak verifier").

## Context

Three places checked Keycloak access tokens: the API's Bearer and Basic auth (`app/routers/auth.py`), the import CLI (`digitaltwins/cli/keycloak_login.py`) and the builder (`app/client/keycloak.py`). All three used python-jose 3.3.0 with the realm's single public key. Each checked only the signature and the expiry:

- **Any token from the realm passed.** No check looked at the issuer (`iss`), the client the token was issued to (`azp`), or the token type, so ID tokens and tokens issued to Grafana, SEEK or Airflow were accepted.
- **The API refetched the realm key for every token that failed,** expired ones included, so anyone could make it call Keycloak once per request. The builder never refetched, so a key rotation broke it until it restarted.
- **TLS and errors differed between the services:**
  - TLS: the API never verified Keycloak's certificate; the builder didn't by default.
  - Keycloak down: the API answered 503, the builder 401.
  - Bad token: the API returned the library's error text, the builder a generic message.
- **python-jose 3.3.0 has two known CVEs:** CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWE decompression DoS).
- **The API printed incoming Basic-auth credentials and bearer tokens** to its log on every request.

Facts the design rests on:

- **Issuer:** Keycloak runs with a fixed `KC_HOSTNAME`, so every token's `iss` is the public URL, however the token was obtained. The realm's discovery document, fetched over the internal URL, reports the same issuer.
- **Keys:** tokens are RS256 and carry a `kid`. The realm's key set also lists an encryption key.
- **Audience:** no audience mapper exists, so `aud` never names `api` and can't identify the backend a token is meant for.
- **Who calls the services:** only two clients' tokens reach them.
  - `portal-frontend`: the portal and the GUI plugins it hosts.
  - `api`: Basic auth, `/login`, the CLI and scripts. The API relays these tokens to the builder.

## Alternatives Considered

### Library
- **PyJWT (chosen).** Actively maintained. Its key-set support picks the key by `kid`, and issuer and required-claim checks are built in.
- **python-jose, bumped to a fixed release.** A smaller dependency change, but we would hand-write the key-set fetch and `kid` lookup, on a library that went years between releases.

### Where the expected issuer comes from
- **Keycloak's discovery document, over the internal URL (chosen).**
  - Needs no configuration and can't drift from `KC_HOSTNAME`.
  - It comes over the same channel already trusted for the keys.
  - A misconfiguration rejects every token, which is loud, rather than drifting quietly.
- **Built from `KEYCLOAK_PUBLIC_URL`, as SEEK does.**
  - Explicit, and independent of what Keycloak reports about itself.
  - But the API would need a new variable, and the value must be kept equal to `KC_HOSTNAME` by hand. The `.env` template already warns about this.

The issuer check is defence in depth: keys come only from our own realm, so a token from another realm already fails the signature check.

### Which callers are accepted
- **An `azp` allowlist, {`portal-frontend`, `api`}, fixed in each service's code (chosen).**
  - It matches every caller in the repo and rejects every other client's tokens.
  - A fixed list is easier to audit than an override setting.
- **An audience check (RFC 9068).** This is best practice: a token names the backends it is for.
  - It needs Keycloak audience mappers on `portal-frontend` and `api`.
  - The API's token relay to the builder means `builder` must be in the audience too.
  - The realm imports only on first boot, so live realms would need patching.
- **No check:** the old behaviour.

### Sharing
- **A verbatim copy kept identical by a test (chosen),** as for the [migration runner](2026-10-21-builder-numbered-sql-migrations.md). The verifier needs only the standard library and PyJWT.
- **A shared package:** more build plumbing than the roughly 130 lines it would share.

## Decision

- **The verifier:** `services/api/src/digitaltwins/core/keycloak_verifier.py`, with a byte-identical copy at `services/builder/app/client/keycloak_verifier.py`. `services/builder/tests/test_shared_with_api.py` checks the copy, and CI runs the builder job when the API's file changes.
- **What it accepts:** an RS256 access token (`typ: Bearer`) that is unexpired, carries `iat`, and is signed by a realm key chosen by `kid`. Its `iss` must equal the discovery issuer, and its `azp` must be in the caller's allowed set.
- **Fetching:**
  - The issuer and keys come over the internal URL, not the discovery document's public `jwks_uri`, and are cached.
  - An unknown `kid` refetches at most once a minute. An expired or badly signed token never causes a fetch.
  - If a refetch fails, the cached keys stay in use.
- **TLS:** Keycloak's certificate is verified unless `KEYCLOAK_VERIFY_SSL=false`, which logs a warning. `KEYCLOAK_CA_CERT` names a CA bundle.
- **Errors:** `InvalidToken` becomes 401 with a generic detail and `WWW-Authenticate: Bearer`; the reason is logged. `KeycloakUnavailable`, raised only when nothing is cached, becomes 503.
- **Each service** declares `ALLOWED_CLIENTS = {"portal-frontend", "api"}` and keeps its own user object and role checks. The CLI uses the same allowed clients as the API.
- **Removed:** python-jose (both services), python-keycloak (the builder), `KEYCLOAK_ALGORITHM`, and the API's logging of credentials.

## Consequences

- **Tokens from any other client are now rejected,** including hand-run scripts that used another client's direct grant. Service-account tokens of the `api` client still pass, but they carry no upload or admin role, so they reach read routes only.
- **Bad tokens can no longer drive traffic to Keycloak,** and a key rotation is picked up without a restart.
- **A Keycloak outage** doesn't affect tokens signed with cached keys.
- **The builder now verifies TLS by default.** Under the platform it reaches Keycloak over internal http, so only a standalone builder on https needs `KEYCLOAK_CA_CERT`, or the opt-out.
- **Follow-up:** audience mappers, then an `aud` check in place of the `azp` allowlist.
- **The two copies of the verifier must change together.**
