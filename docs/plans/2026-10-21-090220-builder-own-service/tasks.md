# Tasks: the builder in its own service folder, services/builder

Plan: [implementation_plan.md](implementation_plan.md)

- [x] Sync the plan to `docs/artifacts/`
- [ ] Sync artifacts to `docs/artifacts/` after every task-list or plan change
- [x] 1 Move with `git mv`: `app/`, `tests/`, `docker-compose.yml`, `README.md`, `requirements.txt` into `services/builder`
- [x] 2 Imports `builder.` → `app.`, `builder_tests.` → `tests.`; test path constants
- [x] 3 Separation tests: compose checks only, in `services/builder/tests`
- [x] 4 Remove the test runtime leftovers in `services/api`
- [x] 5 Restore the API: Dockerfile, compose target, `requirements-test.txt`, `.gitignore`, README pointer
- [x] 6 Root compose extends `./services/builder/docker-compose.yml`
- [x] 7 Makefile: `test-builder`; `test-api` mounts back to the originals; `lint-python`
- [x] 8 CI: "builder unit tests" job and filter; `api` filter restored
- [x] 9 Docs and code comments; rename gate
- [x] 10 ADR `2026-10-21-builder-as-its-own-service`; status line on the merge ADR
- [x] 11 Walkthrough; sync artifacts
- [x] Verify: `make test`, lint, gitleaks, build images, `compose config` (key names only), live matrix
- [x] Commits: `refactor(builder)!: move the builder into its own service folder, services/builder` + `docs: record the builder's move to services/builder`
