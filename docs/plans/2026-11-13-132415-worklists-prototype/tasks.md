# Tasks: Worklists prototype

- [x] Branch `feat/worklists-prototype` from `origin/main`, in a worktree
- [x] Plan folder with `plan.md` and `tasks.md`
- [x] Red: `worklist.spec.ts` (counts, filter, batch capping, advancing, batch finished)
- [x] Green: `model/worklist.ts`
- [x] Red: `worklistStore.spec.ts` (seeded once from the fixture, a decision survives a reload)
- [x] Green: `worklistStore.ts` and `fixtures/example-cases.json`
- [x] Red: `WorklistsView.spec.ts` (tab counts, Start 10, Confirm advances, a correction needs a note)
- [x] Green: `WorklistsView.vue`, `CaseTable.vue`, `CaseReviewPanel.vue`
- [x] Router: `/worklists`, with `/clinician-dashboard` redirecting to it; the home card; the `Default.vue` title
- [x] Docs: glossary, codemap, portal README
- [x] Sync plans to docs/plans/
- [x] `make test-frontend`, `make lint`, `make docs-check`
- [x] Rebuild and restart `portal-frontend`, then check with screenshots
- [x] `walkthrough.md`, then sync plans to docs/plans/
