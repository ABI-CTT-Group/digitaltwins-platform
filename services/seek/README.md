# SEEK

The platform's data catalogue: programmes, projects, investigations, studies, assays, SOPs and
workflows, served at `/seek`.

## Purpose

We run the NFDI4Health Local Data Hub (LDH), a distribution of FAIRDOM-SEEK. The API reads and writes
SEEK as the signed-in user, by forwarding their Keycloak token. SEEK verifies the token and creates
the user's SEEK account on first sight. [docs/seek-integration.md](../../docs/seek-integration.md)
explains the authentication, who can see what, which SEEK we run and how to upgrade it.

## Status

Active. The root `docker-compose.yml` includes `ldh-deployment/docker-compose.yml` together with
`network-override.yml`, with `ldh-deployment/` as the project directory.

## Code map

| Path | What it is |
|---|---|
| `ldh-deployment/` | A git submodule: our fork of `nfdi4health/ldh-deployment`, tracking its `abi` branch (see `.gitmodules`) |
| `ldh-deployment/docker-compose.yml` | `db` (MySQL 8.4), `seek` and `workers` (the LDH image), `solr`, and `exporter` (behind the `exporter` profile) |
| `ldh-deployment/keycloak_jwt_auth.rb` | Verifies the Keycloak tokens the API forwards, and provisions accounts. Mounted into the image as a Rails initializer |
| `ldh-deployment/keycloak_oidc.rb` | The "Sign in with Keycloak" browser login, using the same provisioner |
| `ldh-deployment/test/` | Manual checks of the two initializers against a running SEEK |
| `ldh-deployment/docker-compose.env.tpl` | Template for `docker-compose.env`, SEEK's MySQL settings (the rendered file is git-ignored) |
| `network-override.yml` | Platform overrides: joins the services to the platform network, pins the amd64 images, and replaces the submodule's `extra_hosts` |

## Connects to

| Peer | How |
|---|---|
| api | Calls `SEEK_BASE_URL` (`http://seek:3000/seek`) with the user's Keycloak token as a Bearer token |
| Keycloak | Client `seek` (`SEEK_KEYCLOAK_CLIENT_SECRET`). `KEYCLOAK_PUBLIC_URL` for the browser and as the expected token issuer; `KEYCLOAK_INTERNAL_URL` for server-side calls such as fetching the signing keys |
| gateway | `/seek/` → `seek:3000`. SEEK knows its prefix from `RAILS_RELATIVE_URL_ROOT: "/seek"`, set on both `seek` and `workers` |
| Its own stores | MySQL (`db`), Solr, and the volumes `${PROJECT_NAME}_seek_db`, `_seek_filestore`, `_seek_solr` and `_seek_cache` |

## Configuration

| Where | Variables |
|---|---|
| Root `.env` (from `.env.template`) | `LDH_RELEASE` (the LDH image tag), `SEEK_PORT`, `DHO_TERMS`, `NGINX_CONF`, `COMPOSE_PROJECT_NAME`, `SEEK_KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_INTERNAL_URL`, `PLATFORM_PROTOCOL`, `PLATFORM_DOMAIN` |
| `ldh-deployment/docker-compose.env` | `MYSQL_HOST`, `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`. Written by hand from `secrets.env`: see [docs/deployment.md §2.3](../../docs/deployment.md#23-seeks-database-settings) |

## Run & test

No make target and nothing in CI. After an LDH upgrade, run the two checks in `ldh-deployment/test/`
against the running SEEK; each file's header has the command. Then sign in to `/seek` through
Keycloak in a browser.

First-time setup (admin user, features) is in
[docs/deployment.md §5](../../docs/deployment.md#5-bootstrap-seek). The `util/*seek*` scripts handle
admin tasks such as project membership; see [util/SCRIPTS.md](../../util/SCRIPTS.md).

## Gotchas

- **It is a submodule.** After cloning, run `git submodule update --init`. Changes go through a PR on
  the fork's `abi` branch, then a bump of the submodule pointer here.
- **Don't use upstream's `update.sh`.** Follow
  [Upgrading LDH](../../docs/seek-integration.md#upgrading-ldh): the image doesn't migrate its own
  database.
- **SEEK uses MySQL, not the platform's Postgres.** Back up its volumes separately.
- **Provisioning gives an account, not access.** Project membership is an admin action
  (`util/add-seek-project-member.sh`).
- **The images are amd64 only.** `network-override.yml` pins `platform: linux/amd64`, so they run
  emulated on arm64.
- `network-override.yml` uses `!override`, which needs Docker Compose 2.24 or later.

## Related ADRs

- [Provision SEEK accounts just-in-time from Keycloak identity](../../docs/decisions/2026-10-14-seek-jit-user-provisioning.md)
- [SEEK stays on MySQL, upgraded to 8.4](../../docs/decisions/2026-10-23-seek-database-mysql-8.4.md)
- [Register tool datasets in SEEK with a single RO-Crate POST](../../docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md)
- [Title SEEK tools and workflows with the portal name](../../docs/decisions/2026-10-15-seek-title-from-portal-name.md)
- [Link an assay to its workflow through an auto-created SEEK SOP](../../docs/decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md)
