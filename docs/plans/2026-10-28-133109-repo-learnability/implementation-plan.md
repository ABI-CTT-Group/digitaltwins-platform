# Plan: make the repo easy to learn for humans and AI agents

## Context

New developers, AI agents and operators all get lost in this repo today (interview answer: all three). The repo already has good material: a docs index, mermaid diagrams in `docs/architecture.md`, 34 ADRs, `make test`/`make lint`, and nginx/builder READMEs. What's missing is the layer that tells you **where things are and how they connect**:

- `AGENTS.md` covers process only (artifacts, ADRs, secrets, Docker rebuild). It has no repo map, commands or safety rules. There's no `CLAUDE.md`, `GEMINI.md` or Copilot file.
- No "where does code for X live" map, no request-flow walkthrough, no glossary of domain terms (SDS, SEEK ISA objects, SOP, tool, workflow, plugin).
- 7 active services have no README (jupyterhub, pacs, postgres, minio, hapi-fhir, seek, keycloak has only REALM.md). 3 inactive folders (jupyterlab, pacs_pretend_external, irods) aren't marked as inactive.
- `util/README.md` is an install runbook, not a script index. About 37 of the ~70 scripts aren't mentioned in it, and 11 are documented nowhere.
- Key gotchas live only in untracked artifacts or nowhere. Examples: `MINIO_SERVER_SECRET_KEY` must equal `MINIO_ROOT_PASSWORD`; destructive scripts (`docker_delete_volumes.sh`, `reset.sh`, `portal-restore.sh`); never `down -v` or daemon-wide prune.
- `docs/testing.md` has no "how to write a test" section or suite map. The PACS manual tests aren't covered.
- 8 broken links in `services/portal/docs/release-notes.md`. `services/portal/docs/deployment-guide.md` is stale ("Clinical Dashboard", old submodule).

## Decisions from the interview

| Topic | Decision |
|---|---|
| Scope | **Docs and agent files only.** No file or folder moves, no Dockerfile or compose changes. |
| AI tools | Claude Code, Codex/AGENTS.md tools, Gemini/Antigravity, Copilot/Cursor. **`AGENTS.md` is the single source of truth.** Every agent instruction lives in an `AGENTS.md` (root, or nested for a service). Tool-specific files exist only because some tools don't read `AGENTS.md`; they hold nothing but a pointer, and `docs-check` enforces that (ADR below). |
| Diagrams | Mermaid in Markdown |
| Doc checks | Link check plus map check, as `make docs-check` and a CI job |
| `docs/artifacts/` | Historical audit record, not reference. Signpost it; don't edit the contents. |

## Target layout (new = ✚, changed = ✎)

```
AGENTS.md                      ✎ canonical agent guide (restructured, process rules kept verbatim)
CLAUDE.md                      ✚ "@AGENTS.md"
GEMINI.md                      ✚ "@AGENTS.md"   (.agents/rules/main.md already imports AGENTS.md)
.github/copilot-instructions.md ✚ 3-line pointer to AGENTS.md (no import syntax in Copilot)
                                  (Cursor and Codex read AGENTS.md natively; no .cursor/rules)
docs/README.md                 ✎ add "Start here" reading paths per role + new pages
docs/codemap.md                ✚ where code lives, per service; how services connect (couplings table)
docs/request-flows.md          ✚ mermaid sequence diagrams for the main user journeys
docs/glossary.md               ✚ domain and platform terms
docs/testing.md                ✎ suite map, how to write a test, PACS manual tests, docs-check
docs/artifacts/README.md       ✚ "historical record; may be stale; read guides and ADRs first"
docs/decisions/2026-10-28-agents-md-single-source.md ✚ ADR
services/<svc>/README.md       ✚/✎ standard sections (below), for every service folder
services/{api,builder,portal,airflow}/AGENTS.md ✚ short local rules (≤60 lines) + CLAUDE.md "@AGENTS.md"
util/SCRIPTS.md                ✚ index of every util/ entry, grouped, with a "destructive?" column
util/check_docs.py             ✚ link and map checker (stdlib Python)
util/tests/test_check_docs.sh  ✚ tests for the checker (bash, same style as test_compose_file.sh)
Makefile, .github/workflows/ci.yml ✎ docs-check target and job
```

## Implementation steps

Work on a new branch off `main` (e.g. `docs/repo-learnability`), with one atomic Conventional Commit per step. **Step 0:** sync this plan and the ADR to `docs/artifacts/2026-10-28-<HHMMSS>-repo-learnability/` (repo-relative paths only, no secrets), then re-sync after every plan change.

