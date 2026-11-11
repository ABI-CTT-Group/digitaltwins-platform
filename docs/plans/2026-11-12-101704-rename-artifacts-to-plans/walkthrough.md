# Walkthrough: rename `docs/artifacts/` to `docs/plans/`

Branch `docs/rename-artifacts-to-plans` in both VeriFlow (from `main`) and digitaltwins-platform (from `origin/main`).
Plan: [plan.md](plan.md). ADR: `docs/decisions/2026-11-12-name-the-design-evidence-folder-plans.md` (same text in both repos).

## What changed

| | digitaltwins-platform | VeriFlow |
|---|---|---|
| Folder | `docs/artifacts/` → `docs/plans/` (89 folders, 4 loose files) | `docs/artifacts/` → `docs/plans/` (8 folders) |
| Rules (`AGENTS.md`) | `## Plans`; paths; the 7 term changes in the plan; "code, docs or plans" | `## Plans`; paths; the same 7 term changes |
| Paths and links | `CONTRIBUTING.md`, `docs/README.md`, `codemap.md`, `testing.md`, `future_refactoring.md`, 3 ADRs, `style.css` comment, pre-commit comment | `backend/paper-record/CHANGELOG.md`, pre-commit comment |
| Folder index | `docs/plans/README.md`: "Plans", "plan folder", anchor `#plans` | New `docs/plans/README.md`, copied from digitaltwins |
| Glossary | "Artifact" → "Plan folder", moved to alphabetical order; ADR entry says "Compare *plan folder*" | (no entry) |
| Docs checker | `SKIP_PREFIX = "docs/plans/"`, test "docs/plans is skipped" | (none) |
| ADRs | New ADR | New ADR; `2026-11-12-align-docs-layout-…` marked "superseded in part" |

## Deviations from the plan

- VeriFlow's `docs/plans/README.md` points at `AGENTS.md`, `GLOSSARY.md` and the ADRs instead of digitaltwins'
  `docs/README.md` and `codemap.md`, which VeriFlow does not have, and drops the `make docs-check` line.

## Verification

- **Red/green (digitaltwins):** with `test_check_docs.sh` changed first, `make test-util` failed
  (`FAIL docs/plans is skipped: want exit 0, got 1 … broken link gone.md`); after changing `check_docs.py`, 0 failures.
- `make docs-check`: 115 Markdown files, 0 problems.
- `git grep 'docs/artifacts'` outside `docs/plans/`: only ADRs that describe the old name.
- `git grep -wi artifact` outside `docs/plans/`: only other meanings (build, Docker, FHIR knowledge artifacts,
  dev/test artifacts; in VeriFlow, agent output) and the new ADR.
- The Process rules are identical in both repos apart from digitaltwins' Docker section (`diff`).
- VeriFlow `python -m pytest tests`: 423 passed. Every link in VeriFlow's changed Markdown resolves.
- gitleaks: no leaks in either plan folder or the changed files.
