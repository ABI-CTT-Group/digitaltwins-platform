# Walkthrough: resolving the Dependabot alerts

Plan: [plan.md](plan.md). There's one PR per batch, done in order of risk. This file gets a section as each batch lands.

Baseline on 2026-11-03: 284 open alerts (2 critical, 137 high, 119 medium, 26 low).

## PR 1: delete the stale npm lockfile

**Change**
- Deleted `services/portal/frontend/package-lock.json`. The portal image (`Dockerfile`: `COPY package.json yarn.lock`,
  `yarn install --frozen-lockfile`), `make test-frontend`/`make lint` and CI install from `yarn.lock` only. Nothing
  in the repo read the npm lockfile.
- `docs/future_refactoring.md` item 1: removed the lockfile part. The unused `DownloadSheet.vue` and `SubmitSheet.vue`
  are still listed.

**Alerts closed:** all 86 alerts whose manifest is `services/portal/frontend/package-lock.json`. The same packages
still have alerts against `yarn.lock`, and later batches handle those.

**Verification**
- Red: the file was present, and `git grep package-lock` found only the refactoring note.
- `make test-frontend`: 33 files and 162 tests passed.
- `make lint`, `make docs-check`: pass.
- `docker compose build portal-frontend`: builds. The image content that matters doesn't change, because the build
  never copied the npm lockfile into the install step.
