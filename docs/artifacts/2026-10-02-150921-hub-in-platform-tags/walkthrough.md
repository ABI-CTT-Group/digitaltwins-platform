# Walkthrough: "in platform" tags in the Workflow Hub and Measurements

The request was to tag workflows and measurements that have been approved into the platform, the same way the Tool Hub (`/upload-tool-dataset`) does, and to make sure the "Registration status" filter matches the tags.

## What changed (`services/portal/frontend`)

| File | Change |
|---|---|
| `src/views/upload-dataset/components/WorkflowCard.vue` | New green **in platform** chip for a workflow with a real platform uuid. The legacy approval's `sparc-workflow-` placeholder doesn't count. Platform uploads keep their **platform upload** chip instead, as `ToolCard` does. |
| `src/views/upload-dataset/measurements/components/MeasurementCard.vue` | New green **in platform** chip for any committed platform dataset (it has a `uuid`). It sits next to the status chip, so for example "FHIR failed" still shows. |
| `src/views/upload-dataset/measurements/MeasurementsOverallView.vue` | The "In platform" filter now means "committed dataset" (`!!m.uuid`). Before, it meant `status === 'completed'`. |
| `src/views/upload-dataset/components/__tests__/cards.spec.ts` | Tests for the WorkflowCard chip. |
| `src/views/upload-dataset/components/__tests__/registration_filter.spec.ts` (new) | Tests that mount both hubs and run each filter option, plus the MeasurementCard chip. |

## Decision: what "in platform" means for a measurement

The user chose **committed dataset**: any measurement that is a platform dataset (Postgres + MinIO) is in the platform, whatever its FHIR state. This matches the Tool Hub's uuid rule.

Before, the filter counted only `completed`. A dataset whose FHIR push had failed or was still running was listed under "Not in platform", even though it was already stored. Uploads that aren't committed yet (`pending_upload`, `pending`, `uploading`, `submit_failed`) are still "not in platform".

No measurement chip says "platform upload". Every measurement is listed from the platform API, so nothing tells a portal approval apart from a REST upload.

## Workflow Hub filter

The filter was already correct: platform uploads, or a real uuid that isn't the `sparc-workflow-` placeholder. The SDS handoff sets `workflow.uuid` only after the commit succeeds (`workflow_handoff._complete`), so the chip can't show early. The new test confirms how the filter splits the workflows.

## Verification

- **`npx vitest run`:** 50 passed in 13 files (+4 tests).
- **`vite build`** in `node:20-alpine`, the build image: succeeds. On the host (Node 18) it fails with `crypto is not defined` with or without this change.
- **Live check:** not done. It needs a rebuild of `portal-frontend`.
