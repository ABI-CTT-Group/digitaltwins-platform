# Plan: merge upstream `main` into the fork's `abi` branch (ldh-deployment)

## Context

The fork `ABI-CTT-Group/ldh-deployment` now keeps `main` identical to
`nfdi4health/ldh-deployment` (`0cf728c`). Our work lives on `abi` (`d78fbf8`,
the default branch, protected: PR + 1 approval, admins can bypass). The platform
pins the submodule `services/seek/ldh-deployment` to `abi`.

`abi` is 14 upstream commits behind (merge-base `4e8e040`, Feb–Oct 2026):
- MySQL 8.0 → 8.4.
- Solr `8.11` → `8.11.4`.
- New healthchecks, `RAILS_LOG_LEVEL`, and removal of `links`.
- A new `exporter` service, for export to NFDI4Health's Health Study Hub.
- `LDH_EXP_RELEASE` in `.env.tpl`.
- A reworked `update.sh`, README updates, and `patches/patch20261001.md`.

**Goal:** bring these into `abi` without breaking the platform's SEEK (Keycloak
login and API JWT, the `/seek` sub-path, the platform network), and upgrade the
live SEEK database to MySQL 8.4.

**Decisions made with the user:**
- Take MySQL 8.4 in this merge. The live data upgrade is one-way, so it is backed
  up and rehearsed first.
- Keep `exporter`, but off by default (compose profile).

## Conflict analysis (done read-only, before merging)

Files changed on both sides: only `docker-compose.yml` and `.env.tpl`. Files
changed only upstream, merged as-is: `README.md`, `update.sh`,
`patches/patch20261001.md`. Files changed only on `abi`, unaffected:
`keycloak_*.rb`, `test/*`.

Both sides made the same `${PWD}/…` → `./…` volume change, so that part will not
conflict. Expected conflict hunks and their resolution:

