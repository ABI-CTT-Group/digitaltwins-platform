# Plan: README and documentation refresh

## Context

The top-level README has several stale claims:
- It says issue and PR templates "are provided", but GitHub ignores them where they currently live.
- The "Contributing Guidelines" link points back to the README itself.
- The Code of Conduct link uses a `master` branch that doesn't exist.
- It says the platform is Apache 2.0, while `services/portal/LICENSE` is CC BY-NC 4.0.
- Its deployment section links only the airgap runbook.

Several docs it leads to have also drifted:
- `docs/deployment.md` still uses `admin`/`admin`, has manual Keycloak/SEEK setup and a TODO, and has no `gen-realm.sh` step.
- `docs/populating_data.md` points at missing paths.
- `docs/diagnostics.md` has a broken link.
- The nginx README still says the routes don't work.
- The plugin architecture doc describes a SQLite registry.

## Decisions from the interview

| Topic | Decision |
|---|---|
| README introduction | Keep as is |
| README Team section | Keep as is |
| Quick start | Links only: a "which runbook" deployment section, no commands |
| Portal license | It was a mistake. Relicense `services/portal` under Apache 2.0, the same as the platform |
| Code of Conduct | Keep the file. Only fix the README link |
| Issue/PR templates | Move from `services/api/.github/` to the root `.github/`, adapt them to the whole platform, and review them |
| Other docs | Fix `docs/deployment.md`, fix the small stale docs, add `CONTRIBUTING.md`, add a `docs/README.md` index |

## Changes

### 1. `README.md`
- **Table of contents:** add Populating data, Documentation, and Development and testing.
- **Deploying:** a short table of which guide to use when:
  - connected install: `docs/deployment.md`
  - airgapped/production install: `util/README.md`
  - full system with observability and remote compute: `util/BUILD-FULL-SYSTEM.md`
  - macOS/arm64 dev host: the `util/README.md` section
  - production hardening: `docs/production.md`
  - day-to-day development: `docs/development.md`

  Add one line of prerequisites: Ubuntu 24.04 amd64, Docker Engine with Compose v2, optional NVIDIA GPU.
- **Documentation:** a new section linking `docs/README.md`, the architecture doc and the `digitaltwins` Python package README.
- **Development and testing:** a new section covering `make test`, `make lint`, `docs/testing.md` and `CONTRIBUTING.md`.
- **Reporting issues / Contributing:**
  - Fix the CoC link to the relative `CODE_OF_CONDUCT.md`.
  - Point "Contributing Guidelines" at `CONTRIBUTING.md`.
  - The template claims become true once step 3 is done.
- **License:** "The DigitalTWINS platform is … Apache License 2.0", with the word "API" dropped.
- **Python badge:** change it to 3.11, which is what the services run.
- **Unchanged:** Introduction, Architecture, Team, Funding and Acknowledgements.

### 2. `services/portal/LICENSE`
Replace the CC BY-NC 4.0 text with the Apache 2.0 text, identical to the root `LICENSE`. Nothing else in the portal declares a license; `package.json` has no `license` field.
- **ADR:** `docs/decisions/2026-10-27-relicense-portal-apache-2.md` records the decision and the reason (consistency with the platform). It also notes that relicensing needs the agreement of the portal's copyright holders.

### 3. Root `.github/` templates (`git mv` from `services/api/.github/`)
| File | Changes |
|---|---|
| `ISSUE_TEMPLATE/bug_report.md` | Platform-wide environment fields: platform version (tag or commit), deployment (connected, airgapped, http/https), host OS and arch, browser, affected service(s), and logs (`docker compose logs <service>`). Warn against pasting secrets. |
| `ISSUE_TEMPLATE/document-request.md` | Replace "the version of sparc-me" with "which doc/page, and platform version". Fix the "documentations you will love" grammar. |
| `ISSUE_TEMPLATE/feature_request.md` | Add an "affected service(s)" field. Otherwise unchanged. |
| `pull_request_template.md` | Description, related issues, type of change (Conventional Commit type), how it was tested (`make test`/`make lint`, deployment tried). Checklist: docs updated, ADR if a design decision, no secrets, containers rebuilt if needed. Fix the "enviroment" typo. |

### 4. New `CONTRIBUTING.md`
Each item cites where the convention already lives:
- Fork or branch, then a PR to `main`.
- Branch names like `feat/…` and `fix/…`, and Conventional Commits; both are already the repo's practice in `git log`.
- `make test` and `make lint`; the required CI checks are listed in `docs/testing.md`.
- The `pre-commit install` gitleaks hook.
- ADRs in `docs/decisions/`, using `TEMPLATE.md`.
- Update docs with the code.
- AI coding agents follow `AGENTS.md`.
- Code of Conduct, and how to report issues.

### 5. New `docs/README.md` (documentation index)
One-line entries, grouped:
- **Deploy and operate:** deployment, production, domain change, diagnostics, `util/README.md`, `BUILD-FULL-SYSTEM.md`, `RESET.md`, the compute node.
- **Develop:** development, testing, workflow DAG authoring, future refactoring.
- **Reference:** architecture, gateway pathway access, SEEK integration, the Keycloak realm, populating data.
- **Service docs:** the api/SDK, import-dataset, builder, portal, plugin system, nginx, airflow.
- **Decisions:** `docs/decisions/`.

