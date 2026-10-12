# Brief: consistent card tags across the dataset hubs

Status: **not started**. This brief hands the task to a new session. Start by interviewing the user and writing a plan for approval; do not implement before that (see `~/.claude/CLAUDE.md` planning rules and `AGENTS.md`).

## Problem

The four portal hubs (Measurements, Models, Tools, Workflows) tag their dataset cards with different words for the same states. Some state is shown in one hub and hidden in the others. Users comparing hubs cannot tell whether, for example, "completed" on a tool means the same as "registered" on a model. It does not: on a tool it means the build finished.

## Current tags

All card files are under `services/portal/frontend/src/views/upload-dataset/`. Tags are `aurora-chip` spans in each card's `#meta` slot.

### Status tag (one per card)

| Hub | Card | Values | Source of the value |
|---|---|---|---|
| Measurements | `measurements/components/MeasurementCard.vue` | uploading source…, pending, uploading…, submit failed, completed, FHIR failed | Session status or dataset `fhir_status`, mapped by `SESSION_STATUS` / `FHIR_STATUS` in `src/bootstrap/measurement_api.ts` |
| Models | `models/components/ModelCard.vue` | uploading source…, awaiting approval, registering…, registration failed, registered, FHIR failed | Same mapping as measurements, different labels |
| Tools | `components/ToolCard.vue` | pending, building, completed, failed (raw) | Portal build status |
| Workflows | `components/WorkflowCard.vue` | pending, building, completed, failed (raw) | Portal build status |

Models and measurements share one lifecycle, but the labels differ. The model labels were introduced in the model registration work (commit `f2543dd6`).

### Other tags

| Tag | Measurements | Models | Tools | Workflows |
|---|---|---|---|---|
| in platform (committed dataset) | yes | yes | yes, if not a `sparc-tool-` placeholder | yes, if not a `sparc-workflow-` placeholder |
| platform upload (REST/CLI upload; replaces "in platform") | no | no | yes | yes |
| FHIR (has FHIR details) | no | yes | no | no |
| stage · upload / fhir_push (failed step) | yes | no; failure text shown instead | no | no |
| approving… / approval failed (handoff) | in status | in status | separate tags | separate tags |
| version, author | no | no | yes | yes |
| deploy · status, workflow (tool of a gui workflow) | no | no | yes | no |
| workflow type | no | no | no | yes |
| date | yes | yes | yes | yes |

- **Tool and workflow FHIR state** is visible only inside `components/ToolApprovalDialog.vue`, not on the card.
- **Handoff states** (`HandoffStatus` in `src/models/types.ts`): uploading, awaiting_reauth, committing, completed, failed.

## Why they differ

- **Tools and workflows** are built in the portal backend first, then handed off to digitaltwins-api on approval. Their status tag tracks the build.
- **Measurements and models** upload straight to digitaltwins-api in chunked sessions. Their status tag tracks upload, approval and FHIR.

## Idea raised so far (not agreed)

Three independent dimensions, each with one vocabulary used by every hub:

1. **Registration:** draft, awaiting approval, registering, registration failed, in platform. Tools and workflows derive it from the approval handoff; measurements and models from the session.
2. **FHIR:** none, publishing, published, FHIR failed. Shown on every card.
3. **Build** (tools and workflows only): e.g. "build · completed", so it cannot be read as registration.

The cheapest first step is to align the model and measurement labels.

## Open questions for the interview

- Scope: only align model and measurement labels, or the shared vocabulary for all four hubs?
- Which wording wins ("completed" vs "registered", "pending" vs "awaiting approval")?
- Should REST/CLI uploads be flagged ("platform upload") everywhere, or nowhere?
- Should tool and workflow cards show FHIR state, which means reading the dataset's `fhir_status` for approved items?
- Keep the measurement "stage ·" tag, or show the failure message like the model card?
- Should the hub list filters (e.g. measurements "Registration status") follow the same vocabulary?

## Starting points

- **Card tests:** `components/__tests__/cards.spec.ts` (Tool and Workflow cards). Measurement and model cards have no card tests yet.
- **Running tests:** vitest in a `node:20` container from `services/portal/frontend`. See the walkthrough in `docs/artifacts/2026-10-12-131907-model-dataset-registration/` for the exact commands and the vue-tsc version note.
- **Rebuilding:** frontend changes need a rebuild of `portal-frontend` (`docker compose up -d --build --no-deps portal-frontend`).
