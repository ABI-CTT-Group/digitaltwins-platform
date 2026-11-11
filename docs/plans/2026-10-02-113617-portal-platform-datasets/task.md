# Tasks: platform workflows and tools in the portal

Plan: [plan.md](plan.md) (approved 2026-10-02, option B)

- [x] Investigate the hubs (workflows missing, tools read-only, measurements OK)
- [x] Write the plan; sync artifacts to docs/artifacts/
- [x] 0. API `GET /datasets/{uuid}/workflow-tools` (pytest first; suite: 314 passed, legacy failures unchanged)
- [x] 1. Frontend vitest setup (yarn 1.22.22, bundled in node:20; `@vue/test-utils` pinned to 2.4.6 for Node 20)
- [x] 2. `platform_api.ts`, spec first (6)
- [x] 3. `useWorkflowHub`, spec first (2)
- [x] 4. `DeletePlatformDatasetDialog.vue`, spec first (7)
- [x] 5. Platform-only menus on `WorkflowCard` and `ToolCard`, specs first (4)
- [x] 6. Wire both hubs to the dialog
- [x] 7. Verify: `yarn test` 20/20; vue-tsc 0 new errors (12 pre-existing); `yarn build` OK; clean `--frozen-lockfile` install OK; API suite OK
- [x] 8. Walkthrough; sync artifacts to docs/artifacts/; gitleaks: no leaks
- [x] Live check: the user rebuilt both and deleted `workflow_image_conversion` and its tools from the portal; verified gone from every service (see walkthrough)
- [ ] Commit (only when asked)
