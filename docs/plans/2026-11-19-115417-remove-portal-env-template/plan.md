# Remove the stale env template in services/portal/

Resolves `docs/future_refactoring.md` → "Repository layout" → item 6.

## Context

`services/portal/.env.template` is headed "the builder", but the builder moved to `services/builder/` (e932c1d7).
The platform renders only the root `.env` (`util/gen-env.sh`; `docs/codemap.md`, "How the compose files fit
together"), so nothing reads the file. It sets `KEYCLOAK_VERIFY_SSL=false` and `KEYCLOAK_CLIENT_ID=api`, which
contradict the root `.env.template` and the builder's compose defaults.

Review finding: the portal's old standalone stack, if you run `services/portal/docker-compose.yml` on its own,
reads `services/portal/.env`. It uses `PROJECT_NAME` (no default), `MINIO_SERVER_ACCESS_KEY`,
`MINIO_SERVER_SECRET_KEY` and `MINIO_BROWSER_REDIRECT_URL` (both have defaults). The `minio` service's comment points
at this template. That stack is itself listed for removal (Repository layout item 1).

**Decision (user):** remove the template rather than trim it or move it to `services/builder/`. This keeps one env
template, at the root.

No ADR: this removes an unused file and follows the existing rule of one `.env`, at the root.

## Steps

1. `git rm services/portal/.env.template`.
   → `git grep -n "portal/.env.template"` finds only `docs/plans/` and the debt item.
2. In `services/portal/docker-compose.yml`, the `minio` comment "Filled from .env (see .env.template)" drops the
   reference to the removed template.
3. In `services/portal/README.md` → Gotchas, the standalone-stack bullet says the stack has no env template and
   needs `PROJECT_NAME` passed when running it, since it has no `.env` of its own.
4. In `docs/future_refactoring.md`, remove Repository layout item 6.
   → `make docs-check` passes; `docker compose config -q` (read-only) passes.
5. Sync the plan and tasks. Commit only when asked.
