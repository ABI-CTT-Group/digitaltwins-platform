# Study design sandbox: really launch the Test Project example's assays

## Context

The sandbox study `/study-dashboard?trail=isa-sandbox,isa-sandbox:p-test-project,isa-sandbox:p-test-project:i-test,isa-sandbox:p-test-project:i-test:s-test`
simulates Launch and Submit (`StudyDesign.vue` `launch`/`submit` → `simulateLaunch`/`simulateSubmit`), and
Monitor, Verify and Download only print "isn't part of the prototype". Stakeholders want to see the
notebook, script and GUI assays actually run from the sandbox.

Every real launch path is keyed on a SEEK assay id and runs the config saved in Postgres
(`GET /api/dashboard/assay-launch`, `dashboard.py:296`). No endpoint launches from a workflow id plus
inputs. The example already mirrors the real Test Project (SEEK study 11), whose assays exist and are
configured:

| Sandbox assay | Platform assay | Type | Real launch does |
|---|---|---|---|
| `a-cohort` Test Assay 1: cohort selection | 41 (workflow 97, cohort {2}) | notebook | stages `assay_41/` into your JupyterHub server, opens it |
| `a-convert` Test Assay 2: image conversion | 42 (workflow 116, cohort {1}) | script | triggers Airflow DAG runs, enables Monitor |
| `a-visualise` Test Assay 3: image visualisation | 43 (workflow 95, cohort {1}) | gui | opens `/tool-view?assay=43` (VolView) |
| `a-breast-app` Test Assay 4: breast app | 45 (workflow 156, cohort {1}) | gui | opens `/tool-view?assay=45` (lesion curator) |

So the sandbox can drive those platform assays with no API change.

## Decisions (grilling, 2026-11-13)

| # | Decision |
|---|---|
| L1 | **Real side effects allowed:** Launch really runs, and **Submit is real too** (it uploads the workspace as new datasets). The user changed this from "Submit stays simulated". |
| L2 | **Scope:** only the Test Project example. Uploaded and other projects keep the simulated actions. |
| L3 | **Config:** Launch runs the platform assay's own saved config, not the sandbox's edits. The UI says so and links to the platform assay. Nothing writes assay config. |
| L4 | **Link:** a prototype-only map in code (example id + assay id → SEEK assay id). The ISA project JSON format and downloaded bundles don't change. |
| L5 | **Gating kept** (I read "open 1" as option 1): an assay launches only when the sandbox shows it ready, so the walkthrough stays 1 → submit → 2 → … |
| L6 | **Follow-ups real:** Monitor (script → Airflow DAG page), Verify (notebook → JupyterHub workspace), Download (workspace zip). |

My defaults, flagged for review:
- **Platform inputs are pinned.** A real Submit creates new datasets with new ids (`upload_workspace_datasets`, `assays.py:886`). Platform assay 42 still reads the `test_curated_dataset` it was configured with, not what assay 41 just submitted. The sandbox's "reads the latest submitted run" is the design proposal, not what the platform does. The study note says this in one line.
- **Relaunch:** a linked assay that has run or been submitted can launch again (an assay runs many times). Its sandbox status doesn't change.
- **Status follows real outcomes:** the card turns "ran" only when the launch call succeeds, and "submitted" only when the real submit succeeds. A failed Submit (for example a GUI assay whose tool wrote no workspace returns 404) leaves it at "ran" and shows the API error.
- **"Simulate next run" and Reset stay simulated** (the user confirmed this after the build). Reset clears the sandbox's statuses only; real runs and datasets stay on the platform.
- **Shared code untouched**: `useAssayActions.launch`/`submit` don't report success, so the sandbox calls the same bootstrap API functions itself and mirrors their toasts. It reuses `useAssayActions().monitor/verify/download` and the dashboard cache store's `setAssayExecute` unchanged, so a Monitor URL from the sandbox also shows on the real dashboard card for that assay.
- Status text for submitted linked assays drops "(simulated)".
- No ADR: the prototype is throwaway and nothing is hard to reverse.

## Design (frontend-design pass)

