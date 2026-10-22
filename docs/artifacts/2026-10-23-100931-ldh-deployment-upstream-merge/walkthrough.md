# Walkthrough: merge upstream ldh-deployment `main` into the fork's `abi`

Plan: [implementation_plan.md](implementation_plan.md). ADR:
[2026-10-23-seek-database-mysql-8.4.md](../../decisions/2026-10-23-seek-database-mysql-8.4.md).

## What changed

| Where | Change |
|---|---|
| Fork `ABI-CTT-Group/ldh-deployment`, branch `merge/upstream-main-2026-10` (PR #9 into `abi`) | Merge commit `6edaa23`: upstream's 14 commits, with conflicts resolved per the plan |
| `services/seek/network-override.yml` | `exporter` joins the platform network, pinned to `linux/amd64` (the image is amd64-only). It only matters when the profile is enabled |
| `docs/seek-integration.md` | Solr 8.11.4, MySQL 8.4 with a link to the ADR, the exporter profile, "don't use upstream's `update.sh`", and notes on changing the MySQL or Solr image |
| `docs/decisions/2026-10-23-seek-database-mysql-8.4.md` | Stay on MySQL (8.4, as upstream) rather than move SEEK to Postgres |

## The merge

- Textual conflicts appeared only where predicted: `.env.tpl`, and 6 hunks in
  `docker-compose.yml`. They were resolved per the plan's table.
- **Hidden conflict:** git auto-merged the `db` service *without* conflict
  markers but kept both healthchecks, which made `healthcheck` a duplicate YAML
  key. Upstream's healthcheck was kept and ours dropped. This was caught by
  reading the merged file and confirmed with a YAML load that rejects duplicate
  keys.
- **Checks after resolving:**
  - The file loads as YAML with no duplicate keys.
  - `docker compose config` from the platform root succeeds and lists no
    `exporter`.
  - With `--profile exporter`, the exporter resolves to
    `fmeineke/ldh-exp:latest` on the platform network.
  - `db`, `seek`, `workers` and `solr` have the expected images, healthchecks
    and `depends_on` conditions, and no `links`.
- Upstream `main` is an ancestor of the merge commit.

## Runtime upgrade

1. Stopped `seek`, `workers`, `solr` and `db`. Backed up `seek_db`,
   `seek_filestore` and `seek_solr` to `*_bak_mysql80_20261023`, and verified
   them identical with `diff -r`.
2. **Rehearsal** on copies, in a separate compose project:
   - MySQL logged "Data dictionary upgrade 80023 → 80300 completed" and "Server
     upgrade from 80046 to 80413 completed", then became healthy on 8.4.13.
   - `schema_migrations` still had 603 rows, and both accounts still used
     `caching_sha2_password`.
   - Solr 8.11.4 became healthy and its `seek` core responded to ping.
   - `seek` and `workers` became healthy, and `/seek/` returned 200.
   - The patch and provisioning checks passed, with no log errors.
3. **Live:** started `db` alone (same upgrade log lines), then `solr`, `seek`
   and `workers`. Ran `rake seek:reindex_all`; the reindexing queue drained and
   Solr now holds 180 documents.

## Verification (live)

| Check | Result |
|---|---|
| MySQL version | 8.4.13 |
| Services | All healthy; `exporter` not running |
| Patch check (OIDC provider, `SessionsController`, `KeycloakJwtAuth`, SEEK 1.18.3) | PASS |
| `test/keycloak_provisioning_check.rb` | ALL PASSED |
| `test/keycloak_oidc_check.rb` | ALL PASSED |
| Browser login through Keycloak, driven with curl | Callback 302 → `/seek/`; session `people/current` 200 |
| Bearer JWT `/seek/people/current` | 200 |
| `/api/investigations`, `/studies`, `/assays`, `/workflows` | 200; counts 4 / 4 / 10 / 10, same as before |
| Search (`/seek/search`, bearer) | 200 with results |
| `seek`, `workers`, `db` and `api` logs since the upgrade | No errors |

## Remaining

- Merge PR #9 into `abi` with **"Create a merge commit"**. It needs one approval
  or an admin bypass.
- Bump the platform's submodule pointer to the `abi` tip after the merge.
- Rollback, if ever needed: restore the `*_bak_mysql80_20261023` volumes and
  set the submodule back to `d78fbf8`. MySQL 8.0 can't read 8.4 data.
