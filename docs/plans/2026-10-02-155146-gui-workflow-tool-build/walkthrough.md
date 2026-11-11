# Walkthrough: launchable GUI tools from gui workflows

- **Date:** 2026-10-02
- **Spec:** [spec.md](spec.md) (see "Changes during planning and implementation")
- **Plan:** [plan.md](plan.md), **Tasks:** [task.md](task.md)
- **ADR:** [2026-10-02-build-gui-workflow-tools](../../decisions/2026-10-02-build-gui-workflow-tools.md) (Accepted)
- **Status:** implemented in the working tree, not committed. End-to-end check pending the user's go-ahead.

Paths below are relative to this folder, so `../../../` is the repo root.

## 1. What changed, per task

| Task | Change | Main files |
|---|---|---|
| 1 | digitaltwins-api copies `primary/<tool_stem>/` into the tool dataset's `primary/` (all upload paths). README documents the folder. | [pipeline.py](../../../services/api/src/digitaltwins/workflows/pipeline.py), [README.md](../../../services/api/README.md), [test_workflow_assemble_tool.py](../../../services/api/tests/test_workflow_assemble_tool.py) |
| 2 | Portal schema: `workflows` GUI columns; `workflow_builds.tool_name`, `bundle_path`, `tool_dataset_uuid`; `plugin_deployments.workflow_build_id` with nullable `plugin_id`/`build_id` and check constraint `ck_plugin_deployments_one_build`. Startup migration. | [database.py](../../../services/portal/backend/app/database/database.py), [db_model.py](../../../services/portal/backend/app/models/db_model.py), [test_db_constraints.py](../../../services/portal/backend/tests/test_db_constraints.py) |
| 3 | Workflow create validates and stores the GUI fields (same rules as tools; other types drop them). | [db_model.py](../../../services/portal/backend/app/models/db_model.py), [test_workflow_create.py](../../../services/portal/backend/tests/test_workflow_create.py) |
| 4 | `PluginBuilder.build_frontend`: the GUI build steps shared by tool and workflow builds. | [build_tool.py](../../../services/portal/backend/app/builder/build_tool.py) |
| 5 | A gui SDS workflow build builds its tool frontend in a scratch copy, writes the bundle to `primary/<tool_stem>/`, uploads it to `tool-builds/<expose>/primary/`, records `tool_name` and `bundle_path`. | [build_workflow.py](../../../services/portal/backend/app/builder/build_workflow.py), [builder_utils.py](../../../services/portal/backend/app/utils/builder_utils.py), [test_workflow_build_dataset.py](../../../services/portal/backend/tests/test_workflow_build_dataset.py), [test_workflow_build_executor.py](../../../services/portal/backend/tests/test_workflow_build_executor.py) |
| 6 | Approval stores the tool dataset uuid (`tool_dataset_uuid`); a failing lookup does not fail the approval. | [workflow_handoff.py](../../../services/portal/backend/app/services/workflow_handoff.py), [test_workflow_handoff.py](../../../services/portal/backend/tests/test_workflow_handoff.py), [test_tool_handoff.py](../../../services/portal/backend/tests/test_tool_handoff.py) |
| 7 | `/api/tools/metadata` lists gui workflow bundles (approved: `/tools/<uuid>/...`; otherwise `/tool-builds/<expose>/...`); build-log endpoint falls back to workflow builds. | [workflow_tool_plugin.py](../../../services/portal/backend/app/router/workflow_tool_plugin.py), [workflow_tool_utils.py](../../../services/portal/backend/app/utils/workflow_tool_utils.py) |
| 8 | `GET /api/workflow/gui-tools` returns Tool Hub rows. | [workflow_router.py](../../../services/portal/backend/app/router/workflow_router.py) |
| 9 | Workflow tool backend deploy (`GET /api/workflow/{id}/deploy`, admin); Compose actions work on workflow deployment rows; rebuild and delete shut down deployments and remove `tool-builds` prefixes. | [workflow_router.py](../../../services/portal/backend/app/router/workflow_router.py), [workflow_tool_plugin.py](../../../services/portal/backend/app/router/workflow_tool_plugin.py) |
| 10 | Tool Hub merges workflow tool rows, de-duplicating platform rows by `tool_dataset_uuid`. | [tool_api.ts](../../../services/portal/frontend/src/bootstrap/tool_api.ts), [types.ts](../../../services/portal/frontend/src/models/types.ts) |
| 11 | ToolCard: "from workflow `<name>`" tag and reduced menu; deploy handler dispatches by `kind`. | [ToolCard.vue](../../../services/portal/frontend/src/views/upload-dataset/components/ToolCard.vue), [ToolsOverallView.vue](../../../services/portal/frontend/src/views/upload-dataset/workflow-tool/ToolsOverallView.vue) |
| 12 | Wizard shows the GUI fields for gui SDS workflows only, and sends them. Review fix: `inspect_workflow_source` lists `code/` subfolders for SDS workflows. | [BaseInformationStep.vue](../../../services/portal/frontend/src/views/upload-dataset/components/BaseInformationStep.vue), [workflow_layout.py](../../../services/portal/backend/app/builder/workflow_layout.py), [test_workflow_layout.py](../../../services/portal/backend/tests/test_workflow_layout.py) |
| 13 | Spec, ADR, task list and this walkthrough updated. | [spec.md](spec.md), ADR, [task.md](task.md) |

