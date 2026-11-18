# Plan: post-deploy smoke tests in the root `tests/` folder

## Context

`docs/future_refactoring.md` "Repository layout" item 4 says the root `tests/` holds only a
`.gitkeep`: "Use it for end-to-end tests, or remove it." Rather than delete it, we fill it
with a first, small set of **post-deploy smoke tests** (user's choice): run by hand against an
already-running stack (local, staging or demo) right after a deploy or upgrade, to answer "is the
platform up and wired correctly?" They go through the gateway exactly as a user does, and only
read. That closes item 4 and gives the platform its first end-to-end check.

Out of scope: CI (the stack can't run in the offline CI jobs), browser/Playwright tests of portal
screens (those would go in `services/portal/frontend/e2e/` later), anything that writes data.

## Design

**Tool:** pytest + httpx, pinned to the API's versions (`pytest==9.0.3`, `httpx==0.28.1`,
from `services/api/requirements-test.txt`), in the pinned `PY311_IMAGE` with a cached venv,
following the `test-api` pattern in the root `Makefile`.

**Run:** `make smoke` (default `SMOKE_URL=http://localhost`), e.g.
`make smoke SMOKE_URL=https://<staging-domain>`. Not part of `make test` and not in CI.
- Uses `--network host` (not `$(OFFLINE)`), so it reaches `localhost` or a remote domain.
- Mounts only `tests/` (never the repo root: `.env`/`secrets.env` stay unseen).
- Credentials come from the caller's environment, `SMOKE_USERNAME` and `SMOKE_PASSWORD`, passed
  as `-e NAME` (no value on the command line, so they don't show in `ps` or make output). The
  tests never print them. Without them, the signed-in tests **skip with a reason** and the
  public checks still run (my call: lets someone without an account check a host).

**Sign-in:** `POST /api/login` with HTTP Basic returns the Keycloak token
(`services/api/app/routers/auth.py:104`). This needs no client secret. The bearer token is then
used for the builder, which accepts bearer only.

**Tests (~11, all GET except the login POST, none with side effects):**

| File | Check | Catches |
|---|---|---|
| `tests/test_public.py` | `GET /` returns the portal HTML | gateway/portal down |
| | `GET /api/health` → 200 `{"status":"healthy"}` | API down, `/api` prefix strip broken |
| | `GET /auth/realms/digitaltwins/.well-known/openid-configuration` → 200, `issuer == SMOKE_URL + "/auth/realms/digitaltwins"` | Keycloak down; `PLATFORM_DOMAIN`/protocol mismatch (tokens would fail every API check) |
| | `GET /jupyter/hub/api/health` → 200 | JupyterHub |
| | `GET /airflow/api/v2/monitor/health` → 200 | Airflow |
| | `GET /seek/` → 200 | SEEK |
| | `GET /fhir/metadata` → 200 | HAPI FHIR |
| | `GET /api/builder/workflow/` without a token → 401 | builder reachable via portal-frontend's nginx, and auth is enforced |
| `tests/test_signed_in.py` | `POST /api/login` (Basic) → 200 with `access_token` | Keycloak sign-in and the API's password grant |
| | `GET /api/verify_token` → `{"active": true}` | API's token verification against Keycloak |
| | `GET /api/dashboard/programmes` → 200 list | API reaching its DB/SEEK for a real user |
| | `GET /api/builder/workflow/` with the token → 200 list | builder's Keycloak verifier and DB |

All local probes above already answer as expected (checked read-only with curl today). Not
included: MinIO (its health port isn't routed through the gateway), Orthanc (gateway marks it
best-effort). Never call the side-effect GETs (`/api/dashboard/assay-launch`, downloads,
builder `/build`, `/approval`, `/execute`).

**Files:**
- `tests/conftest.py`: `base_url` fixture (`SMOKE_URL`, trailing slash stripped), an `httpx.Client`
  with a timeout and TLS verification on, a session-scoped `token` fixture that skips when
  `SMOKE_USERNAME`/`SMOKE_PASSWORD` are unset.
- `tests/test_public.py`, `tests/test_signed_in.py`, as above; parametrize the plain 200 probes.
- `tests/requirements.txt`: the two pins.
- `tests/README.md`: what it is, how to run it, the read-only rule, how to add a check.
- Delete `tests/.gitkeep`.
- `Makefile`: `smoke` target (+ `.PHONY`), and add `tests` to `lint-python`'s mount and paths.
- `.github/workflows/ci.yml` (added during implementation): a change under `tests/` sets `code=true`,
  so the `lint` job runs for it, now that lint covers `tests/`.

**Docs:**
- `docs/testing.md`: replace the "no end-to-end tests … empty placeholder" sentence (:37); add a
  short "Smoke tests" section (when, how, credentials, read-only rule).
- `docs/codemap.md:31`: describe `tests/` as the post-deploy smoke tests.
- `AGENTS.md` commands table: add `make smoke`. `README.md` testing paragraph: one line.
- `docs/future_refactoring.md`: remove "Repository layout" item 4 (no renumbering; the file
  keeps gaps). Nothing in it needs moving.
- ADR `docs/decisions/2026-11-18-post-deploy-smoke-tests.md` (draft below).
- Plan folder `docs/plans/2026-11-18-<HHMMSS>-smoke-tests/` with `plan.md` (this plan) and
  `tasks.md`, synced after every doc change; ticked as each step passes.

### ADR draft: post-deploy smoke tests live in the root `tests/`, run by hand

- **Context:** root `tests/` was an empty placeholder; the platform had no end-to-end checks.
- **Options:** (a) delete the folder; (b) Playwright browser tests in the portal frontend;
  (c) pytest HTTP smoke tests in root `tests/`, run by hand against a running stack;
  (d) run the full stack in CI for pre-merge end-to-end tests.
- **Decision:** (c). They cover every service through the gateway, are cheap, reuse the Makefile
  pattern, and work against any host. (b) tests one service's screens and fits its own folder
  later. (d) needs SEEK/Airflow/JupyterHub and secrets in CI: too heavy for now.
- **Consequences:** not run automatically, so someone must run them after each deploy; they must
  stay read-only because they target real data; credentials come from the caller's environment.

## Steps (TDD: the "code under test" is a deployment, so red = a broken target)

1. Plan folder + `tasks.md` → verify: synced into `docs/plans/`.
2. `tests/` files + `make smoke` → verify red first: `make smoke SMOKE_URL=http://localhost:9`
   fails every public test with a clear connection error; a wrong `SMOKE_PASSWORD` fails
   the login test with 401.
3. Green: `make smoke` against the local stack with real credentials → all pass; without
   credentials → public pass, signed-in skip with the reason shown.
4. Lint: `make lint` clean, including `tests/`.
5. Docs + ADR + debt item removal → `make docs-check` (after `git add`) passes.
6. Secret check: grep the diff for passwords/tokens; `make gitleaks` once committed (commit only
   when asked).

## Verification

- `make smoke` (local, credentials exported from the shell, never echoed): all ~12 pass.
- `make smoke` with no credentials: 8 pass, 4 skipped with the reason.
- Red runs from step 2 fail for the right reason.
- `make test` unchanged (smoke is not in it); `make lint` and `make docs-check` pass.
- Nothing rebuilt or restarted: no service code changes.
