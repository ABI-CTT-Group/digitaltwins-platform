# Platform ↔ SEEK: authentication, access, and visibility

How the DigitalTWINS platform talks to SEEK, what that connection is allowed to
see, and how SEEK's own visibility model gates (or doesn't) different callers.
Written for anyone reasoning about **who can see what** — especially in a
locked-down / airgapped deployment.

## TL;DR

- The platform authenticates to SEEK using **Keycloak-issued JWT Bearer tokens**.
- When a user interacts with the portal, the API forwards the user's Keycloak JWT to SEEK on a per-request basis.
- SEEK intercepts these tokens via a custom initializer (`keycloak_jwt_auth.rb`), cryptographically verifies them against Keycloak's JWKS endpoint, and maps the token's `sub` UUID to a specific SEEK user via the `identities` table. A Keycloak user SEEK has not seen yet gets a SEEK account created on the spot (see [Account provisioning](#account-provisioning)).
- Therefore, every platform→SEEK request runs **as the authenticated user** and sees exactly that user's **authorized view**: public items + items shared with them + items in their projects + what they own. 
- The legacy global `SEEK_API_TOKEN` singleton has been completely removed to prevent unauthorized cross-tenant data access.

## How the platform authenticates to SEEK

The API's SEEK client extracts the Keycloak token from the caller and dynamically injects it into every downstream SEEK request:

```python
# services/api/src/digitaltwins/seek/querier.py
self._api_token = api_token # Injected via Depends(get_querier)
...
"Authorization": "Bearer " + self._api_token
```

On the SEEK side, the request is intercepted before hitting Rails controllers. We monkey-patch the `AuthenticatedSystem` module to decode and verify the JWT signature against the Keycloak JWKS public keys. 

If valid, SEEK looks up the Keycloak UUID (`sub`) in the `identities` table (where `provider: 'oidc'`). If a match is found, the request executes as that SEEK user. If not, SEEK provisions the account first (below) and then runs the request as the new user.

## Account provisioning

There is no batch Keycloak→SEEK sync. SEEK creates the account the first time it sees a Keycloak user, whichever path comes first:

- an API call carrying the user's JWT (`keycloak_jwt_auth.rb`, `KeycloakJwtAuth.provision_user`), or
- the user's first "Sign in with Keycloak" at `/seek` (`keycloak_oidc.rb` overrides `SessionsController#create_user_from_omniauth` to call the same provisioner).

It creates an active SEEK User, a Person (name and email from the token's `given_name`, `family_name`, `email`) and the `identities` row (`provider: 'oidc'`, `uid: <sub>`), so nobody sees SEEK's "create your profile" form. The browser path relies on SEEK's admin setting *omniauth user create* being on.

It deliberately does **not** provision when:

- **The email already belongs to a SEEK Person** (case-insensitive), e.g. a local SEEK account or an admin-created profile. It never links by email: the realm does not verify emails, so that would let one Keycloak user take over another's SEEK account. The call stays anonymous, the browser login is refused, and SEEK logs `Not provisioning sub=…: email already used by Person <id>`. An admin resolves it with the `util/*seek*` scripts.
- **The token has no email**, or **`preferred_username` starts with `service-account-`** (client-credentials tokens). These stay anonymous, as before.

Provisioning gives an account, not access: **project membership is still an admin action** (`util/add-seek-project-member.sh`). A new user can read public items and own what they create, but can only register tools/workflows into projects they have been added to.

## What the token grants

Because every request executes as the caller's specific SEEK user, the platform is strictly bound by SEEK's internal sharing and permission models.

A user will only see:
- Items marked as Public.
- Items explicitly shared with their SEEK user account.
- Items belonging to Projects they are a member of.
- Items they have personally created/owned.

## Three callers, three scopes

| Caller | How they auth | What they can see |
|---|---|---|
| **Anonymous** (logged-out browser at `/seek`) | nothing | only **SEEK-public** items (none, if everything is private) |
| **SEEK user** (login at `/seek`) | SEEK account | that user's **SEEK permissions** — public + own + shared-with-them |
| **Platform user** (login at `/` via Keycloak) | Keycloak → backend queries SEEK **forwarding the JWT** | **Exactly the same** as if they were logged into the SEEK UI directly. |

## SEEK-UI visibility (the anonymous / world case)

SEEK enforces its own per-item sharing at its web UI, independent of the platform:

- **Private items are not anonymously browsable.** A logged-out visitor to
  `/seek` sees only items shared publicly. If nothing is public, they see nothing
  — no projects, studies, or assays.
- Two extra levers for defense-in-depth:
  1. **SEEK's server-level anonymous-access setting** — whether logged-out users
     may view public content at all.
  2. **The gateway.** `/seek` is currently an nginx **passthrough** (no auth at
     the edge — see the gateway-routes table in `util/README.md`), so SEEK itself
     is the only gate. A locked-down deployment could additionally restrict
     `/seek` at the network/gateway layer.

## Hardening notes for a secure / airgapped deployment

- **Watch for provisioning refusals:** a user whose email clashes with an existing SEEK Person stays anonymous until an admin resolves it (see [Account provisioning](#account-provisioning)). Grep the SEEK log for `Not provisioning`.
- **Default new items to private** so a study isn't inadvertently made public by
  accepting a default sharing policy.
- **After a `portal-restore`**, SEEK's user DB is the *source's* — that includes
  the source's public/private choices and its user accounts. Review the imported
  sharing state (and prune source users) rather than assuming your local posture.

## Which SEEK we run

We run the **NFDI4Health Local Data Hub (LDH)**, not stock FAIRDOM-SEEK. Three
upstreams are involved:

| | What it is | How we consume it |
|---|---|---|
| [FAIRDOM-SEEK](https://github.com/seek4science/seek) (`fairdom/seek` on Docker Hub) | The upstream Rails application | Indirectly, through LDH. We only use FAIRDOM's Solr image, `fairdom/seek-solr:8.11.4`, directly |
| [nfdi4health/ldh](https://github.com/nfdi4health/ldh) (`ghcr.io/nfdi4health/ldh`) | A downstream distribution of the SEEK codebase with NFDI4Health changes, maintained by SEEK's core developers. We run `v0.3.6`, which reports SEEK `1.18.3` | The `seek` and `seek-worker` image, pinned by `LDH_RELEASE` in `.env` |
| [nfdi4health/ldh-deployment](https://github.com/nfdi4health/ldh-deployment) | A deployment kit with no application code: a compose file for MySQL, LDH and Solr, plus nginx configs, backup/restore scripts and `.env` templates | Forked to `ABI-CTT-Group/ldh-deployment` and mounted as the submodule `services/seek/ldh-deployment`, tracking the fork's `abi` branch |

Our fork adds the Keycloak integration (`keycloak_jwt_auth.rb`,
`keycloak_oidc.rb`, the provisioning check script) and the matching
`docker-compose.yml` and `.env.tpl` changes.

We fork only `ldh-deployment`, not `ldh`, because we don't change LDH's
application code. Our Keycloak initializers are mounted read-only into the stock
image at `/seek/config/initializers/`, so taking a new LDH release only requires
bumping `LDH_RELEASE`. The trade-off is that the initializers depend on SEEK's
internals, which aren't a stable interface: re-run the provisioning check after
every bump.

Consequences:

- **`fairdom/seek:<tag>` is not a drop-in replacement** for the LDH image. It
  lacks the NFDI4Health changes and is versioned independently. To find the SEEK
  version inside an LDH tag, read `config/version.yml` in the image.
- **Keep Solr compatible with the SEEK version inside LDH** whenever you bump
  `LDH_RELEASE`.
- **Upstream changes arrive through two separate channels**: application changes
  through `LDH_RELEASE`, and compose, nginx and script changes through the fork.
  The fork's `main` is kept identical to upstream; update it with
  `gh repo sync ABI-CTT-Group/ldh-deployment -b main` and never commit to it. Our
  changes live on `abi`, the fork's default branch, which is protected
  (PRs only, no force-push). To take upstream changes, merge `main` into `abi`
  through a PR, then bump the submodule pointer. To see how far `abi` is behind
  upstream, run
  `gh api repos/ABI-CTT-Group/ldh-deployment/compare/abi...main --jq '.ahead_by'`.
- **For security fixes, watch releases on `nfdi4health/ldh`, not on FAIRDOM-SEEK.**
  A SEEK release (announced on the FAIRDOM Slack) only reaches us once
  NFDI4Health merges it into an LDH release. `ldh-deployment` has no releases,
  so its changes show up only as commits to `main`.
- **SEEK has its own MySQL (`mysql:8.4`)**, unlike the rest of the platform,
  which shares Postgres. We follow upstream here; see
  [the ADR](decisions/2026-10-23-seek-database-mysql-8.4.md). Back up the
  `seek_db` volume separately.
- **Upstream's `exporter` service** (`fmeineke/ldh-exp`, export to NFDI4Health's
  Health Study Hub) is behind the `exporter` compose profile and doesn't start by
  default. Start it with `docker compose --profile exporter up -d exporter`.
- **Don't use upstream's `update.sh`.** It assumes a standalone deployment; in
  the platform, follow [Upgrading LDH](#upgrading-ldh) below.

### Upgrading LDH

The image's entrypoint does not migrate the database, so bumping `LDH_RELEASE`
needs these steps:

1. Stop the stack and back up the `${PROJECT_NAME}_seek_db`, `_seek_filestore`
   and `_seek_solr` volumes.
2. Set `LDH_RELEASE` in `.env`, then start only `db` and `solr`:
   `docker compose up -d --wait db solr`.
3. Migrate: `docker compose run --rm --no-deps seek docker/upgrade.sh`.
4. Start the rest (`docker compose up -d`) and run both checks in
   `services/seek/ldh-deployment/test/`: `keycloak_provisioning_check.rb`
   (API-token account provisioning) and `keycloak_oidc_check.rb` (browser
   login's server-side calls to Keycloak). Then log in to `/seek` through
   Keycloak in a browser.

One-off `rake` or `rails runner` commands in a fresh `seek` container need
`cp docker/database.docker.mysql.yml config/database.yml` first. Without it,
they silently use the image's default SQLite database. `docker compose exec`
into the running `seek` container doesn't need this.

**Known issue, `v0.3.2` → `v0.3.6`:** step 3 fails with
`Mysql2::Error: Duplicate column name 'title'`. `v0.3.2`'s `schema.rb` already
contains `snapshots.title` and `description`, so a database created with
`db:setup` has the columns but no record of migration `20250212145346`. Mark
that migration as applied, then rerun step 3:

```sql
INSERT INTO seek.schema_migrations (version) VALUES ('20250212145346');
```

Upstream's [patch notes](https://github.com/nfdi4health/ldh-deployment/blob/main/patches/patch20261001.md)
cover a related failure in `Fix doorkeeper foreign keys`. We didn't hit that
one.

**Changing the MySQL or Solr image:** back up first, as in step 1. A newer
MySQL upgrades the data directory in place on its first start (the `db` log
shows `Server upgrade from … completed`), and older versions can't read it
afterwards. After a Solr change, rebuild the search index with
`docker compose exec seek bundle exec rake seek:reindex_all`.

## Where the pieces live

| Piece | Location |
|---|---|
| SEEK JWT Auth Interceptor + account provisioning | `services/seek/ldh-deployment/keycloak_jwt_auth.rb` |
| SEEK browser OIDC login (uses the same provisioner) | `services/seek/ldh-deployment/keycloak_oidc.rb` |
| Provisioning check script | `services/seek/ldh-deployment/test/keycloak_provisioning_check.rb` |
| Token forwarded (bearer) | `services/api/src/digitaltwins/seek/querier.py` |
| API Dependency Injection | `services/api/app/routers/dependencies.py` (`get_querier`) |
| `/seek` gateway route | passthrough — see gateway-routes table in `util/README.md` |
