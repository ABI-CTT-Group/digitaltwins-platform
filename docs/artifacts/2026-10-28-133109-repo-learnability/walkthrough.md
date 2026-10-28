# Walkthrough: repo learnability (docs and agent files only)

Goal: make the repo easy to learn for new developers, AI agents and operators, without moving any
files. Plan: [implementation-plan.md](implementation-plan.md). ADR:
[2026-10-28-agents-md-single-source.md](../../decisions/2026-10-28-agents-md-single-source.md).

## What changed

| Area | Files |
|---|---|
| Agent entry points | `AGENTS.md` gained a read order, a repo map, commands, safety rules and a couplings table; the process rules are unchanged. New pointers: `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`. Nested `AGENTS.md` + `CLAUDE.md` in `services/{api,builder,portal,airflow}/`. |
| Maps and diagrams | New `docs/codemap.md` (every service, the compose layout, couplings, "change X: where to look"), `docs/request-flows.md` (four mermaid sequence diagrams: sign-in, dataset upload, assay launch, tool/plugin deploy), `docs/glossary.md` (30 terms). `docs/architecture.md` links to them. |
| Service docs | New READMEs for postgres, minio, hapi-fhir, keycloak, seek, jupyterhub and pacs, and short "inactive" READMEs for jupyterlab, pacs_pretend_external and irods. Missing sections added to the nginx, builder, airflow, portal and api READMEs. 9 broken links fixed in `services/portal/docs/release-notes.md`; a "historical" banner on `services/portal/docs/deployment-guide.md`. |
| util index | New `util/SCRIPTS.md`, indexing all 71 entries with a "Destructive?" column; linked from `util/README.md`. |
| Docs check | New `util/check_docs.py` and `util/tests/test_check_docs.sh` (12 cases), a `make docs-check` target, `test-util` running every `util/tests/test_*.sh`, and a report-only `docs` CI job. |
| Hub and history | `docs/README.md` "Start here" paths for each role; `docs/artifacts/README.md` (history, not reference); `docs/testing.md` (suite map, writing a test, PACS manual tests, docs check); a PR template checkbox; a CONTRIBUTING note; and 5 layout and cleanup items in `docs/future_refactoring.md`. |

## Decisions made during implementation

- `make docs-check` pipes only tracked files into the container as a tar, rather than mounting the
  repo root, so `.env` and `secrets.env` never reach it. New files must be `git add`ed first.
  `--no-recursion` keeps the SEEK submodule as an empty folder.
- The checker skips `docs/artifacts/` (history) and `TEMPLATE.md` files (their links are placeholders).
  It doesn't check `#anchor` fragments.
- The CI `docs` job starts report-only, like `lint`. Making it required is a later ruleset change.

## Verification

- TDD: `util/tests/test_check_docs.sh` failed (11 of 11) before `check_docs.py` existed, and then
  passed. The `TEMPLATE.md` case was added red-first too.
- `make test-util`: both suites pass (0 failures).
- `make docs-check` with the new files added to the index: 106 Markdown files, 0 problems. With a
  broken link added on purpose, it exits non-zero.
- gitleaks (`dir` mode) on every new and changed file: no leaks. No absolute local paths in the new
  docs.
- No service code, Dockerfile or compose file changed, so no image rebuild is needed.

## Found, not fixed (out of scope: docs only)

- Six `#anchor` links in the contents list of `services/api/README.md` point at headings that no
  longer exist. This predates this change.
- The other stale comments and possible bugs found while documenting are listed in
  `docs/future_refactoring.md` or were reported to the user for triage.
