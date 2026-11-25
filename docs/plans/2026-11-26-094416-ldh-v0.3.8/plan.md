# Update LDH to v0.3.8 (SEEK 1.18.5)

Status: active

Branch: chore/ldh-v0.3.8

## Context

Issue [#397](https://github.com/ABI-CTT-Group/digitaltwins-platform/issues/397): SEEK 1.18.4 fixes a
vulnerability in `programmes_controller.rb` and `projects_controller.rb` (signed-in users could change
which projects belong to a programme). We run the NFDI4Health LDH image, pinned at `v0.3.6`, which
contains SEEK 1.18.3.

NFDI4Health has since released two LDH versions, both on 2026-11-24:

| LDH | SEEK (`config/version.yml` at the tag) |
|---|---|
| `v0.3.7` | 1.18.4 |
| `v0.3.8` | 1.18.5 |

SEEK 1.18.5 changes only the Ruby patch version (3.3.13 to 3.3.14, in `.ruby-version` and the
Dockerfile base image). Between LDH `v0.3.6` and `v0.3.8`, the only application changes are the two
controller fixes and their tests; there are no migrations or schema changes and no Solr changes. The
image `ghcr.io/nfdi4health/ldh:v0.3.8` is published, and its revision label matches the tag commit.

## Steps

1. Set `LDH_RELEASE=v0.3.8` in `.env.template`.
2. Update the version note in `docs/seek-integration.md` to `v0.3.8`, which reports SEEK `1.18.5`.
3. Confirm the image's own `config/version.yml` reports SEEK 1.18.5.
4. Roll out to staging, then demo, following
   [Upgrading LDH](../../seek-integration.md#upgrading-ldh): back up the SEEK volumes, set
   `LDH_RELEASE` in the host's `.env`, pull the image, run `docker/upgrade.sh` (expected to be a
   no-op), restart only `seek` and `workers`, then run both Keycloak checks in
   `services/seek/ldh-deployment/test/` and log in to `/seek` through Keycloak.

## Decisions

- **Target `v0.3.8`, not `v0.3.7`.** `v0.3.8` carries the security fix plus the Ruby patch update, and
  adds no migrations, so it costs nothing extra over `v0.3.7`.
- **Still run `docker/upgrade.sh` during rollout**, although SEEK says 1.18.3 to 1.18.4 needs no
  migrations: it is a no-op when nothing is pending, and it keeps the documented upgrade path the same
  for every bump.
