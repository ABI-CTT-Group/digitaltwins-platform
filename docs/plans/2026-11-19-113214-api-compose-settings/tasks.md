# Tasks: API compose settings cleanup

- [x] Create branch `refactor/api-compose-settings` from `origin/main`
- [x] Sync plans to docs/plans/
- [x] 1. Red: `services/api/tests/test_compose.py` fails all three tests
- [x] 2. Green: compose change; the three tests pass; `docker compose config api` shows it
- [x] 3. Remove `_coerce_value`; `grep` finds nothing
- [x] 4. Docs (API README, `.env.template`, `docs/production.md`, `util/sync-runtime.sh`, `docs/future_refactoring.md`); `make docs-check` passes
- [x] 5. `make test`, `make lint` (compared against `main`), `make gitleaks` pass
- [ ] 6. Live check: rebuild and restart `api` only; `printenv`; `/api/docs` returns 200 (not run; see Outcome in plan.md)
- [x] 7. Plan synced, with an Outcome section if anything differed from the plan
- [x] Sync plans to docs/plans/
- [x] Follow-up: reword `docs/production.md` `KEYCLOAK_VERIFY_SSL` item; add debt item for `services/portal/.env.template`
- [x] Sync plans to docs/plans/
