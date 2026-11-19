# Resolve future_refactoring item "A promise that never rejects"

## Context

`docs/future_refactoring.md` (Portal section, item 5) says `getRepoRootCWLContent` in
`services/portal/frontend/src/views/upload-dataset/components/utils.ts` wraps its work in a
`new Promise(...)` that never calls `reject`, so a failing `getRepoContents` hangs the caller.

**The code fix has already shipped.** Commit `13c20aac` ("feat(portal): log failed requests and show
CWL parse errors", 2026-11-04) rewrote it as a plain `async` function (utils.ts:97-112) with no
Promise wrapper, so any rejection from `getRepoContents` (or `atob`) propagates. Its doc comment
already says "rejects if it can't be fetched". The only caller, `loadToolCwl` in
`BaseAnnotateStep.vue:280-283`, catches the error and shows it on the page, and
`BaseAnnotateStep.spec.ts:71-80` ("shows why a public GitHub tool's CWL could not be fetched")
covers that path. Only the backlog entry is stale.

## Change (doc only)

In `docs/future_refactoring.md`, item 5 under the portal section, following the style of the
already-resolved items (Portal item 2, Repo item 3):

1. `### [ ] 5. A promise that never rejects` → `### [x] 5. A promise that never rejects`
2. Keep the Description and Why-skipped lines; add:
   `* **Resolved**: `getRepoRootCWLContent` is now a plain `async` function with no `new Promise`
   wrapper, so a failed `getRepoContents` call rejects it. The tool annotation step
   (`BaseAnnotateStep.vue`) catches the error and shows it on the page; `BaseAnnotateStep.spec.ts`
   covers this.`

No code or test changes: the behaviour is already correct and tested at the caller.

## Process

- Sync this plan to `docs/plans/2026-11-18-HHMMSS-promise-never-rejects/plan.md` (AGENTS.md rule).
- No ADR (no design choice). No container rebuild (docs only).
- Commit only if asked: `docs: resolve promise-never-rejects item in future_refactoring`, on a branch
  off `main`, with the plan folder in the same commit.

## Verification

- `make docs-check` (git add the new plan folder first) passes.
- Optional sanity: `make test-frontend` still passes (code unchanged), including the
  "could not be fetched" test.