Per-task reports and review diffs are kept in `.superpowers/sdd/plan-2026-10-02-155146-gui-workflow-tool-build/` (local working files).

## 2. Test evidence

Run on 2026-10-02 against the final working tree (Task 13, Step 2).

| Suite | Command (from) | Result |
|---|---|---|
| Portal backend (isolated container, no DB env) | `docker run --rm --network none -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-portal-backend -c '/app/.venv/bin/python -m unittest discover -s tests -t .'` (`services/portal/backend`) | `Ran 202 tests in 11.960s` / `OK (skipped=9)` (baseline 152) |
| Portal frontend | `npx vitest run` (`services/portal/frontend`) | `Test Files  14 passed (14)` / `Tests  57 passed (57)` (baseline 50) |
| Frontend build (Node 20, scratch copy) | `yarn install --frozen-lockfile && yarn build` in `node:20-alpine`, on an rsync copy excluding `node_modules` and `build` | Build passed (`Done in 12.88s`, service worker generated) |
| API workflow tests | `PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/test_workflow_assemble_tool.py tests/test_workflow_validation.py` (`services/api`) | `24 passed in 0.06s` (baseline 22 for validation alone) |
| API workflow tests, all four modules (digitaltwins-api image, pytest and httpx added in the throwaway container) | `docker run --rm -v $PWD:/src -w /src --entrypoint sh digitaltwins-platform-digitaltwins-api -c 'pip install -q pytest httpx >/dev/null 2>&1; PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_datasets_workflows_api.py tests/test_dataset_uploads_workflows_api.py tests/test_workflow_assemble_tool.py tests/test_workflow_validation.py'` (`services/api`) | `24 passed, 28 skipped, 1 warning`. The 28 skips are the integration tests, which need live Postgres/MinIO and will run in the E2E or an integration environment. The warning is starlette's anyio `BlockingPortal` DeprecationWarning, from a dependency. |

Other verification:
- **Postgres migration** (controller, throwaway `postgres:16` on an isolated docker network; credentials not recorded here, `<REDACTED>`): old-schema `init_db`, then the new `init_db` twice. Result: `plugin_id` and `build_id` nullable, a single `workflow_build_id` FK, `ck_plugin_deployments_one_build` present, second run a no-op, an existing tool deployment row still inserts, a row with no build is rejected, `workflows.has_backend` defaults to false.
- **Type check:** `vue-tsc --noEmit` crashes at HEAD on any Node version (`Search string not found: /supportedTSExtensions/`, vue-tsc ^1.2 against TypeScript 5.x), so the plan's "no new `error TS`" gate could not be applied. Ruling: `vite build` plus vitest replace it. `yarn build` is `vite build` only.
- **Secret scan:** see section 6.

## 3. Deviations from the plan and spec

