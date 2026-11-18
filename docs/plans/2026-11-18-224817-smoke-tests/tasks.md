# Tasks: post-deploy smoke tests

- [x] 0. Branch `test/post-deploy-smoke-tests` off `main`; plan in this folder
- [x] Sync plans to docs/plans/
- [x] 1. `tests/` files (`conftest.py`, `test_public.py`, `test_signed_in.py`, `requirements.txt`) and `make smoke`
- [x] 2. Red: unreachable `SMOKE_URL` fails every test with a connection error; a wrong password fails the login test with 401
- [x] 3. Green: local stack with credentials, all pass; without credentials, public pass and signed-in skip with the reason
- [x] 4. `make lint` clean, `tests/` included
- [x] 5. Docs: `tests/README.md`, `docs/testing.md`, `docs/codemap.md`, `AGENTS.md`, `README.md`; remove debt item 4
- [x] 5a. CI lint filter covers `tests/` (`.github/workflows/ci.yml`, `docs/testing.md`); added to the plan
- [x] 6. ADR `docs/decisions/2026-11-18-post-deploy-smoke-tests.md`
- [x] Sync plans to docs/plans/
- [x] 7. Verify: `make docs-check` 0 problems; `make test` (api 422, builder 260, frontend 374, hub 5, util) all pass; gitleaks dir scan of changed files and a diff grep found no secrets
- [x] 8. `tests/README.md`: first run, `PYTEST_ARGS`, where to run, clearing credentials, a non-admin account (checked: all 12 pass as `test1`), and a failure guide
- [x] Sync plans to docs/plans/
