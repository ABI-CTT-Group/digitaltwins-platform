# Tasks: fix sample-types for a dataset with no samples

- [x] Plan written and approved
- [x] Sync plans to docs/plans/
- [x] 1. Branch `fix/dataset-sample-types-empty` from `main`; plan folder with `plan.md` and `tasks.md`
- [x] 2. Red: unit tests in `services/api/tests/test_postgres_querier.py` fail
- [x] 3. Red: integration test fails against a throwaway Postgres
- [x] 4. Green: `get_dataset_sample_types` returns `[]` early and parameterises both queries; unit and integration tests pass
- [x] 5. Remove item 7 from `docs/future_refactoring.md`
- [x] 6. `make test-api`, `make lint`, `make docs-check` pass
- [ ] 7. Rebuild and restart the API container (skipped: no local stack running; commands given to the user)
- [x] 8. Add a debt item for the other `Querier` methods that format values into SQL
- [x] Sync plans to docs/plans/