| Area in `docker-compose.yml` | `abi` | upstream | Resolution |
|---|---|---|---|
| `db.image` | `mysql:8.0` | `mysql:8.4` | **8.4** (user decision) |
| `db.healthcheck` | root ping, every 30s | `MYSQL_USER` ping, every 10s | **upstream**. `docker-compose.env` has `MYSQL_USER`/`MYSQL_PASSWORD`, and it means less divergence |
| `seek.environment` | `/seek` root, Keycloak vars | adds `RAILS_LOG_LEVEL: info`, root `/` | **ours + `RAILS_LOG_LEVEL`** |
| `seek.healthcheck` | `curl /seek/` | `curl /up` | **ours**. SEEK's internal nginx only serves `^/seek(/.*\|$)`, so `/up` would 404 and `seek` would never turn healthy |
| `links` (seek, workers) | kept | removed | **remove**. Deprecated; the services share the platform network |
| `depends_on` | `condition: service_healthy` | plain list | **ours** (needs the db and solr healthchecks, which both sides have) |
| `workers.healthcheck` | `delayed_job` check | none | **ours** |
| `solr.image` | `8.11` | `8.11.4` | **8.11.4** |
| `solr.healthcheck` | `/solr/admin/info/system` | `/solr/seek/admin/ping` | **upstream** (stricter: the `seek` core must exist) |
| `exporter` (new) | — | `fmeineke/ldh-exp:${LDH_EXP_RELEASE}` | **keep, gated**: `profiles: [exporter]`, `${LDH_EXP_RELEASE:-latest}`, `LDH_SOURCE: http://seek:3000/seek` (sub-path; check if the exporter is ever enabled) |
| `volumes:` | `${PROJECT_NAME}_seek_*`, not external | unchanged from base | **ours** (upstream didn't touch it) |

`.env.tpl`: keep `# LDH_RELEASE=latest` and `LDH_RELEASE=v0.3.6` (bumping the
stale `v0.3.2`), and add upstream's `LDH_EXP_RELEASE=latest`.

## Steps

### 0. Record the plan

Copy this plan to
`docs/artifacts/<YYYY-MM-DD-HHMMSS>-ldh-deployment-upstream-merge/implementation_plan.md`
and draft an ADR, `docs/decisions/2026-10-23-seek-database-mysql-8.4.md`. The
ADR's decision: stay on MySQL (now 8.4, as upstream) rather than move SEEK to
the platform's Postgres. Postgres is supported by SEEK, but the move means
converting the schema and data and leaving upstream's tested setup.

### 1. Merge in the submodule (git only, no runtime changes)

1. `git -C services/seek/ldh-deployment fetch origin`, then
   `git switch -c merge/upstream-main-2026-10 origin/abi`.
2. `git merge --no-ff origin/main`, then resolve the conflicts per the table.
3. Check that the merged files parse in context:
   - `docker compose config` from the platform root succeeds and does not list
     `exporter`.
   - `docker compose --profile exporter config` succeeds, with
     `fmeineke/ldh-exp:latest`.
4. Commit the merge (message lists the resolutions), push the branch, and open a
   PR into `abi`. Merge it with **"Create a merge commit"**, not squash or rebase,
   so `main`'s history stays an ancestor of `abi` and future merges only see new
   upstream commits. The PR needs one approval or an admin bypass.

### 2. Platform-side wiring (platform repo, `dev_chinchien`)

- `services/seek/network-override.yml`: add `exporter` with
  `networks: [digitaltwins-platform]` (and `platform: linux/amd64` if the image
  is amd64-only; check with `docker manifest inspect`). This is inert unless the
  profile is enabled.
- `docs/seek-integration.md`:
  - Solr `8.11.4` and MySQL `8.4` in "Which SEEK we run".
  - The exporter profile.
  - That upstream's `update.sh` assumes a standalone deployment; the platform
    uses the "Upgrading LDH" steps.

### 3. Runtime upgrade to MySQL 8.4 and Solr 8.11.4 (live data)

1. Stop `seek workers solr db`. Back up `seek_db`, `seek_solr` and
   `seek_filestore` to `*_bak_mysql80_<date>`, and verify them with `diff -rq`,
   as for the LDH upgrade.
2. **Rehearsal** on copies (throwaway compose project and port, the same
   approach as the `v0.3.6` rehearsal) using the merged compose files:
   - `db` on 8.4 must log the server upgrade from 8.0.46 to 8.4.x and turn
     healthy.
   - `solr` 8.11.4 turns healthy and its `seek` core pings.
   - `seek` and `workers` turn healthy.
   - Run the checks in step 4 against the rehearsal.
3. **Live**: check out the merged submodule commit, then start `db` first
   (watch the upgrade log), then `solr`, `seek`, `workers`. Then run
   `docker compose exec seek bundle exec rake seek:reindex_all`, as upstream's
   `update.sh` does after a Solr change.

### 4. Verification

- **Versions and health:** MySQL `select version()` returns 8.4.x. All SEEK
  services are healthy, and `docker compose ps` shows no `exporter`.
- **Checks in the `seek` container:**
  - Patch check: OIDC provider patched, `SessionsController` patched,
    `KeycloakJwtAuth` loaded, SEEK 1.18.3.
  - `test/keycloak_provisioning_check.rb`: ALL PASSED.
  - `test/keycloak_oidc_check.rb`: ALL PASSED.
- **End-to-end** (same scripts as before):
  - Browser login through Keycloak, driven with curl, ends in callback 302 →
    `/seek/` with `people/current` 200.
  - Bearer JWT: `/seek/people/current` returns 200.
  - `/api/investigations`, `/studies`, `/assays` and `/workflows` return 200,
    with counts matching the pre-upgrade values (4 / 4 / 10 / 10).
  - Search works after reindexing (a `/seek/search?q=…` request returns
    results).
  - No errors in the `seek`, `workers` or `db` logs.

### 5. Finish

Bump the submodule pointer to the merge commit on `abi`. Update the
walkthrough and plan artifacts and the ADR to match what actually happened, run
`gitleaks` on the artifacts, and commit when the user asks.

**Rollback:** restore the `*_bak_mysql80_<date>` volumes and set the submodule
pointer back to `d78fbf8`. MySQL 8.4 data can't be opened by 8.0.
