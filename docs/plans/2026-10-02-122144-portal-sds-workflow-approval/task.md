# Tasks: upload and approve SDS workflow packages from the portal

Plan: [plan.md](plan.md). ADR: [2026-10-02-portal-sds-workflow-approval](../../decisions/2026-10-02-portal-sds-workflow-approval.md). Walkthrough: [walkthrough.md](walkthrough.md).

User decisions on 2026-10-02:
- Option B ("the tool way").
- SDS only; root `.cwl` unchanged.
- Per-step port FHIR annotation.
- Workflow type in the Registration step.
- Local and Git sources.
- Workflow router authentication consistent with tools and measurements.
- Subagent-driven execution.

- [x] Find the root cause: `allowSds` is off for workflows (`BaseInformationStep.vue:296`), and later stages assume a root `.cwl`
- [x] Write the plan and the ADR draft
- [x] Sync the artifacts to `docs/artifacts/`
- [x] Get the user's approval of the plan and the ADR
- [x] Task 1: backend `workflow_layout.py`
- [x] Task 3: model columns and SDS pass-through build. This comes before Task 2, and also covers Task 2 Steps 0 and 1.
- [x] Task 3b: sign-in on the whole `/api/workflow` router and `WRITER` on writes
- [x] Task 2: upload-source, `/cwl` and probe use the layout
- [x] Task 4: `tool_handoff` refactor, `workflow_handoff`, approval, status and delete endpoints. One fix round made the platform DELETE async-safe.
- [x] Task 5: frontend SDS-workflow detection
- [x] Task 6: workflow type in the Registration step
- [x] Task 7: Annotation step for SDS workflows
- [x] Task 8: approval dialog `kind`, `WorkflowCard` and the Workflow Hub
- [x] Final whole-branch review. One fix wave: delete failure feedback, the probe's package.json metadata, `run` basename matching, and the Submit guard.
- [x] Task 9 Steps 1–2: backend 141 OK (9 skipped); frontend 36/36; `yarn build` OK; no new vue-tsc errors
- [x] Write the walkthrough; set the ADR to Accepted
- [x] Sync the artifacts to `docs/artifacts/`; run gitleaks
- [ ] Task 9 Step 3: live end-to-end check (the user rebuilds `portal-backend` and `portal-frontend`)
- [ ] Commit (only when asked)
