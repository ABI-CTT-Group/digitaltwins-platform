# Plan: make `make lint` pass (ruff, eslint, vue-tsc)

## Context

`make lint` fails on `main`. The failures were already there before PR #370 and were not introduced by it. CI runs lint report-only, so the errors pile up unnoticed. Step 1 is done: ruff's safe automatic fixes cut ruff from 135 to 77 findings, are staged on `dev_chinchien`, and `make test-api` and `make test-builder` pass. This plan covers the rest:
- 77 ruff findings in `services/api` and `services/builder`;
- 33 eslint problems (11 errors, 22 warnings) in `services/portal/frontend`;
- 14 vue-tsc errors in `services/portal/frontend`.

The goal is `make lint` exiting 0 with **no behaviour change**. The one deliberate exception is the duplicate route-handler name.

Your interview decisions:
- **E402:** move imports where safe; use `noqa` only for the real circular import.
- **`tool_bucket`:** move the fixture to `conftest.py`.
- **Dead files:** keep `DownloadSheet.vue`, `SubmitSheet.vue` and `package-lock.json`, fix them in place, and list them in `docs/future_refactoring.md`.

## Ground rules

- Work on `dev_chinchien`; it is currently level with `main`. Make one atomic Conventional Commit per step, and commit only when you say so.
- **Red/green:** the failing `make lint-python` / `make lint-frontend` output is the red test. Each step must also keep its suite green: `make test-api`, `make test-builder`, `make test-frontend`.
- Use exact-text edits only, never line-number `sed`.
- **Step 0 (on approval):** copy this plan to `docs/artifacts/2026-10-28-<HHMMSS>-lint-cleanup/implementation-plan.md`, and re-sync it after any change.
- No ADR: none of these choices is a significant design decision.

## Step 1: ruff safe fixes (done; staged)

Commit: `chore(lint): apply ruff safe fixes in api and builder`.

## Step 2: duplicate route-handler name (builder)

