# Tasks: Old names in code and comments

- [x] 0. Branch `refactor/old-names` from `main`; plan folder with `plan.md` and `tasks.md`
- [x] 1. Red: `services/api/tests/test_airflow_workflow.py` fails on the removed-path checks
- [x] 2. Green: remove `run()`, `core/workflow.py`, the `Workflow` export, `examples/run_workflow.py`, `AIRFLOW_VERSION`
- [x] 3. Reword the three comments (builder compose, compute-worker compose, example DAG)
- [x] 4. Docs: `codemap.md` airflow line; tick item 3 in `future_refactoring.md`
- [x] 5. Verify: `make test`, `make lint` (vs main), `make docs-check`, old-name grep
- [x] 6. Rebuilt the `api` image; the import smoke test passes. No local stack was running, so the container was not left up (see the session summary)
- [ ] 7. Ask before committing

## Part 2: follow-ups (2026-11-18)

- [x] 8. Red: token test runs without `AIRFLOW_API_URL` and fails
- [x] 9. Green: drop `AIRFLOW_API_URL` and `AIRFLOW_API_TOKEN` from the client, API compose and docs
- [x] 10. Portal deployment guide brought up to the current layout; portal README link text; override comment
- [x] 11. Release notes path `clinical-dashboard/frontend/` → `services/portal/frontend/`
- [x] 12. `future_refactoring.md` Resolved line updated
- [x] 13. Verify: make test, make lint, make docs-check pass; old-name grep clean (ADR history line left); `api` rebuilt and restarted on the running stack, live Airflow token + DAG list 200
- [ ] 14. Ask before committing
