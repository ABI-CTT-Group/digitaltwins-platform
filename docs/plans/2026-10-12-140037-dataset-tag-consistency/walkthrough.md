# Walkthrough: consistent card tags across the dataset hubs

Plan: `plan.md` in this folder. ADR: `docs/decisions/2026-10-12-card-tag-vocabulary.md`.

## What changed

All paths are under `services/portal/frontend/src/`.

| File | Change |
|---|---|
| `views/upload-dataset/components/cardTags.ts` (new) | `measurementRegistrationTag`, `handoffRegistrationTag`, `buildTag`, `typeTag`: the one source of tag labels, colours and tooltips |
| `views/upload-dataset/measurements/components/MeasurementCard.vue` | One Registration chip (with tooltip) replaces the status, "in platform" and "stage ·" chips |
| `views/upload-dataset/models/components/ModelCard.vue` | Same; the `FHIR` chip and the inline failure text are removed |
| `views/upload-dataset/components/ToolCard.vue` | Order: Registration, `build ·`, `deploy ·`, type (new), `from workflow`, version, author, date. The approving, approval-failed, "platform upload" and "in platform" chips are folded into Registration |
| `views/upload-dataset/components/WorkflowCard.vue` | Registration, `build ·`, type, version, author, date |
| `views/upload-dataset/models/ModelsOverallView.vue` | "Registration status" filter, copied from Measurements |
| `bootstrap/tool_api.ts` | `usePlatformTools(known)` → `withPlatformTools(tools)`: attaches `fhirStatus` / `fhirFailureMessage` to portal tools and appends platform-only ones, from the one existing `/datasets` call. The build enrich step keeps `handoffError` |
| `bootstrap/platform_api.ts`, `bootstrap/workflow_api.ts` | Same for workflows (`withPlatformWorkflows`) |
| `models/types.ts` | `handoffError`, `fhirStatus` and `fhirFailureMessage` added to `ToolResponse` and `WorkflowResponse` |
| `views/upload-dataset/workflow-tool/ToolsOverallView.vue` | Comment only (it referred to the removed "platform upload" badge) |

### Where implementation differs from the plan

- `buildTag` takes `{ status, platformOnly }`, not just the status, so that "no build chip for platform-only items" lives in the helper.
- The platform list helpers were renamed (`with…` instead of `use…`), because they now return the merged list rather than only the platform-only rows.
- The `PLATFORM_WORKFLOW` test fixture now has `version: ""`, as real platform-only workflows do. It used to inherit `"1"` from the portal fixture.

## Verification

| Check | Result |
|---|---|
| Vitest (`docker run --rm -v $PWD/services/portal/frontend:/fe -w /fe node:20 npx vitest run`) | 121 passed (24 files), up from 94 |
| New and changed tests | `cardTags.spec.ts` (12), `cards.spec.ts` (+8, 3 updated), `tool_hub.spec.ts` (+3), `workflow_hub.spec.ts` (+1, 2 updated), `platform_api.spec.ts` (+1, 1 updated), `registration_filter.spec.ts` (+1, 1 updated) |
| vue-tsc 2.2.10 + TypeScript 5.9.3, in a throwaway container on a copy | 13 errors, all in untouched code or the known `RegistryView` slot-typing error (`ModelsOverallView`, `MeasurementsOverallView`, `WorkflowsOverallView`). `ToolsOverallView.vue:10` is an untouched line |
| Rebuild `portal-frontend` (`docker compose up -d --build --no-deps portal-frontend`) | Healthy. The served bundle contains `upload paused` and no longer contains `platform upload` |

## Not verified

- I did not click through the four hubs in a browser. The browser checks listed in `plan.md` (chip order, amber `in platform` on a FHIR failure, tooltips, the Models filter) are covered by vitest component tests, not checked by eye.
