# Keycloak

The platform's identity provider: one realm, `digitaltwins`, served at `/auth` behind the gateway.

## Purpose

Every sign-in goes through Keycloak (OIDC). Each platform service has a client in the realm, and the
API and the builder verify the realm's access tokens. Read [REALM.md](REALM.md) before changing the
realm: it lists every client, role, group and seeded user, and which secret belongs to which client.
For which service uses which client, see
[docs/architecture.md](../../docs/architecture.md#keycloak-clients).

## Status

Active. The root `docker-compose.yml` includes this folder's `docker-compose.yml`.

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | The `keycloak` service (Keycloak 26.3.2, production mode, HTTP behind the gateway) |
| `digitaltwins-realm.json.template` | The realm. `util/gen-realm.sh` renders it into `import/digitaltwins-realm.json` |
| `import/` | The rendered realm (git-ignored). Mounted at `/opt/keycloak/data/import` |
| `digitaltwins-login-theme/` | The login page theme, set as the realm's `loginTheme`. It has its own README |
| `REALM.md` | Reference for the realm template |
| `docker-compose-https.yml` | A Keycloak that terminates TLS itself, with a Java keystore. Not included by the root compose |

## Connects to

| Peer | How |
|---|---|
| Postgres | The `keycloak` database: `KC_DB_URL` (`database:5432/keycloak`), `KEYCLOAK_DB_USER`, `KEYCLOAK_DB_PASSWORD` |
| gateway | `/auth/` → `keycloak:8080`. Keycloak trusts the gateway's `X-Forwarded-*` headers (`KC_PROXY_HEADERS: xforwarded`) |
| Every other service | Browsers use the public address (`KEYCLOAK_PUBLIC_URL`); containers use `http://keycloak:8080/auth` (`KEYCLOAK_INTERNAL_URL`, or `KEYCLOAK_BASE_URL` for the api and builder) |

## Configuration

Set in the root `.env` (rendered from `.env.template`).

| Variable | Use |
|---|---|
| `KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_BOOTSTRAP_ADMIN_PASSWORD` | The master realm's bootstrap admin |
| `KC_HOSTNAME` | The public address, `<protocol>://<domain>/auth`. It becomes the `iss` claim of every token |
| `KC_HOSTNAME_STRICT`, `KC_HOSTNAME_STRICT_HTTPS` | `false` for localhost over HTTP, `true` for a real domain |
| `KC_HTTP_RELATIVE_PATH` | `/auth`, the gateway route |
| `KEYCLOAK_DB_USER`, `KEYCLOAK_DB_PASSWORD` | Database login. Not in `.env.template`; the compose file's defaults match the role `services/postgres/keycloak_init.sql` creates |

The client secrets are not set here: `util/gen-realm.sh` writes them into the realm import from
`secrets.env`, and each consuming service reads the same variable from `.env` (see REALM.md).

## Run & test

No automated tests. The host publishes port 8009 for direct admin access; normal traffic goes through
the gateway at `/auth`.

## Gotchas

- **The realm is imported on first boot only** (`--import-realm`, empty `keycloak` database). Editing
  the template changes nothing in a running realm: change it live in the admin console, or recreate
  Keycloak's data. See REALM.md.
- **`KC_HOSTNAME`, `KEYCLOAK_PUBLIC_URL` and `ORTHANC_KEYCLOAK_URL` must name the same address**
  (`ORTHANC_KEYCLOAK_URL` with a trailing slash), or token issuer checks fail. `.env.template` derives
  all three from `PLATFORM_PROTOCOL` and `PLATFORM_DOMAIN`; regenerate `.env` rather than editing one.
- **Redirect URIs live in the realm.** Moving a service's route means updating its client's
  `redirectUris` in the live realm too.
- `util/gen-realm.sh` fails if any secret it substitutes is blank in `secrets.env`.

## Related ADRs

- [One Keycloak token verifier for the API, its CLI and the builder](../../docs/decisions/2026-10-21-one-keycloak-token-verifier.md)
- [Provision SEEK accounts just-in-time from Keycloak identity](../../docs/decisions/2026-10-14-seek-jit-user-provisioning.md)
