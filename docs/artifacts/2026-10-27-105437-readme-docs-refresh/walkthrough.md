# Walkthrough: README and documentation refresh

The changes follow `implementation_plan.md` in this folder.

## What changed

### README.md
- **Deploying:** a "which guide when" table replaces the single link to `util/README.md`, with one line of prerequisites above it.
- **New sections:** Documentation, and Development and testing.
- **Table of contents:** lists Populating data, Documentation, and Development and testing.
- **Contributing links:**
  - The Code of Conduct link is relative, replacing the `blob/master` URL.
  - "Contributing Guidelines" points to `CONTRIBUTING.md`.
- **License:** the line covers the whole platform, not only "the platform API".
- **Python badge:** 3.11.
- **Unchanged:** the introduction, Architecture, Team, Funding and Acknowledgements.

### License
- `services/portal/LICENSE` is now the Apache 2.0 text, identical to the root `LICENSE`. It was CC BY-NC 4.0.
- The ADR `docs/decisions/2026-10-27-relicense-portal-apache-2.md` records the decision. It notes that the portal's copyright holders must agree.

### Issue and PR templates
They moved from `services/api/.github/`, where GitHub ignores them, to the root `.github/`.
- **Bug report:** asks for platform version, deployment type, OS, browser, affected service and logs, and warns against pasting secrets.
- **Document request:** asks for the page and the platform version. The "sparc-me version" field is gone.
- **Feature request:** adds an affected-service field.
- **PR template:** type of change, how it was tested, and a checklist (docs, ADR, secrets, rebuild).

### New files
- **`CONTRIBUTING.md`:** branches, Conventional Commits, `make test` and `make lint`, the required CI checks, the gitleaks pre-commit hook, ADRs, `docs/development.md` and `AGENTS.md`.
- **`docs/README.md`:** an index of every guide, grouped as deploy and operate, use, develop, and reference.

### docs/deployment.md
Sections 1–8 are rewritten to match `util/airgap_build_step3.yml`:
- `gen-realm.sh` added;
- SEEK's `docker-compose.env` built from `secrets.env`;
- the TLS cert install;
- the airflow-init step;
- the SEEK bootstrap with `create-admin-user.sh` and `enable-features.sh`;
- the asset precompile after launch;
- the workflow DAGs;
- corrected access and credential tables.

The manual Keycloak, Airflow-role and SEEK browser setup is removed. §9 (Upgrading) is unchanged.

### Small fixes
| File | Fix |
|---|---|
| `docs/populating_data.md` | SEEK at `<platform>/seek`. The missing `examples/workflow/airflow/` step is gone. The API TODO now points to `util/populate-cpu-burn-assay.sh`. Portal measurement upload (`/catalogue/measurements`) is documented. The empty "Automated Data Population" stub now links to the data-transfer section of `util/README.md`. |
| `docs/diagnostics.md` | Removed the link to the missing `api_examples.md`. |
| `docs/gateway-pathway-access.md` | The `/` row describes the Vue SPA. A new `/api/builder` row gives the builder's role checks. The broken wiki-style link is replaced. |
| `services/nginx/README.md` | "Known gaps: none of the four platform routes work yet" is replaced by a "Path prefixes" table; all routes are live. |
| `services/portal/docs/plugin-system-architecture.md` | The registry is the Postgres `portal` schema, with SQLite only as the standalone fallback. A broken link to `RemoteComponentApp.vue` is fixed. |
| `util/README.md`, `services/keycloak/REALM.md` | The platform admin is `${PLATFORM_ADMIN_USERNAME}` (default `admin1`), not `admin`. |

## Verification
- **Links:** every relative link and `#anchor` in the 17 changed Markdown files resolves (script check, GitHub slug rules).
- **License:** `diff LICENSE services/portal/LICENSE` is empty.
- **Templates:** each issue template has `name` and `about` front matter.
- **Secrets:** gitleaks `--no-git` finds nothing in each changed file and in this artifact folder.
- **Local paths:** none in the diff.
- **Not run:** the new `docs/deployment.md` was not run end to end; that needs a fresh host. Each command was checked against the playbook and the scripts it calls.
- **Rebuild:** none needed; the changes are docs and license only.

## Flagged, not changed
- `CODE_OF_CONDUCT.md` names Microsoft (`opencode@microsoft.com`) as the contact.
- `.github/workflows/docker_vol_backup.yml` runs `buildout/util/backup.sh`, which no longer exists.
- The status table in `services/nginx/snippets/platform-routes.conf` still marks Airflow "NOT live". The route comment below it, and the nginx README, say it is live.
- `docs/deployment.md` §9 still uses `sudo docker compose`.
- The Windows/WSL guide exists only in the gitignored `my_workspace/`.
- The untracked file `docs/FAIRDOM-SEEK Projects for Auckland Bioengineering Institute`.
