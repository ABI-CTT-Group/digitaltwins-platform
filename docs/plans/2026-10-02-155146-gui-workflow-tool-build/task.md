# Tasks: launchable GUI tools from gui workflows

Spec: [spec.md](spec.md). ADR (accepted): [2026-10-02-build-gui-workflow-tools](../../decisions/2026-10-02-build-gui-workflow-tools.md).

- [x] Find out why `tool_volview` can't be launched (it was created from `workflow_volview`; the bundle was never built)
- [x] Map the current GUI tool lifecycle: registration, build, deploy, approval and launch
- [x] Brainstorm the design with the user (decisions 1-7 in the spec)
- [x] Write the spec and the ADR draft
- [x] Sync the artifacts to `docs/artifacts/`
- [x] User reviews the spec and the ADR (approved 2026-10-02; ADR Accepted, decision 3 of the SDS workflow ADR marked superseded)
- [x] Write the implementation plan (writing-plans), as `plan.md` in this folder (13 tasks; it records 5 changes from the spec)
- [x] Sync the artifacts to `docs/artifacts/`
- [x] User approves the plan and chooses how it will be carried out (2026-10-02: subagent-driven; no commits until the user asks)
- [x] Task 1: the API carries `primary/<tool_stem>/` into the tool dataset
- [x] Task 2: portal schema
- [x] Task 3: workflow GUI fields at registration
- [x] Task 4: `PluginBuilder.build_frontend`
- [x] Task 5: a gui SDS workflow build builds its tool frontend
- [x] Task 6: approval records the tool dataset
- [x] Task 7: launcher metadata and build-log fallback
- [x] Task 8: `GET /api/workflow/gui-tools`
- [x] Task 9: workflow tool backend deploy, plus cleanup on rebuild and delete
- [x] Task 10: Tool Hub merges the workflow tools
- [x] Task 11: ToolCard and Tool Hub handlers
- [x] Task 12: the wizard's GUI fields for gui SDS workflows
- [x] Task 13 (Steps 1, 2, 4): docs, all suites, walkthrough; E2E pending the user's go-ahead
- [x] Sync the artifacts to `docs/artifacts/`
