# SEEK stays on MySQL, upgraded to 8.4

- **Date:** 2026-10-23
- **Status:** Accepted

## Context

Every other platform service that needs a relational database (Keycloak,
HAPI-FHIR, the API and builder) uses the shared `postgres:16` service,
`database`. SEEK alone runs its own `mysql:8.0` container, because that is what
upstream's LDH deployment kit (`nfdi4health/ldh-deployment`) ships.

Upstream has since moved to `mysql:8.4`, and we are merging upstream `main` into
our fork's `abi` branch. That raised the question of whether to follow upstream
to MySQL 8.4 or move SEEK onto the platform's Postgres.

SEEK supports Postgres: the LDH image ships the `pg` gem and
`docker/database.docker.postgres.yml`. Our SEEK database holds 603 migrations of
schema plus live data. All its accounts use `caching_sha2_password`, which
MySQL 8.4 still supports.

## Alternatives Considered

### Option A: Stay on MySQL, upgrade to 8.4

- Pros:
  - Matches upstream's tested setup, so future merges of `ldh-deployment` stay
    simple.
  - MySQL 8.0.46 upgrades directly to 8.4 in place.
  - No change to SEEK's configuration.
- Cons:
  - Keeps a second database engine in the platform, with its own backups and
    image.
  - The data upgrade is one-way; only a backup can undo it.

### Option B: Move SEEK to the platform's Postgres

- Pros:
  - One database engine for the whole platform.
  - Shared backups and monitoring.
- Cons:
  - Needs a MySQL → Postgres conversion of the schema and data (e.g. pgloader),
    and checks that SEEK behaves the same on Postgres.
  - Diverges from upstream LDH, which only tests MySQL, so every future merge
    conflicts on the database service.
  - Much larger than the security-driven merge this decision is part of.

### Option C: Stay on MySQL 8.0

- Pros: no data change now.
- Cons:
  - Diverges from upstream on the database image.
  - 8.0 is past its end of life (April 2026).

## Decision

**Option A.** Follow upstream to `mysql:8.4`, with the live data upgrade backed
up and rehearsed on a copy first. Moving SEEK to Postgres remains possible later
as its own project, with its own ADR.

## Consequences

- The platform keeps two database engines. SEEK's MySQL needs its own backup and
  restore (the `seek_db` volume), separate from Postgres.
- Rolling back past this upgrade needs the pre-upgrade volume backup, because
  8.0 can't open 8.4 data.
- Future `ldh-deployment` merges keep the `db` service close to upstream.
