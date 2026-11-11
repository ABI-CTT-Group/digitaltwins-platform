# Plan: GUI tool launch context (standard per-launch config for GUI tools)

## Context

Launching a gui assay whose workflow's tool is the Lesion-Ground-Truth-Curator (annotator) opens the tool,
which then fails with "File not found in MinIO: volunteer/subjects.xlsx". It ignores everything
the platform passes and boots from its bundled `tool_config.json`, whose dataset `volunteer` doesn't exist.
VolView works only because it reads its own `?urls=` query, which the portal sets for it.

Today the portal provides an undocumented `assayContext` through Vue inject. No tool reads it. It carries
input files as proxy URLs only: no cohort, and no bucket or key that a backend could use. The only way to
point a tool at an assay's data is a per-tab manual override or a rebuild.

**Goal:** one documented, versioned **launch context** that the platform hands every GUI tool when it opens
from an assay. A tool reads it once in code (a one-time change), falls back to its bundled defaults when it
is absent, and never needs a rebuild per assay. A guide and an example JSON give authors the template.

## Decisions (settled with the user)

| Decision | Choice |
|---|---|
| Mechanism | One standard object that every tool reads (not per-tool templates that the portal renders) |
| Scope | GUI tools only; script and notebook launches unchanged |
| Name | **Launch context** (added to the glossary) |
| Channel | Vue `inject('launchContext')` only; rename `assayContext` (it has no consumers). VolView's `?urls=` query stays as its adapter |
| Contents | Minimal: `schemaVersion`, `assayId`, `cohort` (subject IDs), `inputs[]`, plus `getAccessToken()` |
| File addressing | Both: `url` (API proxy, for browser code) and `bucket` + `key` (for trusted backends holding platform MinIO credentials) |
| Tool Hub launch | No launch context (unchanged); the tool uses its bundled defaults |
| Template | `launch-context.example.json` plus the TS type as the single source of truth; a test keeps them in step. No JSON Schema |
| Guide | New `docs/gui-tool-authoring.md` |
| Annotator | Worked mapping example in the guide only; its code change is a separate PR in its own repo |
| Branch | All work on a new branch `feat/gui-launch-context`, cut from `main` |

### Launch context shape (camelCase, as the portal already delivers it)

```json
{
  "schemaVersion": 1,
  "assayId": "12",
  "cohort": ["sub-1"],
  "inputs": [{
    "name": "contrast_pre_nrrd",
    "datasetUuid": "<dataset uuid>",
    "bucket": "measurements",
    "sampleType": "contrast_pre_nrrd",
    "files": [{
      "name": "contrast_pre_nrrd.nrrd", "subjectId": "sub-1", "sampleId": "sam-1",
      "key": "<dataset uuid>/primary/sub-1/sam-1/contrast_pre_nrrd.nrrd",
      "url": "/api/dashboard/assays/12/input-files/measurements/<dataset uuid>/primary/..."
    }]
  }]
}
```
`getAccessToken()` is added at runtime; it is not part of the JSON. `cohort` holds the resolved subject IDs
(`sub-1`), not the stored indices (`{1}`). With the bucket and `datasetUuid`, a trusted backend reaches the
dataset's SDS metadata at `<bucket>/<datasetUuid>/subjects.xlsx` etc., which is what the annotator needs.

## Steps (TDD: failing test first in each)

0. **Branch and plan folder.** `git switch main && git pull && git switch -c feat/gui-launch-context`.
   Create `docs/plans/<YYYY-MM-DD-HHMMSS>-gui-launch-context/` with `plan.md` (this plan) and `tasks.md`
   (checklist, ticked during implementation). Sync after every plan edit.
   → verify: branch exists; plan folder holds both files.