Recorded in the spec's "Changes during planning and implementation":
1. No `gui_frontend.py`; the shared build is `PluginBuilder.build_frontend`.
2. gui workflows that aren't SDS packages are unchanged (the spec's "fails its build" was dropped).
3. No workflow update endpoint; pre-existing gui SDS workflows build with defaults on Rebuild.
4. `workflow_builds.tool_name` marks a bundle; a failed `tool-builds` upload leaves `bundle_path` null without failing the build.
5. Build-log endpoint falls back to workflow builds.
6. `inspect_workflow_source` lists `code/` subfolders for SDS workflows (found in Task 12 review).
7. Task 4 moved `_update_plugin_version` after the npm build, so a failed tool build no longer updates `Plugin.version`.

The ADR's Consequences now state that only gui SDS workflows build a frontend.

## 4. End-to-end check: pending, needs the user's go-ahead

Not run, because it rebuilds and restarts the live services. No containers were touched. Checklist (plan Task 13, Step 3):
1. `docker compose up -d --build portal-backend portal-frontend digitaltwins-api`, from the directory with the compose file, project name `digitaltwins-platform`.
2. Migration check: in portal-backend, a read-only query lists `workflow_build_id`, nullable `plugin_id` and `build_id` in `portal.plugin_deployments`, and `ck_plugin_deployments_one_build`.
3. Workflow Hub: **Rebuild** `workflow_volview`; watch the npm output in the log console. (Risk: a failure in VolView's own `build:plugin`, for example itk-wasm assets, is VolView packaging, not this feature; report it with the log.)
4. Tool Hub: a `tool_volview` card tagged "from workflow workflow_volview" with Launch enabled; the old "platform upload" card stays until re-approval.
5. Launch: VolView mounts and the browser loads `/tool-builds/<expose>/primary/my-app.umd.js`.
6. **Submit to approval**, wait for completion; `curl -s -o /dev/null -w "%{http_code}" http://localhost/tools/<tool uuid>/primary/my-app.umd.js` prints `200`; one `tool_volview` card remains and Launch loads from `/tools/<tool uuid>/...`.
7. gui workflow WITH a backend: **Deploy backend**, then **Compose up**; **Launch** reaches `/plugin/<expose>/` (acceptance criterion 3).

Outcome: not yet recorded.

## Final review fixes

- F1: listing `status` is the served build's status; `latest_build_*` still follow the newest build.
- F2: a served build with no bundle location counts as no served build (not listed).
- F3: gui-tools query ordered by `Workflow.created_at`.
- F4: `delete_plugin` shuts backends down off the event loop (`asyncio.to_thread`).
- F5: corrected the rebuild shutdown comment in `_trigger_workflow_build`.
- F6: with a backend, `frontend_folder`/`backend_folder` must be single folder names inside `code/`.
- F7: `unittest.main()` guard moved to the end of `test_workflow_build_dataset.py`.

Full portal backend suite after the fixes: `Ran 202 tests in 11.960s` / `OK (skipped=9)`.

## 5. Follow-ups (out of scope)

From the spec:
- A local-source tool build modifies the canonical staging dir in place (how `volview_983ba79e` reached `tests/data/tool_volview/code/vite.config.ts`).
- A tool rebuild after approval tears down deployments, and deploy targets only the latest build, so the approved bundle's baked-in backend route can no longer be redeployed.
- `backend_deploy_command` is stored but never run.
- Build and deploy error paths assign `error` and `error_message`, which are not columns, so `error_messages` is never filled.
- `plugin_metadata` and `toolMetadata` don't match, so plugin metadata is dropped.
- `/test-build` calls a non-existent `builder.build_plugin`.
- The legacy workflow approval uuid contains a literal `$`.
- Each workflow annotation save inserts a new row instead of updating.
- Workflow test builds live in the platform `workflows` bucket rather than a separate builds bucket.

Added during implementation:
- `vue-tsc` / TypeScript version mismatch breaks the frontend type check.
- Existing deployment rows keep `up=True` after a rebuild shutdown (same as tools).
- The API's workflow integration tests (28) need a live Postgres/MinIO run.

## 6. Secret check

No secrets are present in this folder; the throwaway database password is not recorded (`<REDACTED>` where referenced).
