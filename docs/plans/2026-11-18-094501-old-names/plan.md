# Plan: Old names in code and comments (future_refactoring.md, Repository layout #3)

Branch `refactor/old-names`; plan folder `docs/plans/2026-11-18-094501-old-names/` (`plan.md`, `tasks.md`).

## Part 1: done (uncommitted, staged)

Removed the dead `preprocessor` DAG trigger: `airflow/workflow.py:run()`, `core/workflow.py` (the
`digitaltwins.Workflow` export), `services/api/examples/run_workflow.py`, `AIRFLOW_VERSION`. Kept
`get_api_token()` (workflow deploy uses it). Reworded three old-name comments, updated `codemap.md`,
ticked the item in `future_refactoring.md`. New `services/api/tests/test_airflow_workflow.py`.
`make test`, `make lint`, `make docs-check` pass; `api` image rebuilt (no local stack running).

## Part 2: follow-ups the user asked for (2026-11-18)

### Context
Part 1 left two things: the Airflow client still requires `AIRFLOW_API_URL` (and reads
`AIRFLOW_API_TOKEN`) but uses neither; and `services/portal/docs/` still says `clinical-dashboard`.
User decisions: remove both env vars; update the portal deployment guide to today's layout (not delete).

Findings:
- `AIRFLOW_API_URL` is read only by `airflow/workflow.py`'s required-config check. Deploy builds its
  URLs from `AIRFLOW_ENDPOINT` (`workflows/deploy.py:wait_for_dag`), as does `assays.py:_trigger_dag`.
  Referenced in: `services/api/docker-compose.yml:35`, `docs/codemap.md:456`,
  `services/airflow/README.md:55`, `services/api/README.md:289`. Not in `.env.template`.
- `AIRFLOW_API_TOKEN` is read into `_airflow_api_token`, never used, set nowhere.
- The standalone portal stack still exists (`services/portal/docker-compose.yml` + `.override.yml`,
  root compose `extends` only the base file), so the guide's content holds; only the
  `clinical-dashboard` paths, the `DigitalTWINS-Portal` submodule text and the "Historical" banner are stale.

### Steps
8. **Red**: in `test_airflow_workflow.py`, `test_get_api_token_posts_credentials` also `delenv`s
   `AIRFLOW_API_URL` (instead of setting it). → verify: fails with "Airflow configuration is incomplete".
9. **Green**: `airflow/workflow.py` drops `_airflow_api_url` (and from the required list) and
   `_airflow_api_token`. Drop `AIRFLOW_API_URL` from `services/api/docker-compose.yml`. Docs:
   - `docs/codemap.md:456`: remove the `AIRFLOW_API_URL (...)` clause.
   - `services/airflow/README.md:55`: "(`AIRFLOW_ENDPOINT`, `AIRFLOW_API_URL`)" → "(`AIRFLOW_ENDPOINT`)".
   - `services/api/README.md:289`: "`AIRFLOW_ENDPOINT` / `AIRFLOW_API_URL`" → "`AIRFLOW_ENDPOINT`".
   → verify: `make test-api` passes.
10. **Portal guide** `services/portal/docs/deployment-guide.md`:
   - Title "Clinical Dashboard — Deployment Guide" → "Portal — Deployment Guide (Portal Frontend Nginx)".
   - Replace the "Historical" banner, Audience, Date/Status lines with a short note: covers
     `portal-frontend`'s nginx and the standalone dev stack in `services/portal/`; full platform deploys
     follow `docs/deployment.md`.
   - `cd ../clinical-dashboard` / `cd clinical-dashboard` / `clinical-dashboard/` tree → `services/portal`
     (the switch example becomes: `docker compose down` at the repo root, then `cd services/portal`).
   - `digitaltwins-platform/services/nginx` → `services/nginx` (relative links where they're links).
   - §6: "builds this repo as a git submodule" → "extends `services/portal/docker-compose.yml`"; drop the
     "Never edit `services/portal/DigitalTWINS-Portal/`" submodule paragraph.
   - `services/portal/README.md:153`: "a historical deployment guide" → "a deployment guide for
     portal-frontend's nginx".
   - Also the same "digitaltwins-platform/services/nginx" wording in `services/portal/docker-compose.override.yml`
     comment → `services/nginx`.
11. **Release notes** `services/portal/docs/release-notes.md:40`: `clinical-dashboard/frontend/` →
   `services/portal/frontend/` (other dated entries, e.g. `portal-backend`, stay as history).
12. **`future_refactoring.md`**: drop the "Left over: AIRFLOW_API_URL" sentence from the Resolved line;
   add that the portal guide was brought up to date.
13. **Verify**: `make test`, `make lint`, `make docs-check` (after `git add`);
   `grep -rni "clinical.dashboard\|AIRFLOW_API_URL\|AIRFLOW_API_TOKEN\|DigitalTWINS-Portal"` outside
   `docs/plans/` returns only the refactoring-doc description. Rebuild `api` image
   (`docker compose build api`); offline import smoke as before. No local stack is running, so not started.
14. Sync `plan.md` + `tasks.md` after each step. Ask before committing. Proposed commits:
   (a) `refactor(api): remove dead preprocessor workflow trigger` (part 1 code, test, env, codemap),
   (b) `refactor(api): drop unused AIRFLOW_API_URL and AIRFLOW_API_TOKEN`,
   (c) `docs: drop pre-merge names from comments and the portal guide`,
   (d) `docs: resolve old-names item in future_refactoring` with the plan folder.

No ADR: removals of confirmed-unused code/config and doc updates.

## Notes
- The package version (`2.0a4`) is not bumped; the Airflow image pins `2.0a3`, so DAGs are unaffected.
- Deployed hosts' `.env` may still set `AIRFLOW_VERSION` / `AIRFLOW_API_URL`; harmless, nothing reads them.