1. **API: cohort and bucket in gui-inputs.** In `get_assay_gui_inputs`
   (`services/api/app/routers/assays.py:689`), add `cohort` (the unique `subject_id`s of the samples
   `_discover_samples` returns, in dataset order: a plain sort would put `sub-10` before `sub-2`) and a per-input `bucket` (`downloader.find_bucket`, already called and cached
   there, so it's no extra work). Files already carry `bucket` and `key`.
   Test first in `services/api/tests/test_assay_gui_launch.py`.
   → verify: `make test-api PYTEST_ARGS="-k gui"`.

1a. **API: each GUI input keeps its own samples** (added during implementation). `_discover_samples` gains
   `per_input=False`; `get_assay_gui_inputs` passes `True`, so the dedup key includes the input name.
   Script runs are unchanged. Test first: two inputs from different datasets that both have `sub-1/sam-1`.
   → verify: `make test-api PYTEST_ARGS="-k gui"`.

2. **API: pass them through assay-gui-context.** In `get_assay_gui_context`
   (`services/api/app/routers/dashboard.py:319`), add `schema_version: 1`, `cohort`, and per input `bucket`;
   keep `key` alongside `url` on each file. `tool` stays in the response for the portal's own use.
   Test first in `services/api/tests/test_dashboard_api.py`.
   → verify: `make test-api PYTEST_ARGS="-k gui_context"`.

3. **Portal: type, builder and provide.**
   - `services/portal/frontend/src/models/types.ts:56-74`: add `bucket`/`key` to `AssayGuiFile`/`AssayGuiInput`
     and `schemaVersion`/`cohort` to `AssayGuiContext`; add `LaunchContext`, the public contract (no `tool`).
   - New pure `src/utils/launchContext.ts`: `toLaunchContext(ctx, getAccessToken): LaunchContext`.
   - `src/views/tool-plugin/tool-plugin-view.vue:84`: use `toLaunchContext`.
     `src/components/RemoteComponentApp.vue:44`: `provide('launchContext', …)` instead of `'assayContext'`;
     update the comments.
   - New `src/models/launch-context.example.json` (the template: one measurement input, placeholder UUIDs).
   - Tests first: `src/utils/__tests__/launchContext.spec.ts` (mapping drops `tool`; the example has exactly
     the keys `toLaunchContext` produces, and is typed `LaunchContext` so vue-tsc checks it), and a case in
     `src/views/tool-plugin/__tests__/tool-plugin-view.spec.ts` that the context reaches `remote-component-app`.
     The existing `volviewParams.spec.ts` must still pass.
   → verify: `make test-frontend`, `make lint`.

4. **Docs.**
   - New `docs/gui-tool-authoring.md`:
     - the plugin contract (UMD, `VITE_PLUGIN_ROUTE_PREFIX`, backend compose, with the env vars the builder
       actually passes: `MINIO_SERVER_*`, `PLUGIN_ROUTE_PREFIX`);
     - the launch context: fields table, link to the example, `inject('launchContext', null)` with fallback;
     - data access: `url` + `getAccessToken()` in the browser (the cookie lasts 5 minutes); `bucket`/`key` in
       a backend, approved tools only;
     - the annotator worked example: mapping to its `tool_config` (inputs grouped by `datasetUuid`, names as
       sample types, `cohort` to `cohorts`, `bucket` to `system.minio.base_url`), with the caveat that it
       routes by input name;
     - known limits: no user identity yet, no Tool Hub context, no result submission.
   - `docs/README.md`: index the guide. `docs/glossary.md`: add **Launch context**.
   - `docs/request-flows.md` (~line 419) and `services/portal/docs/plugin-system-architecture.md` §5 and §7:
     link the guide, and fix the wrong `MINIO_ACCESS_KEY` "from the parent .env" line (194).
   - ADR `docs/decisions/2026-11-12-gui-tool-launch-context.md`: standard object vs per-tool template
     rendering, and URL vs bucket/key. It amends the "Generic contract" section of
     `2026-10-05-gui-assay-launch-input-handoff.md`; add a one-line pointer there.
   → verify: `git add` new files, then `make docs-check`.

5. **Rebuild and restart** the changed services by name (never a blanket `up -d`):
   `docker compose up -d --build api portal-frontend` (confirm the exact service names in
   `docker-compose.yml` first). Check a gui assay launch by hand; report it in the chat, not here.

6. **Wrap-up.** `make test`, `make lint` (compare with `main`), `make gitleaks`. Re-check the ADR against what
   was built. Tick `tasks.md` and sync the plan folder. Commit only when asked, as atomic Conventional
   Commits (feat(api), fix(api) for step 1a, feat(portal), docs), with the plan folder and ADR in the same PR.

## Verification

- `make test-api PYTEST_ARGS="-k gui"`: gui-inputs returns `cohort` and per-input `bucket`; assay-gui-context
  returns `schema_version`, `cohort`, `bucket`, and `key` plus `url` on each file.
- `make test-frontend`: `toLaunchContext` maps the response and drops `tool`; the example JSON matches it;
  `/tool-view` passes the launch context to the plugin; the VolView query is unchanged.
- `make lint` (vue-tsc type-checks the example against `LaunchContext`), `make docs-check`.
- The annotator still uses its bundled config until its own PR reads the launch context; the guide says so.

## Known risks and limits (stated in the guide and ADR)

- `_discover_samples` dedups `(subject, sample)` across inputs, ignoring the dataset. SDS ids restart in every
  dataset, so an input from a second dataset could lose its `sub-1/sam-1`. Found during the live check and
  fixed for GUI launches during implementation (step 1a); script runs keep the old behaviour.
- Backend direct MinIO access keeps platform-wide read; removing those credentials is a later decision.
- No user identity in the context (minimal by choice); the annotator keeps its own `user_info`.
