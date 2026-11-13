# Walkthrough: sandbox real launch

The Test Project example in the study design sandbox now runs its assays on the platform. Each of its four
assays is linked to the platform's Test Project assay it mirrors, and Launch, Submit, Monitor, Verify and
Download call the same API endpoints as the study dashboard, with the platform assay's saved configuration.
Uploaded projects still simulate. All changes are in `services/portal/frontend`, plus the glossary.

## What changed

- `views/isa-project/platformRun.ts` (new): the link map (example id → sandbox assay id → SEEK assay id),
  and `launchPlatformAssay` / `submitPlatformAssay`, which report whether the call worked. They call the
  bootstrap API functions directly because `useAssayActions` doesn't report success, and shared code
  stays unchanged.
- `SandboxAssayCard.vue`: a linked card shows "Platform assay N", which opens the platform assay report in a
  new tab. Monitor, Verify and Download are passed to the study instead of being refused by the card. A
  linked card shows the request in flight, and says "Submitted" rather than "Submitted (simulated)".
- `StudyGraph.vue`: passes each card its platform link and forwards the new events.
- `StudyDesign.vue`: a linked assay launches and submits on the platform. Its sandbox status changes only
  when the call works, the readiness rules still apply, and an assay that has run can launch again.
  Monitor, Verify and Download use `useAssayActions`. The study note and the legend say the actions are
  real.
- `docs/glossary.md`: the "ISA project (prototype)" row mentions the links.

## Verification

- `make test-frontend`: 494 tests pass, including new specs for `platformRun`, the card, the graph and
  `StudyDesign` (linked and simulated paths).
- `make lint-frontend` and `make docs-check` are clean.
- Rebuilt and restarted `portal-frontend`. In headless Firefox, signed in as an admin:
  - the notebook assay staged its workspace and opened JupyterHub;
  - the script assay triggered its Airflow DAG and enabled Monitor;
  - the GUI assay opened `/tool-view` with its input image loaded in VolView.
- Submit wasn't run live. It needs a finished run's outputs. Unit tests cover it.

## Known behaviour

- Platform assays keep reading the datasets they were configured with. A real Submit creates new datasets,
  which later platform assays don't pick up.
- "Simulate next run" and Reset change only the sandbox's statuses. Real runs and datasets stay on the
  platform.