Agent history in `docs/artifacts/` is excluded.

### 6. `docs/deployment.md`: rewrite sections 2–8, keep §9 (Upgrading)
I'll align it with what `util/airgap_build_step3.yml` actually does, as a manual connected install:
1. Clone with `--recursive`.
2. Configure:
   - `env` and `secrets.env`, with the localhost block for a local install;
   - `util/gen-env.sh`;
   - **`util/gen-realm.sh`** (new);
   - SEEK `docker-compose.env` from the `MYSQL_*` values in `secrets.env`;
   - for https, certs in `services/nginx/certs/server.{crt,key}`.
3. `docker compose build`.
4. `docker compose up airflow-init`, then `down`.
5. Bootstrap SEEK:
   - `up -d seek`;
   - `util/create-admin-user.sh "$PLATFORM_ADMIN_USERNAME" "$PLATFORM_ADMIN_PASSWORD" "$PLATFORM_ADMIN_EMAIL"`;
   - `SEEK_SITE_BASE_URL=<proto>://<domain>/seek util/enable-features.sh`;
   - `down`.

   This replaces the manual browser and Rails-console steps.
6. `docker compose up -d`, then precompile SEEK assets (`rake assets:precompile`, `tmp:clear`, restart seek, workers and portal-frontend).
7. Workflow DAGs: a fresh install has none. Point to how DAGs get deployed.
8. Access and credentials table:
   - Keycloak master console: `admin` / `KC_BOOTSTRAP_ADMIN_PASSWORD`.
   - Platform admin: `PLATFORM_ADMIN_USERNAME`, default `admin1`, / `PLATFORM_ADMIN_PASSWORD`. It is one identity for the Keycloak realm, SEEK and Airflow, and already has `airflow_admin`.
   - MinIO root: `minioadmin` / `MINIO_ROOT_PASSWORD`.
   - Test users: `clinician`, `researcher`, `test1`, `test2`.

Removed: Keycloak "Method 1/2" (manual config with a TODO, and realm export/import), the manual `airflow_admin` role assignment (the realm template already grants it), and the manual SEEK browser setup at `localhost:8001`.

### 7. Small stale-doc fixes
| File | Fix |
|---|---|
| `docs/populating_data.md` | SEEK UI at `<platform>/seek`, not `localhost:8001`. Remove the missing `examples/workflow/airflow/` copy step. Point the API "Method 2" TODO to `util/populate-cpu-burn-assay.sh` as a worked SEEK-API example (to verify). Mark the portal upload as available if the portal's measurement upload is live (to verify). Replace the "Automated Data Population" stub with a link to the data-transfer section of `util/README.md`. |
| `docs/diagnostics.md` | Remove the link to the missing `api_examples.md`. |
| `docs/gateway-pathway-access.md` | `/` row: the portal is a Vue SPA, and its backend is the `builder`. Re-check which auth code is wired and update the text. Replace the broken `[[reference_seek_permission_model]]` wiki link. |
| `services/nginx/README.md` | Replace "Known gaps: none of the four platform routes work yet" with the current state, after checking the prefix settings for `/seek`, `/airflow`, `/jupyter` and `/auth`. |
| `services/portal/docs/plugin-system-architecture.md` | The registry is the `portal` schema in the platform Postgres, with SQLite only as a standalone fallback. The backend is `builder`. |
| `util/README.md` §6 | The realm admin user is `${PLATFORM_ADMIN_USERNAME}` (default `admin1`), not `admin`. |
| `services/keycloak/REALM.md` | Same admin-user naming fix. |

## Out of scope (I'll flag these, not change them)
- `CODE_OF_CONDUCT.md` still names Microsoft as the contact.
- `.github/workflows/docker_vol_backup.yml` calls `buildout/util/backup.sh`, which no longer exists.
- The Windows/WSL guide is only in the gitignored `my_workspace/` and is untested.
- The untracked file `docs/FAIRDOM-SEEK Projects for Auckland Bioengineering Institute`.
- The external links (12 LABOURS, SPARC, Google Drive, MBIE) are not checked.

## Verification
1. **Links:** every relative link and `#anchor` in the changed Markdown files resolves (script check).
2. **Facts:** each command in `docs/deployment.md` is cross-checked against the playbook and the scripts it calls. It is not run end to end: that needs a fresh host, and running it here would disturb the live stack.
3. **Licenses:** `diff LICENSE services/portal/LICENSE` is empty.
4. **Templates:** GitHub template front matter is valid (name, about).
5. **Secrets:** `gitleaks detect --no-git` on the changed files and the artifacts.
6. **Rebuild:** none needed; this is docs and license only.
7. **Commits:** nothing is committed until you ask. When asked, these become separate atomic commits: README and docs; templates and CONTRIBUTING; portal license and its ADR.
