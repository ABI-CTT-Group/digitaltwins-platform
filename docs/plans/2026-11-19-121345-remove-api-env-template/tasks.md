# Tasks: remove the stale env template in services/api/

- [x] Create branch `chore/remove-stale-api-env-template` from `origin/main`
- [x] Write plan.md and tasks.md in docs/plans/
- [x] 1. `git rm services/api/.env.template`; `git grep` finds only codemap and plans
- [x] 2. Remove the row from `docs/codemap.md`
- [x] 3. Note the removed copy in `docs/production.md` (Secrets handling)
- [x] 4. `make docs-check`, `docker compose config -q`, `make test-api` and gitleaks pass; no secret values in the plan or commits
- [x] Record the PACS compose fallback secret in `docs/future_refactoring.md`
- [x] 5. Sync plans to docs/plans/
