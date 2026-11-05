# Start GUI tool backends on launch

## Context

Launching `Tool_Lesion-Ground-Truth-Curator` (the gui workflow `workflow_Lesion-Ground-Truth-Curator`'s tool)
failed with "Tool backend is not running. Please start the backend by 'Compose Up' first." Its deployment row
is `completed, up=false` and no container is running.

**Root cause:** on a builder restart, `_shutdown_all_plugin_backends` (`services/builder/app/main.py`)
force-removes every plugin container and sets `up=False`. Then `_reconcile_plugin_state` only looks at
`up=True` rows, so nothing comes back. Every platform restart leaves every GUI backend down until an admin
clicks Compose up on each card. A GUI assay's Launch is worse: `services/api/app/routers/dashboard.py` returns
`/tool-view?assay=…` without checking anything, so the tool opens and its `/plugin/<expose>/` calls fail.

Backends are manual, admin-only actions because of [ADR 2026-10-02](docs/decisions/2026-10-02-build-gui-workflow-tools.md),
hence "Deploy backend" and "Compose up/down" in the card's "..." menu.

**Decided in the grilling session:**
- Q1: Launch starts the backend (lazy). Restarts stay as they are, and there's no idle timeout.
- Q2 + Q6: persist the deploy error, and keep one deployment row per build (dedupe the existing rows).
- Q3: any signed-in user's launch may start, or deploy for the first time, the backend of the build that Launch loads.
- Q4: the check runs in `/tool-view`, which both the Tool Hub and assay launches reach with `app.expose`.
- Q5: the menu keeps only "Stop backend" (admin, renamed from Compose down) and View logs. Deploy backend and Compose up go.
- Q7: the backend counts as ready when the start or deploy has finished (`up=True`). There's no HTTP probe.

Consequence to note in the ADR: after an admin stops a backend, the next launch by anyone starts it again.

## Vocabulary (to docs/glossary.md)

- **Deploy (a backend):** build the backend image and create its containers (`compose up --build --force-recreate`). This happens once per build, and takes minutes.
- **Start (a backend):** run the containers of an existing deployment again (`compose up -d`). Takes seconds.
- **Deployment:** the record of one build's backend: one per build, either running or not.

## Plan (TDD: failing tests first in each step)

0. Sync this plan to `docs/artifacts/2026-11-05-<time>-start-backend-on-launch/plan.md`; draft the ADR
   `docs/decisions/2026-11-05-start-gui-backends-on-launch.md` (supersedes ADR 2026-10-02's "backends are admin
   actions" bullet; add a "Superseded in part by" note there). Add glossary entries.
   → verify: `make docs-check`.

1. **Builder: migration `0002`** in `services/builder/app/database/migrations/`: add
   `plugin_deployments.error` (text); delete older duplicate rows per `build_id` / `workflow_build_id`, keeping
   the newest; add unique indexes on `build_id` and on `workflow_build_id`. Mirror the changes in
   `app/models/db_model.py` (`error` column, `unique=True`).
   → tests: `test_db_constraints.py` (a second row for the same build is rejected; the error is stored);
   `test_migration_runner.py` if it lists the migrations.

2. **Builder: one row per build.** Add a get-or-create helper in `app/utils/workflow_tool_utils.py` (next to
   `latest_deployment`) that returns the build's row, resetting `status=pending`, `error=None` and keeping
   `deploy_id`. `run_deployment` already stores `result["error_message"]` in `error`; that now persists.
   `log_registry.open` (`engine/log_stream.py`) already resets a reused job key.

3. **Builder: start endpoints** in `app/router/workflow_tool_plugin.py` (router prefix `/api/builder/tools`,
   any authenticated user):
   - `POST /backend/{expose_name}/start` resolves the completed `PluginBuild` or `WorkflowBuild` with that
     `expose_name`. Its owner has no backend → `{"state": "none"}`. Otherwise, under a per-expose
     `threading.Lock` (the builder runs as a single uvicorn process):
     - the row is completed, `up`, and `deployer.is_project_running()` returns `"running"` → `running`
     - the row is completed but not running → start in a background thread → `starting`
     - there's no row, or it failed → `run_deployment` in the background → `deploying`
     - a start or deploy is already in progress → its current state, without starting another
   - `GET /backend/{expose_name}` returns `{state, error, deploy_id}`, with states
     `none | starting | deploying | running | failed`.
   - Pull the "compose up + nginx conf + reload + up=True" body of `execute_plugin_backend_by_docker` into a helper
     that the `up` branch of that endpoint and the start endpoint both call.
   - Remove `GET /tools/plugin/{id}/deploy` and `GET /workflow/{id}/deploy` (the UI was their only caller; start
     replaces them). Keep `GET /tools/plugin/deploy/{id}/execute` (admin), which Stop uses. Remove
     `GET /tools/check/deploy/{id}/`, which nothing calls any more.
   → tests (new `tests/test_backend_start.py`, fake `PluginDeployer` like `test_workflow_gui_tools.py`
   does): a viewer can start; no backend → none; a stopped completed row → compose_up called once; no row →
   deploy using the served build (the approved one for workflows); a failed row → redeploy, and GET
   returns `failed` + `error`; two concurrent starts → one compose call; a tool and a workflow both resolve.
   Move or replace the deploy tests in `test_workflow_gui_tools.py` and `test_tools_auth.py`.

4. **Portal: `/tool-view` makes sure the backend is running.** New `ensureBackend(expose, onState)` in
   `src/bootstrap/tool_api.ts`: POST start, then poll GET every 2 s until the state is `running`/`none` (resolve)
   or `failed` (reject with the error). In `src/views/tool-plugin/tool-plugin-view.vue`, both paths call it once
   `app` is known and before `<remote-component-app>` mounts. Show "Starting the tool's backend…" or "Deploying
   the tool's backend (the first launch builds it, which can take a few minutes)…", and show the error in the
   existing `v-alert`.
   → tests: a vitest spec for `ensureBackend` (none, running, starting→running, failed), and a
   `tool-plugin-view` spec checking that the tool doesn't mount until the backend is running.

5. **Portal: the Tool Hub card.** `ToolCard.vue`: `onLaunch` keeps only the Script/Notebook warning; the menu
   loses Deploy backend and Compose up, and Compose down becomes "Stop backend" (both kinds; admin only, as now).
   `ToolsOverallView.vue`: remove `handleDeploy` and the `deploy`/`compose-up` wiring. In `tool_api.ts`, remove
   `useDeployTool`, `useDeployWorkflowTool` and `useGetDockerComposeStatus`.
   → tests: update `views/upload-dataset/components/__tests__/cards.spec.ts` (menu items, and Launch emits without
   any backend check).

6. **Docs:** finish the ADR with what actually happened; update `services/builder/README.md` and
   `services/portal/docs/plugin-system-architecture.md` wherever they describe Deploy / Compose up; sync the
   artifacts and the walkthrough.

Commits (atomic, Conventional): `fix(builder): persist deploy errors, one deployment per build` (1–2),
`feat(builder): start a gui backend on launch` (3), `feat(portal): start the backend from /tool-view`
(4–5), `docs: …` (0, 6, plus the artifacts). Only once you ask for them.

## Verification

- `make test-builder`, `make test-frontend`, `make lint`, `make docs-check` (no tests in live containers).
- Live: rebuild and restart only `builder` and `portal-frontend`
  (`docker compose build builder portal-frontend && docker compose up -d builder portal-frontend`). The
  migration runs on builder start. Then:
  1. Tool Hub → Launch the Lesion Curator: the "Starting…" spinner appears, then the tool loads; `docker ps` shows
     `workflowlesiongroundtruthcurator_212b4d69-app-1`.
  2. Restart `builder`, then Launch the matching GUI assay from the dashboard: it starts again and opens.
  3. Admin "Stop backend", then Launch: it starts again.
  4. `plugin_deployments` holds one row per build.
