# AGENTS.md: Digital Twins platform

This is the single source of agent instructions for this repository. `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md` and `.agents/rules/main.md` only point here; put any new instruction
in this file (or in a service's own `AGENTS.md`), never in a pointer file. `make docs-check` enforces it.

The platform is one Docker Compose project: an nginx gateway routes by path to a Vue portal, a FastAPI
API, a builder, Airflow, JupyterHub, SEEK, MinIO, HAPI FHIR and Orthanc, with Keycloak for sign-in.

## Read first

1. [README.md](README.md): what the platform is, the architecture overview, deploy and test entry points.
2. [docs/README.md](docs/README.md): index of every guide.
3. [docs/codemap.md](docs/codemap.md): where code lives in each service and how services connect.
4. The service's own `README.md`, and its `AGENTS.md` if it has one (api, builder, portal, airflow).
5. [docs/decisions/](docs/decisions/): read the related ADRs before changing a design.

[docs/glossary.md](docs/glossary.md) explains domain terms (SDS, SEEK assay, SOP, tool, workflow, plugin).
`docs/plans/` is dated design evidence kept for audit. It describes what was true when each change
was made, so it may be stale: trust the guides, the ADRs and the code over it. The exception is the
plan folder of your own branch, which is the live plan ([Plans](#plans)).
[docs/future_refactoring.md](docs/future_refactoring.md) lists known debt. Like the plans, its items
can be stale or wrong: check each one against the code before acting on it.

## Repository map

| Path | What it is |
|---|---|
| `docker-compose.yml` | Root compose project; pulls in each service's compose file |
| `services/<name>/` | One folder per service; see [docs/codemap.md](docs/codemap.md) |
| `docs/` | Guides, [ADRs](docs/decisions/), and `plans/` (audit history) |
| `util/` | Install, ops and admin scripts; indexed in [util/SCRIPTS.md](util/SCRIPTS.md) |
| `examples/` | Example workflow datasets |
| `Makefile` | Test, lint and docs-check entry points, shared with CI |
| `env.template`, `.env.template`, `secrets.env.template` | Host inputs, the rendered `.env` template, and the secrets template (see [docs/deployment.md](docs/deployment.md)) |

## Commands

Everything runs in pinned containers and needs only Docker and GNU make. CI calls the same targets.

| Command | What it does |
|---|---|
| `make test` | All unit-test suites |
| `make test-api` / `test-builder` / `test-frontend` / `test-jupyterhub` / `test-util` | One suite; add `PYTEST_ARGS="-k name"` to narrow a Python suite |
| `make lint` | ruff, eslint and vue-tsc; must pass (a required check in CI) |
| `make docs-check` | Doc links, the code map, `util/SCRIPTS.md` and agent pointer files; checks tracked files only, so `git add` new files first |
| `make gitleaks` | Secret scan of this branch's commits |
| `make smoke` | Read-only smoke tests against a running stack (`SMOKE_URL`); not in `make test` or CI ([tests/README.md](tests/README.md)) |

See [docs/testing.md](docs/testing.md) for integration tests and CI.

## Safety rules

- **Never run tests inside a live container.** The builder tests drop and recreate every table, so in
  the `builder` container (or any shell where `BUILDER_DB_HOST` is set) they would wipe the portal
  schema. Never point the API integration tests at a live database. Use `make test-*`, which runs each
  suite in a throwaway container.
- **Never delete Docker volumes on a shared host.** No `docker compose down -v`, no `docker volume prune`
  or `docker system prune`. Remove only containers you created, by name or label, with `docker rm -f -v`.
- **Don't run destructive util scripts** (`reset.sh`, `docker_delete_volumes.sh`, `portal-restore.sh`,
  the `rm-seek-*` scripts and others marked "Destructive" in [util/SCRIPTS.md](util/SCRIPTS.md)) unless
  the user asks for that exact action.
- **Don't blanket `docker compose up -d`** on a running deployment: it can recreate SEEK and others
  needlessly. Name the services you changed ([docs/development.md](docs/development.md)).
- **Never mount the repo root into a container**: it holds `.env` and `secrets.env`. Mount only the
  folders a job needs, as the Makefile does.
- **Never write secret values** into code, docs or plans. Use `<REDACTED>`, and name variables only.

## If you change X, also check Y

| When you change | Also check |
|---|---|
| MinIO credentials | `MINIO_SERVER_ACCESS_KEY` must equal `MINIO_ROOT_USER`, and `MINIO_SERVER_SECRET_KEY` must equal `MINIO_ROOT_PASSWORD`, or every platform S3 client gets 403 |
| `JUPYTERHUB_API_TOKEN` | Both the API and JupyterHub read it; they must match |
| The API's `migration_runner.py` or `keycloak_verifier.py` | The builder keeps identical copies; `make test-builder` fails until they match |
| The builder's environment | It must never hold API credentials (`services/builder/tests/test_service_separation.py`) |
| A gateway route | [services/nginx/README.md](services/nginx/README.md); the app's own prefix setting must match. The gateway strips `/api`, so no API route may start with `/api`. portal-frontend has its own nginx for `/api/builder` and `/plugin/*` |
| DAG files or the DAG folders | The API writes deployed workflows into `services/airflow/dags/workflow_<seek_id>/` through a bind mount; never edit those by hand ([services/airflow/README.md](services/airflow/README.md)) |
| The `digitaltwins` package in `services/api/src/` | The Airflow image installs a pinned release from PyPI, so DAGs don't see your change until that pin moves |
| A Keycloak client or role | [services/keycloak/REALM.md](services/keycloak/REALM.md); realm import runs on first boot only, and the portal's `VITE_KEYCLOAK_*` values are baked in at image build |
| A service folder, or a util script | Add it to [docs/codemap.md](docs/codemap.md) or [util/SCRIPTS.md](util/SCRIPTS.md) |

More couplings, with the mechanism and what breaks, are in [docs/codemap.md](docs/codemap.md#couplings).

---

# Process rules

## Plans

Each change keeps its design evidence in a plan folder:

- What it holds: the plan, the task checklist and, optionally, a walkthrough.
- Where it lives: `docs/plans/YYYY-MM-DD-HHMMSS-<feature>/`. The timestamp is the time of creation or
  last update; for example, `docs/plans/2024-03-15-143000-user-auth/`.
- When it is committed: in the same branch and PR as the change it describes. This is a
  regulated-environment requirement: every change must be traceable to its design.

A plan folder is live while its branch is open, and history once the branch merges
([ADR](docs/decisions/2026-11-23-plan-folders-live-on-their-branch.md)).

- **Start from the template.** Copy [docs/plans/TEMPLATE/](docs/plans/TEMPLATE/) to the new folder.
  - Write the plan straight into its `plan.md`.
  - Add a section when the change needs it: Risks for migrations, deploys or live data; Out of scope
    when the scope is disputed.
  - If a tool wrote the plan elsewhere (Claude Code plan mode writes to `~/.claude/plans/`), copy it
    into the folder before asking for review.
- **Header.** `plan.md` opens with `Status: active` and `Branch: <branch>`.
- **Track progress in `tasks.md`.**
  - It has one checklist item per plan step, each with its check: a command and the result that
    means done. `plan.md` says what each step changes; the check lives only in `tasks.md`.
  - Tick each item the moment its check passes, before starting the next step: people follow the
    work's progress from this file. The last item closes the plan (below).
  - Before a session stops, update the `## Progress / Next steps` section at the end (Done, Next,
    Open questions). A session that picks up the work reads `tasks.md` first.
- **Close the plan in the PR's last commit.**
  - Set `Status: done`. Add a note if the outcome differs from the plan, e.g.
    `Status: done (steps 3–4 dropped)`.
  - Tick the remaining tasks.
  - Rename "Next" to "Follow-ups", listing what moved to `docs/future_refactoring.md`, or "none".
  - If review asks for more work, set the status back to `active`.
- **Finding live work.** Plans on other branches aren't in your checkout, and every plan folder on
  `main` is closed. `gh pr list` shows the team's open work, and `git worktree list` shows your own.
- **Redact.** Plans hold no passwords, keys or tokens. Write `<REDACTED>` and name the variable. The
  `gitleaks` pre-commit hook backs this up; it doesn't replace it.

Folders created before 2026-11-23 have no header and may use other file names; leave them as they are.

---

## Architecture Decision Records (ADRs)

When a task involves a **significant design decision**, document it as an ADR in `docs/decisions/`.

**Location:** `docs/decisions/YYYY-MM-DD-title.md` (timestamped, one per decision).
**Template:** See `docs/decisions/TEMPLATE.md`.

**When to create an ADR — only when:**
- A real choice between alternatives was evaluated
- A deviation from an existing convention or architecture was made
- A non-obvious tradeoff with future consequences was accepted

Do NOT create ADRs for routine fixes, minor refactors, or straightforward implementations with no real alternatives.

**Two checkpoints:**
1. **At plan-approval time:** When the implementation plan involves a real choice between alternatives, draft an ADR alongside the plan. Present it to the user for review together with the plan.
2. **At task-end:** Check whether any decisions emerged mid-implementation that weren't captured at plan time. If so, create or update the ADR. If the outcome diverged from the plan-time ADR, update it to reflect what actually happened.

ADRs MUST be committed in the **same branch/PR** as the related code changes.

---

## Technical debt

Debt you find but don't fix goes in `docs/future_refactoring.md`, with a Description and a Why skipped.
When a change fixes an item, remove it in the same PR. If the item holds guidance that stays true
after the fix, move it first to the doc that covers that area: a service's `AGENTS.md` or README, a
guide in `docs/`, or the couplings in `docs/codemap.md`.

---

## Secret Scanning

A `gitleaks` pre-commit hook is configured in `.pre-commit-config.yaml` to automatically block commits containing secrets. This is a mandatory control for this regulated-environment project.

**Agent responsibilities:**
1. **Proactive redaction:** Always use placeholders like `<REDACTED>` for any passwords, API keys, tokens, or sensitive environment variables in all documents.
2. **Pre-sync scan:** Before staging plan files, verify no secrets are present. If unsure, run `gitleaks detect --source docs/plans/ --no-git` and fix any findings.
3. **Never bypass:** Do not advise or assist in bypassing the pre-commit hook.

---

## Docker Container Management

When making code changes that affect services running in Docker containers:
1. **Rebuild and Restart:** Always rebuild and restart the affected Docker images/containers to ensure the changes are applied and tested. You MUST explicitly mention in your response that you have successfully rebuilt and restarted the images.
2. **Provide Commands:** If you cannot restart them yourself, or if you need the user to take action, you MUST explicitly print the exact `docker` or `docker compose` commands required to rebuild and restart the affected services for the user to run.