### 1. Agent entry points → verify: each tool loads the guide
Restructure `AGENTS.md` (target ≤150 lines) into:
1. What the repo is (3 lines), plus a read order: root `README.md` (what the platform is, architecture overview, deploy and test entry points) → `docs/README.md` → `docs/codemap.md` → the service README → ADRs.
2. Top-level repo map: one line per directory, linking to `docs/codemap.md`.
3. Commands: `make test`, `make test-<suite> PYTEST_ARGS=...`, `make lint`, `make docs-check`, `make gitleaks`.
4. **Safety rules:**
   - never run builder or API tests in live containers (`BUILDER_DB_HOST` drops the portal schema);
   - no `docker compose down -v` and no daemon-wide prune (remove sandbox containers by label);
   - list the destructive util scripts;
   - never mount the repo root into test containers;
   - the MinIO key coupling.
5. "If you change X, also check Y" coupling table (from the audit):
   - builder copies of `migration_runner.py` and `keycloak_verifier.py` must match the API's;
   - `JUPYTERHUB_API_TOKEN` must be set on both sides;
   - nginx routes live in both the gateway and portal-frontend nginx configs;
   - the builder env must never hold API credentials;
   - the API bind-mounts `airflow/dags`.
6. `docs/artifacts/` is history: don't treat it as current truth.
7. The existing process rules (artifacts, ADRs, secret scanning, Docker rebuild), **kept verbatim**.

