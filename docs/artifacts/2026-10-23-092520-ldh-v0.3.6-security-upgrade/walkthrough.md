# Walkthrough: upgrade LDH to v0.3.6 (SEEK 1.18.3 security fix)

## Why

SEEK 1.18.3 (released 2026-10-21) fixes a batch-sharing authorization flaw:

- `Seek::Sharing::SharingCommon#resolve_sharing_params` did not limit the items
  to those the user may **manage**.
- `Policy#update_with_bulk_sharing_policy` saved permission rows before the
  owner-access check could reject the change.

LDH `v0.3.2` (SEEK 1.16.1) still had both lines. NFDI4Health shipped the fix as
LDH `v0.3.6` ("Merge seek1.18.3", nfdi4health/ldh#93). Because SEEK creates an
account for every Keycloak user on first login, any platform user can reach the
batch-sharing endpoints.

## Changes

| File | Change |
|---|---|
| `.env.template` | `LDH_RELEASE=v0.3.2` → `v0.3.6` |
| `services/seek/ldh-deployment/keycloak_oidc.rb` (submodule) | Patch `Seek::Config` from `Rails.autoloaders.main.on_load('Seek::Config')` instead of at file load. Make `jwks_uri` an absolute internal Keycloak URL |
| `services/seek/ldh-deployment/test/keycloak_oidc_check.rb` (submodule, new) | Read-only check that the browser-login provider can fetch Keycloak's signing keys |
| `docs/seek-integration.md` | New version, the upgrade procedure, and the known migration issue |

### Why `keycloak_oidc.rb` had to change

Under `v0.3.6`, Rails failed to boot with
`NameError: uninitialized constant Seek` at `keycloak_oidc.rb:8`. SEEK 1.18
(Rails 7.2) uses `config.autoload_lib`, so `lib/seek/config.rb` is managed by
Zeitwerk and can't be referenced while `config/initializers` run. Our file
reopened `Seek::Config` at load time.

| Alternative | Why we didn't use it |
|---|---|
| `to_prepare` | Too late. The middleware stack, including `seek_omniauth.rb`'s `OmniAuth::Builder` block that reads `omniauth_providers`, is built before the prepare callbacks run |
| `on_load` | Runs when `Seek::Config` is first loaded, which is before that block. This is the one we used |

### Why `jwks_uri` had to become absolute

After the upgrade, browser login to `/seek` through Keycloak failed at the
callback with `Failed to open TCP connection to :80 (... for nil port 80)`.

LDH `v0.3.6` bumps `omniauth_openid_connect` from 0.4.0 to 0.8.0, along with
`openid_connect` 2.3.1, `rack-oauth2` 2.2.1 and `faraday` 2.

| Version | How it gets the id_token signing key |
|---|---|
| 0.4.0 | From the discovery document (`config.jwks`). It never fetched `client_options.jwks_uri` |
| 0.8.0 | Fetches `client_options.jwks_uri` with `OpenIDConnect.http_client.get` exactly as given |

Our `jwks_uri` was a relative path. It relied on `client_options`
`scheme`/`host`/`port`, which only rack-oauth2's `absolute_uri_for` applies (for
the token and userinfo endpoints). Faraday therefore got a URL with no host. The
fix builds `jwks_uri` from `KEYCLOAK_INTERNAL_URL`, the same container-to-container
base that the other server-side calls use.

## Upgrade procedure and findings

1. Back up the SEEK volumes (db, filestore, solr) with the stack stopped.
2. Rehearse on a copy of the database in a separate compose project
   (`PROJECT_NAME` and `-p` set to a throwaway name, another `SEEK_PORT`).
3. `docker compose run --rm --no-deps seek docker/upgrade.sh`.

Findings:

- **The entrypoint doesn't migrate.** `docker/entrypoint.sh` only runs
  `db:setup` on an empty database, so step 3 is required.
- **One-off commands can hit the wrong database.** A fresh `seek` container's
  `config/database.yml` is SQLite until `check_mysql` copies
  `docker/database.docker.mysql.yml`. `db:migrate:status` without that copy
  reported "603 up", which was the wrong database.
- **Duplicate-column failure on migration `20250212145346`.** The upgrade
  stopped with `Duplicate column name 'title'`. `v0.3.2`'s `schema.rb` already
  had `snapshots.title` and `description`, but `v0.3.2` didn't ship the
  migration. The columns matched the migration exactly, so we marked it as
  applied (`INSERT INTO schema_migrations (version) VALUES ('20250212145346')`)
  and reran the upgrade. All 17 remaining migrations then ran, including
  `FixDoorkeeperForeignKeys`, which upstream's `patches/patch20261001.md` warns
  about.

## Verification

| Check | Result |
|---|---|
| Fixed code in the running image (`authorized_for('manage', current_user)` in `sharing_common.rb`) | Present. `v0.3.2` fails this check, `v0.3.6` passes |
| `Seek::Version` | `1.18.3` |
| `schema_migrations` | 603 rows, latest `20260623150237`, none pending |
| Keycloak OIDC provider patched in, `SessionsController` patched, `KeycloakJwtAuth` loaded | PASS |
| `test/keycloak_provisioning_check.rb` | ALL PASSED |
| `seek`, `workers`, `db`, `solr` health | healthy |
| `GET /seek/` on `SEEK_PORT` | 200 |

End to end with the full stack running, using a Keycloak user token from a
password grant (client `api`):

| Check | Result |
|---|---|
| Gateway → SEEK `GET /seek/people/current`, no token | 404 (anonymous) |
| Gateway → SEEK `GET /seek/people/current`, bearer JWT | 200, resolved to the token's SEEK person |
| Gateway → SEEK list endpoints, bearer vs. anonymous | The bearer view includes the user's private investigations, studies, assays, workflows and SOPs, which the anonymous view omits |
| Gateway → API `/api/investigations`, `/studies`, `/assays`, `/assays/{id}`, `/workflows`, `/dashboard/workflows` | All 200, and counts match SEEK's bearer view |
| SEEK `filter[tag]=workflow` / `filter[tag]=tool`, used by the API's querier | Splits the workflows as before (workflow + tool = total) |
| `seek` and `api` logs during the run | No errors |
| `test/keycloak_oidc_check.rb` | Before the `jwks_uri` fix: FAIL, same `nil port 80` error as the browser. After: ALL PASSED |
| Browser login driven with curl: CSRF token → `POST /seek/auth/oidc` → Keycloak login form → callback | Callback 302 to `/seek/` (`SessionsController#create`). The session's `people/current` returns 200 |

## Rollback

Restore the three backed-up volumes, set `LDH_RELEASE=v0.3.2`, and revert the
`keycloak_oidc.rb` change. The migrations are not reversible in place.
