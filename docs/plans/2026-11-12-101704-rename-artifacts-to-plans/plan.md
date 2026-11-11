# Plan: rename `docs/artifacts/` to `docs/plans/` in VeriFlow and digitaltwins-platform

Status: approved 2026-11-12 and implemented; see `walkthrough.md`.

## Why

"Artifact" is Google Antigravity's name for these documents. Elsewhere it means build or CI output, and in
VeriFlow it already means an agent's output (`GET /api/v1/orchestrate/{run_id}/artifacts/{agent_name}`,
`waitForArtifact.ts`, "validate generated artifacts"). An agent told to "sync artifacts" could reasonably
reach for the wrong thing. `plans` is the most widely recognised name for this folder.

## Decisions taken (from the user)

- Rename in **both** repos, so they stay identical.
- Rename the **term** too, wherever it means these documents: "artifact" becomes "plan" (a document) or
  "plan folder" (one dated folder). Uses meaning build, Docker or pipeline output stay as they are. Other
  rule wording stays as it is (wording fixes are still deferred).

## Rule text changes (both `AGENTS.md`, identical)

| Now | After |
|---|---|
| `## Agent Artifacts` | `## Plans` |
| folders in `docs/artifacts/` (every path) | `docs/plans/` |
| "any planning or summary artifact" | "any planning or summary document" |
| "**COMMIT POLICY:** Artifacts MUST be committed" | "Plans MUST be committed" |
| "`[ ] Sync artifacts to docs/artifacts/`" | "`[ ] Sync plans to docs/plans/`" |
| "create or update a plan or artifact" | "create or update a plan or summary document" |
| "all updated artifacts have been synced" | "all updated plans have been synced" |
| "Before staging artifact files" | "Before staging plan files" |

## digitaltwins-platform (branch `docs/rename-artifacts-to-plans` from `origin/main`)

1. `git mv docs/artifacts docs/plans` (89 dated folders and 4 loose files). Contents of the folders are
   history and are not rewritten.
2. `docs/plans/README.md` (the folder's index, not history): heading "Plans", "a plan folder", and anchor
   `AGENTS.md#plans`.
3. `AGENTS.md`: lines 19 and 28 (`docs/plans/`), line 63 ("code, docs or plans"), and the rule text above.
4. Paths and links: `CONTRIBUTING.md`, `docs/README.md` (2), `docs/codemap.md`, `docs/testing.md`,
   `docs/future_refactoring.md` (3), ADRs `2026-09-30-register-tools-…`, `2026-10-02-build-gui-workflow-tools`,
   `2026-11-06-card-status-sentence`, the comment in `services/portal/frontend/src/styles/style.css`, the
   comment in `.pre-commit-config.yaml`.
5. `docs/glossary.md`: entry "Artifact" becomes "Plan folder" (moved to keep alphabetical order); the ADR
   entry's "Compare *artifact*" becomes "Compare *plan folder*".
6. Docs checker: `util/check_docs.py` `SKIP_PREFIX = "docs/plans/"` and its docstring;
   `util/tests/test_check_docs.sh` case "docs/plans is skipped". **Red/green:** change the test first,
   `make test-util` fails; change the checker, it passes.
7. ADR `docs/decisions/2026-11-12-name-the-design-evidence-folder-plans.md` (alternatives: keep `artifacts`,
   `plans`, `specs`).
8. A copy of this plan folder in `docs/plans/2026-11-12-101704-rename-artifacts-to-plans/`.

→ verify: `git grep -n 'docs/artifacts'` outside `docs/plans/` finds only the new ADR; `git grep -nwi artifact`
finds no use that means these documents; `make docs-check` (after `git add`) and `make test-util` pass;
`make gitleaks` is clean.

## VeriFlow (branch `docs/rename-artifacts-to-plans` from `main`)

1. `git mv docs/artifacts docs/plans` (8 folders, including this plan's folder).
2. `AGENTS.md`: preamble line 6 (`docs/plans/`) and the rule text above.
3. `backend/paper-record/CHANGELOG.md`: 4 links; `.pre-commit-config.yaml` comment.
4. Add `docs/plans/README.md`, copied from digitaltwins without the `make docs-check` line (VeriFlow has no
   docs checker).
5. Same ADR as digitaltwins. Mark `2026-11-12-align-docs-layout-with-digitaltwins-platform.md`
   "Accepted; superseded in part by […]: the folder is `docs/plans/`" (digitaltwins' convention for partial
   supersession).

→ verify: `git grep 'docs/artifacts'` outside `docs/plans/` finds only the two ADRs; the Process rules are
identical in both repos (`diff`, ignoring digitaltwins' Docker section); backend tests pass; gitleaks clean.

## Not changed

- Uses of "artifact" that mean other things: build, Docker and CWL artifacts in digitaltwins' builder and
  util scripts; VeriFlow's agent artifacts, API, SPEC, README and rubric item "Output artifact obtainable".
- Text inside existing dated plan folders (history).
- VeriFlow's untracked `backend/rubric/v7/`.

## Commits (only when asked), per repo

1. `docs!: move docs/artifacts to docs/plans` (folder move and every path)
2. `docs: call design evidence "plans", not "artifacts"` (term changes, glossary, README, ADR, this plan)
