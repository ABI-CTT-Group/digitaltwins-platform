# Tasks: require every platform secret in the compose files

- [x] PR #411 merged; branch `fix/require-compose-secrets` created from `origin/main`
- [x] Plan synced to docs/plans/
- [x] 0. Baseline `docker compose config --hash "*"` recorded (27 services, scratchpad only)
- [x] 1. Red: `util/tests/test_secrets_required.sh` + Makefile mounts; `make test-util` fails with 40 offenders
- [x] 2. Green: compose files use `${VAR:?...}`; `make test-util` passes
- [x] 3. Config hashes identical to baseline; Compose fails without `.env`
- [x] 4. Docs: codemap playbook, portal README, future_refactoring, ADR; `make docs-check` passes
- [x] 5. `make test`, `make lint` (vs `main`), `make gitleaks`, plan-folder gitleaks; no secret values written
- [x] 6. Plan synced, Outcome section if anything differed
- [x] Sync plans to docs/plans/