Then add the pointer files (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`) and nested `AGENTS.md` + `CLAUDE.md` for api, builder, portal and airflow.

**Single-source rule:**
- All instructions live in `AGENTS.md` files.
- Pointer files contain only the import line (`@AGENTS.md`) or, for Copilot, a one-line "Follow AGENTS.md" pointer. Nothing else.
- `.agents/rules/main.md` keeps its existing frontmatter plus import.
- Nested `AGENTS.md` files never repeat root content. They add only service-local rules, such as the API's `integration` marker and fixtures, the frontend `__tests__/*.spec.ts` convention, DAG folder ownership, and the builder security boundary.

### 2. Code map, connections, flows, glossary → verify: renders on GitHub, links resolve
- `docs/codemap.md`:
  - a table per service: path, role, entry point (e.g. `services/api/app/main.py`, `app/routers/`, `src/digitaltwins/<area>/`), migrations, tests, compose file;
  - a **couplings table**: from → to, mechanism (env var, hostname, mount, shared volume, token), what breaks if it's wrong;
  - an "inactive" section listing jupyterlab, pacs_pretend_external, irods, `services/api/docker/*` and the extra services in the portal compose.
- `docs/request-flows.md`: 3–4 mermaid `sequenceDiagram`s. Sign-in through the gateway and Keycloak; upload or import a dataset (portal → api → MinIO/SEEK/FHIR); launch an assay (api → Airflow DAG → worker → MinIO → SEEK); build and deploy a GUI tool or plugin (portal → builder → nginx). Each step links to the handling code.
- `docs/glossary.md`: SDS, SEEK investigation/study/assay, SOP, tool vs workflow vs plugin, DAG, measurement dataset, cohort (subject indices to run), realm and clients.
- `docs/architecture.md`: add links to these three pages only; leave the existing diagrams as they are.

### 3. Per-service READMEs → verify: every `services/*` folder has a README with the sections
Each README uses the same sections: **Purpose · Status (active/inactive) · Code map · Connects to · Configuration (env var names only, no values) · Run & test · Gotchas · Related ADRs**.
- New: jupyterhub, pacs, postgres (explain `digitaltwins_schema.sql` vs the API migrations), minio (bucket init and the key coupling), hapi-fhir, seek (submodule), keycloak (short, pointing to REALM.md), and stub READMEs for the 3 inactive folders.
- Add a "Developing this package" section to `services/api/README.md` that points to `make test-api`.
- Existing good READMEs (nginx, builder) only get any missing sections.
- Fix the 8 broken links in `services/portal/docs/release-notes.md`. Add a "historical, superseded by docs/deployment.md" banner to `services/portal/docs/deployment-guide.md`.

### 4. util index → verify: every util/ entry appears in util/SCRIPTS.md
- `util/SCRIPTS.md`: groups are install/airgap, env and secrets, certs, Keycloak, SEEK admin, backup/restore, sync, reset, observability, and legacy.
- Each row has: script, one-line purpose, run where (host/container), destructive? (Y/N), and the doc with details.
- Get each purpose from the script's header or body; mark it "purpose unclear" rather than guess.
- Add a link to SCRIPTS.md at the top of `util/README.md` and from `docs/README.md`.

### 5. Testing docs + doc checks (TDD) → verify: red, then green
1. **Red:** write `util/tests/test_check_docs.sh` with temporary fixture trees. Cases: a broken relative link fails; a valid link passes; `#anchor` suffixes and external URLs are ignored; a `services/foo/` missing from the codemap fails; a util entry missing from SCRIPTS.md fails; files under `docs/artifacts/` are skipped. Run `make test-util`; it should fail.
2. **Green:** `util/check_docs.py` (stdlib only). It checks:
   - (a) relative links in tracked `*.md` files resolve, excluding `docs/artifacts/`;
   - (b) every `services/*/` directory is named in `docs/codemap.md`;
   - (c) every top-level `util/` entry is named in `util/SCRIPTS.md`;
   - (d) agent pointer files hold only their pointer: every `CLAUDE.md`/`GEMINI.md` has an `AGENTS.md` beside it, and Copilot's file and `.agents/rules/main.md` contain nothing beyond the allowed lines. This keeps `AGENTS.md` the single source of truth.

   Add red-test cases for (d) too: a `CLAUDE.md` with extra content fails, and a `CLAUDE.md` without a sibling `AGENTS.md` fails.
3. Add `make docs-check` using `PY311_IMAGE` with `--network none`. To keep `.env`/`secrets.env` out of the container (the Makefile's rule), pipe the tracked files in with `git ls-files -z | tar --null -T - -c | docker run -i ...` instead of mounting the root. Hook `test_check_docs.sh` into `test-util`.
4. Add a `docs` job to `ci.yml`, path-filtered to `**/*.md`, `services/**`, `util/**`. It starts report-only like `lint`. Make it a required check once it's green on `main` (your call).
5. Update `docs/testing.md`:
   - suite map (suite → location → runner → make target → CI job → what's not covered: DAGs, nginx, realm, e2e);
   - "writing a test" (API fixtures and the `integration` marker, builder's `BUILDER_DB_HOST` guard, frontend `__tests__` convention);
   - PACS manual tests;
   - `docs-check`.
6. Add a docs checkbox to `.github/pull_request_template.md`: "updated codemap/SCRIPTS.md/service README if structure changed".

### 6. Role-based hub + artifacts signpost → verify: walkthroughs below
- `docs/README.md`: add a **Start here** block at the top with three reading paths, each 4–6 links in order:
  - *New developer*: README → architecture → codemap → request-flows → glossary → development → testing.
  - *AI agent*: AGENTS.md → root README.md → codemap → service README/AGENTS.md → ADRs.
  - *Operator*: deployment → util/README → SCRIPTS.md → diagnostics → production.
- `docs/artifacts/README.md`: explain what artifacts are (regulated-environment design evidence, one folder per change), that they may be stale, and to read guides and ADRs first.
- Task end: check whether any decision emerged mid-way and update the ADR; final artifact sync.

## ADR draft: `docs/decisions/2026-10-28-agents-md-single-source.md`

- **Context:** the team uses Claude Code, Codex, Gemini/Antigravity and Copilot/Cursor. Each reads a different file, and separate copies would drift apart.
- **Option A, a full file per tool:** tailored to each tool, but 4× the maintenance and guaranteed drift.
- **Option B, symlinks to AGENTS.md:** one copy, but symlinks break on some Windows checkouts (we ship a WSL guide), and Copilot/Gemini tooling handles them inconsistently.
- **Option C (chosen), canonical AGENTS.md plus one-line import/pointer files** (`@AGENTS.md` where supported, a short text pointer for Copilot). Nested AGENTS.md files hold service-local rules only.
- **Consequences:**
  - `AGENTS.md` is the single source of truth, with one place to edit per scope (root or service).
  - Tool-specific tips must go in AGENTS.md under a labelled subsection, never in a pointer file. `make docs-check` enforces this.
  - Copilot's pointer depends on the agent following a link.

## What is deliberately not in scope

- Moving or renaming files, deleting inactive services, or fixing old names in code (`clinical-dashboard`, `preprocessor`). These get **listed** in `docs/future_refactoring.md`, not changed.
- Folding knowledge from artifacts into the guides. The exception is the gotchas named above, which go into AGENTS.md and the service READMEs.
- New unit or e2e tests for services. The gaps get documented in the testing suite map.

## Verification

1. `make docs-check` passes; `make test-util` passes, including the new checker tests. Break a link on purpose and confirm it fails.
2. `make test` and `make lint` are unchanged (docs only). **No Docker images need rebuilding**: no service code, Dockerfile or compose file changes.
3. `make gitleaks` and the pre-commit hook pass. Grep the new docs for absolute `/home/` paths and secret values (there should be none).
4. Agent smoke test: in a fresh Claude Code session (and Gemini if available), ask "Where is the code that starts an assay's Airflow run, which services does it touch, and how do I test a change to it without touching the live database?" It should answer from the docs with correct paths and the safety rule.
5. Human walkthrough: someone unfamiliar follows each "Start here" path and reports where they got stuck. You run this one.
6. View the mermaid diagrams on GitHub (PR preview) to confirm they render.
