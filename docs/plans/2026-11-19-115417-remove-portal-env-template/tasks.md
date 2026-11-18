# Tasks: remove the stale env template in services/portal/

- [x] Create branch `chore/remove-stale-portal-env-template` from `origin/main`
- [x] Write plan.md and tasks.md in docs/plans/
- [x] 1. `git rm services/portal/.env.template`; `git grep` finds no other references
- [x] 2. Fix the `minio` comment in `services/portal/docker-compose.yml`
- [x] 3. Portal README gotcha: the standalone stack needs `PROJECT_NAME` passed on the command line (it has no `.env`)
- [x] 4. Remove the debt item; `make docs-check` and `docker compose config -q` pass
- [x] 5. Sync plans to docs/plans/
