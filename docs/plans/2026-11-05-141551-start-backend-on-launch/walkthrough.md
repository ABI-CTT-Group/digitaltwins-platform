# Walkthrough: start GUI tool backends on launch

Plan: [plan.md](plan.md). Tasks: [tasks.md](tasks.md). ADR: [2026-11-05-start-gui-backends-on-launch](../../decisions/2026-11-05-start-gui-backends-on-launch.md).

## Problem

A GUI tool with a backend failed to launch after a platform restart: "Tool backend is not running. Please
start the backend by 'Compose Up' first." When the builder stops, it removes all plugin containers and
marks them down; when it starts, it brings back only those still marked up, which is none. A gui assay's
Launch never checked, so the tool opened with a dead backend.

## What changed

**Builder** (`services/builder/`)
- `POST /api/builder/tools/backend/{expose}/start` and `GET /api/builder/tools/backend/{expose}`, open to any
  signed-in user. The start runs the build's deployment again (`compose up -d`), or deploys the build when
  it has no deployment or the last one failed. States: `none | stopped | starting | deploying | running | failed`.
  Starts in flight are tracked in memory under a lock, so concurrent launches share one start.
  (`start_backend`, `backend_state`, `start_deployment` in `app/utils/workflow_tool_utils.py`.)
- Migration `0002_one_deployment_per_build.sql`: an `error` column, unique indexes on `build_id` and
  `workflow_build_id`, and removal of older duplicate rows (the newest is kept). A redeploy reuses the row.
- A failed deploy's error is now stored. Before, it was written to attributes that had no column.
- Removed: `GET /tools/plugin/{id}/deploy`, `GET /workflow/{id}/deploy`, `GET /tools/check/deploy/{id}/`.
  The admin-only `GET /tools/plugin/deploy/{id}/execute` stays, and its `up` branch uses the shared start helper.

**Portal** (`services/portal/frontend/`)
- `/tool-view` calls `ensureBackend(expose)` before mounting the tool, shows "Starting…" or "Deploying…",
  and shows the deploy error if it fails. Both the Tool Hub and gui assay launches pass through it.
- Tool Hub card: Launch no longer checks the backend; the menu offers only "Stop backend" (was Compose
  down) and View logs. Deploy backend and Compose up are gone.

**Docs**: ADR (supersedes part of ADR 2026-10-02), a glossary entry for "Backend (of a GUI tool)",
`services/portal/docs/plugin-system-architecture.md` §4–5, `services/builder/AGENTS.md`.

## Deviations from the plan

- The plan's state list gained `stopped` (a deployment exists but isn't running and nothing is starting it).
- A failed start marks the deployment failed, so the next launch redeploys it, rather than retrying the start.
- The `tool-plugin-view` spec mocks `http` and uses the real `ensureBackend`, because a mocked
  `ensureBackend` received a stray zero-argument call from the test harness.

## Verification

- `make test`: api 407 passed / 1 skipped, builder 254 / 12 skipped, frontend 186, hub 5, util ok.
- Builder Postgres integration tests against a throwaway Postgres: 12 passed (models and migrations
  agree; duplicate deployments keep the newest).
- `make lint` and `make docs-check`: clean.
- Live, after rebuilding and restarting `builder` and `portal-frontend`, checked through the API:
  migration 0002 applied; a builder restart leaves the backend `stopped`, and a start brings it to `running`;
  an admin stop followed by a start runs it again; an unknown expose gives 404 and no token gives 401.
  The plugin route answered 502 for a few seconds while its app booted, then 200 (the accepted tradeoff
  of no readiness probe).
- In a browser, the user checked Launch on the Tool Hub card and on a gui assay.