- **File:** [workflow_tool_plugin.py:572](services/builder/app/router/workflow_tool_plugin.py#L572).
- **Change:** rename the second `get_plugin_builds` (`GET /plugin/build/{build_id}/deploys`) to `get_build_deploys`.
- **Effect:** both routes already work, because FastAPI registers them at decoration time; only the module name is shadowed. Nothing references either name: the frontend calls hand-written URLs in `src/bootstrap/tool_api.ts`. The only visible effect is a new default operationId in `/openapi.json`.
- **Commit:** `fix(builder): give the build-deploys route its own handler name`.

## Step 3: E402 import order (api)

| Cause | Files | Fix |
|---|---|---|
| `load_dotenv()` or `urllib3.disable_warnings()` before imports | `src/digitaltwins/core/{deleter,downloader,querier,querier_factory,uploader,uploader_gen3,workflow}.py`, `gen3/querier.py:13`, `minio/uploader.py`, `airflow/workflow.py` | Move the imports above the call. No imported module reads env vars at import time. |
| Circular import | `gen3/querier.py:414` (`core/dataset.py` imports `Querier`) | Keep it in place with `# noqa: E402` and a one-line reason |
| Class-level monkeypatch of `Request.form` | `app/main.py:20-30` | Move the patch block below the imports, keeping lines 20-30 in their current order. The routers read env vars at import, which relies on `digitaltwins` (and its `load_dotenv`) loading first. |
| Redundant `sys.path` guard in tests | `tests/test_assay_gui_launch.py`, `test_assay_notebook_launch.py`, `test_notebook_staging.py` | Delete the block; `pyproject.toml` already sets `pythonpath = ["src", "."]` |
| Notebook | `tutorials/tutorial_5_uploading_datasets.ipynb`, first code cell | Move `import digitaltwins as dts` above `config_file = ...` |

Then run `make test-api`. Commit: `style(api): move imports to the top of each module (E402)`.

## Step 4: the remaining ruff findings (api + builder)

- **F841, unused locals:**
  - Delete the dead `.get()` and f-string assignments in `build_tool.py:543-550`, `build_workflow.py:150-155,164`, `workflow_router.py:233` (`build_ts`), `airflow/workflow.py:63,67`, `postgres/uploader.py:77` and `uploader_gen3.py:94`. Rewrite the last one as `if not dataset_dir.is_dir(): raise ...`.
  - **Exception: `build_tool.py:609`.** Keep the `json.loads(...)` call, because it rejects a malformed `config.portal.json`, and drop only the assignment.
- **E722:** change `metadata_convertor.py:178,378` to `except Exception:`. It keeps the current behaviour; the narrower exceptions are noted for later.
- **E731:** turn the lambdas into nested `def`s in `assays.py:414,506` and `jupyterhub/staging.py:116-120`. For `undo_link`, use `def undo_link(): pass`.
- **E741:** rename `l` to `link` in `fhir_service.py:218` and `purge_legacy_measurements.py:60`.
- **E701:** split `if not row: continue` in `core/uploader.py:111` over two lines.
- **F401:** add `__all__` with the 6 public names to `src/digitaltwins/__init__.py`. They are re-exports used by the routers, examples, tutorials and the README.
- **F811 `tool_bucket`:** move the fixture from `tests/test_datasets_workflows_api.py:88` into `tests/conftest.py`. Then delete the 5 `from test_datasets_workflows_api import tool_bucket` imports and the 2 existing `# noqa: F811` comments.

Then run `make test-api test-builder` and `make lint-python`, which should be 0. Commit: `chore(lint): fix the remaining ruff findings in api and builder`.

## Step 5: eslint (frontend)

- **Errors:**
  - Remove the 4 leading `;` in `src/bootstrap/index.ts:29-32`.
  - Add `:key` by name on the `v-for` loops: `AssayContent.vue:23,56` (`data.input.name` / `data.output.name`) and `BaseAnnotateStep.vue:84,102,143,151` (`input.name` / `output.name`). The names are unique CWL keys.
  - In `tools-viewer.vue:32`, change the slot to `<template #dialog-description>`.
- **Warnings:**
  - Delete the unused imports and dead variables listed by eslint. Keep `defineProps(...)` and the awaited calls; drop only the unused binding.
  - Add `argsIgnorePattern: '^_'` and `ignoreRestSiblings: true` to `@typescript-eslint/no-unused-vars` in `.eslintrc.js`. This covers `_value`, and `_src`, which is a deliberate destructure that strips `source` from the payload.

Then run `make test-frontend` (specs exist for AssayContent, BaseAnnotateStep and BaseInformationStep). Commit: `chore(frontend): fix eslint errors and warnings`.

## Step 6: vue-tsc (frontend)

All of these are type-only, and none changes runtime behaviour:
- `RegistryView.vue:30,87`: change `as { value: T[] }` to `as Ref<T[]>`. This also clears the 6 errors in Measurements/Models/WorkflowsOverallView.
- `AssayContent.vue:240`: `.find(...)` used as a loop becomes `inputs?.forEach(...)`.
- `DownloadSheet.vue` / `SubmitSheet.vue`: use `defineModel<boolean>(...)` and drop the `!`.
- `LocalFolderDropzone.vue:401`: `typeof import('jszip')`.
- `ToolsOverallView.vue:10`: `.includes(t.handoffStatus ?? '')`.
- `UploadToolForm.vue:94`: type the parameter as `ToolInformationStep`.
- `vite.config.ts:36`: `glslify({...}) as PluginOption`. Vite bundles its own rollup 4.53, while the hoisted rollup 4.61 comes from workbox. The cast avoids a lockfile change.
- *(Added during implementation.)* Once the cast was in, vue-tsc showed an error it had been hiding: the `test` key in `vite.config.ts`. vitest 3.2.7 adds that key to its own nested vite 7.3.6, while this file imports vite 6.4.1. The fix is a `@ts-expect-error` with the reason, and it becomes a type error itself once the versions are aligned.

Then run `make test-frontend` and `make lint-frontend`, which should be 0. Commit: `fix(frontend): resolve vue-tsc type errors`.

## Step 7: docs + artifacts

- `docs/future_refactoring.md`:
  - the unused `DownloadSheet.vue` and `SubmitSheet.vue`;
  - the stale `package-lock.json`;
  - narrowing the two `except Exception` handlers;
  - `uploader_gen3.py` importing names that `digitaltwins` no longer exports;
  - examples that import names that aren't exported;
  - the never-rejecting promise in `upload-dataset/components/utils.ts:117`.
- Write `walkthrough.md` in the artifact folder, then commit it with the plan: `docs: lint cleanup plan and walkthrough`.

## Verification

1. `make lint` exits 0 (ruff, eslint and vue-tsc all clean).
2. `make test` passes, with the same pass and skip counts as before (API 391/1 skipped, builder 221/11 skipped, plus the frontend, jupyterhub and util suites).
3. `make docs-check` passes, and `make gitleaks` is clean.
4. Rebuild the touched images on a host that runs them:
   ```
   docker compose build api builder portal-frontend
   docker compose up -d --no-deps api builder portal-frontend
   ```
   Smoke check:
   - the portal loads;
   - the tool catalogue and a tool's builds/deploys list render;
   - the upload-dataset registry pages list items.

   No containers run on this machine now, so if none are up at the end, I'll give you these commands.

## Step 8: make lint a required check (added on request, same PR)

- `.github/workflows/ci.yml`: rename the job `lint (report-only)` → `lint`, drop `continue-on-error`, and run the frontend step with `if: ${{ !cancelled() }}` so both steps report.
- `services/portal/frontend/package.json`: `lint:check` gets `--max-warnings 0`, because eslint exits 0 on warnings by default and they would pile up again.
- Remove "report-only" for lint from `AGENTS.md`, `CONTRIBUTING.md`, the `Makefile` comment, `docs/testing.md` (add `lint` to the required list; there are now six) and the PR template.
- Add ADR `docs/decisions/2026-10-28-lint-required-check.md`, and a pointer to it in the 2026-10-16 CI ADR, which said lint is report-only.
- Ruleset "CI required checks": add `lint` **after** this PR merges. Open PRs that still run the old workflow never report a `lint` check, so they would be blocked. This is a repo-settings change and needs your go-ahead.
- Verify with `make docs-check` and a YAML parse of `ci.yml`; the PR's own CI run shows the renamed `lint` job failing or passing for real.
