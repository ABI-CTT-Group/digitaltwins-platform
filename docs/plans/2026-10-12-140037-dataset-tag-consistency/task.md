# Task: consistent card tags across the dataset hubs

Plan: `plan.md` in this folder (approved 2026-10-12).

- [x] Sync approved plan to docs/artifacts/
- [x] Red: `cardTags.spec.ts` (registration, build, type derivations)
- [x] Green: `components/cardTags.ts`
- [x] Red: card tests (`cards.spec.ts`: Tool, Workflow, Measurement, Model)
- [x] Green: rewrite `#meta` slots of the four cards
- [x] Red: hub data tests (`tool_hub.spec.ts`: fhirStatus + handoffError on tools and workflows)
- [x] Green: `tool_api.ts`, `workflow_api.ts`, `platform_api.ts`, `types.ts`
- [x] Red: Models hub registration filter (`registration_filter.spec.ts`)
- [x] Green: `ModelsOverallView.vue` filter
- [x] Full vitest run + vue-tsc on touched files
- [x] Rebuild and restart `portal-frontend`
- [x] ADR `docs/decisions/2026-10-12-card-tag-vocabulary.md`
- [x] Walkthrough `walkthrough.md`
- [x] Sync artifacts to docs/artifacts/ + gitleaks scan