Inside the Aurora theme, no new palette. One restrained cue, so a viewer can tell real from
simulated at a glance: on each linked card's meta row, after the type tag, a quiet link "Platform
assay 41" (`mdi-link-variant`, `--text-dim`, underline on hover) that opens the platform assay report
(`LaunchedAssayOverview?assayId=41`) in a new tab. Unlinked cards look exactly as now.

The study note under the toolbar changes for a linked study, from "nothing runs" to:
"Launch, Submit and Download run the linked platform assays with their platform configuration.
Changes you make here stay in this browser, and later platform assays keep reading the datasets
they were configured with." Legend label "Submitted (simulated)" becomes "Submitted" for a linked
study.

## Implementation

1. **`views/isa-project/platformRun.ts`** (new): `PLATFORM_ASSAYS` map
   `{ "example-test-project": { "a-cohort": "41", "a-convert": "42", "a-visualise": "43", "a-breast-app": "45" } }`
   (keyed by the entry's `exampleId`, as in `adapter/isaProjectSource.ts:27`), `platformAssayId(entry, assayId)`,
   and `launchPlatformAssay(seekId): Promise<boolean>` / `submitPlatformAssay(seekId): Promise<boolean>`
   that call `useDashboardGetAssayLaunch` / `useDashboardSubmitAssayResults` (`bootstrap/dashboard_api.ts`),
   set Monitor via `useDashboardCacheStore().setAssayExecute`, open notebook/GUI URLs, and toast like
   `useAssayActions.ts:98-126` / `:164-175`.
2. **`components/SandboxAssayCard.vue`:** optional props `platformAssayId`, `canMonitor`, `launching`,
   `downloading`, `submitting`; render the "Platform assay N" link; emit `monitor`/`verify`/`download`
   instead of `unavailable(...)` (the parent decides), pass the flags to `AssayActionBar`.
3. **`components/StudyGraph.vue`:** pass the same per-assay platform props into the node card and forward
   the new events.
4. **`StudyDesign.vue`:** look up the entry and its links; `launch`/`submit` call the real functions for a
   linked assay (gating unchanged, relaunch allowed), then update `sim` only on success; route Monitor,
   Verify, Download to `useAssayActions()` when linked, else keep the "isn't part of the prototype"
   message; linked-study note and legend text.
5. **Glossary** (`docs/glossary.md`, "ISA project (prototype)" row): add that the example's assays are
   linked to the Test Project's platform assays, so their Launch, Submit, Monitor, Verify and Download
   are real and use the platform configuration.
6. **Plan folder** `docs/plans/2026-11-13-145013-isa-sandbox-real-launch/` with `plan.md` (this plan)
   and `tasks.md`, synced after every edit; walkthrough at the end. No local run details (assay ids
   created, run ids) in committed docs.

## Tests first (Red → Green)

- `__tests__/platformRun.spec.ts`: map lookup (linked example → id; uploaded project or other example →
  none); launch with an `airflow` response sets Monitor and resolves true; `notebook`/`gui` open a tab;
  `null`, `{message}` or a thrown error resolve false and toast; submit success/failure.
- `__tests__/SandboxAssayCard.spec.ts`: link renders only with `platformAssayId`; Monitor/Verify/Download
  emit their own events; `canMonitor` enables Monitor for scripts.
- `__tests__/StudyDesign.spec.ts`: Test Project example → Launch calls the API with the platform id and marks
  ran only on success; Submit calls the real submit and marks submitted only on success; blocked assay
  doesn't call the API; an uploaded project still simulates and makes no API call; linked note text.
- `__tests__/StudyGraph.spec.ts`: platform props reach the node cards.

## Verification

1. `make test-frontend` and `make lint` (compare lint with `main`).
2. Rebuild and restart only the portal: `docker compose up -d --build portal-frontend`.
3. In the browser at the sandbox URL (signed in as admin): Assay 1 Launch opens JupyterHub `assay_41`,
   Verify reopens it; Submit uploads; Assay 2 becomes ready → Launch shows the toast, Monitor opens the
   Airflow DAG page; Download gives a zip; Assays 3 and 4 open `/tool-view?assay=43|45` with data.
   An uploaded project's Launch still only simulates. Screenshot via headless Firefox.
4. No commits until asked.
