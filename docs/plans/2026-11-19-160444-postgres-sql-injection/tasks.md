# Tasks: fix SQL injection in the API's Postgres access

- [x] Plan written and approved
- [x] Sync plans to docs/plans/
- [x] 1. Branch `fix/postgres-sql-injection` (stacked on `fix/dataset-sample-types-empty`); plan folder with `plan.md` and `tasks.md`
- [x] 2. Red: querier unit tests fail
- [x] 3. Red: querier integration tests (per method, plus injection checks) fail against a throwaway Postgres
- [x] 4. Green: eight methods parameterised, `get_samples` and `get_workflow` deleted; unit and integration tests pass
- [x] 5a. Red: uploader column-name tests fail
- [x] 5b. Green: `_column_list` check used at the four INSERT sites; uploader tests pass
- [x] 6. Delete `digitaltwins/metadata/` and its commented import
- [x] 7. Remove item 7 from `docs/future_refactoring.md` (its SQL guidance moved to `services/api/AGENTS.md`); no stale mentions of `metadata/`
- [x] 8. `make test-api`, `make lint`, `make docs-check`; integration tests incl. measurement upload; formatted-SQL grep clean
- [x] Sync plans to docs/plans/
