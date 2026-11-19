# Fix `GET /datasets/{uuid}/sample-types` for a dataset with no samples

## Context

Debt item "REST API 7" in `docs/future_refactoring.md`. `Querier.get_dataset_sample_types`
(`services/api/src/digitaltwins/postgres/querier.py:182`) joins the dataset's sample UUIDs into
`... WHERE sample_uuid IN ()` when the dataset has no rows in `dataset_mapping`. Postgres rejects
the empty list, so the endpoint (`app/routers/datasets.py:133`, also `dashboard.py:227`) returns
500 instead of `[]`. Both queries also build SQL by string formatting (`dataset_uuid`, then the
sample UUIDs). Outcome: empty dataset → `[]`; both queries parameterised; item removed from the
debt list.

Scope: only `get_dataset_sample_types`. The other methods in that file also format values into
SQL; that's out of scope (not listed in the item) and I'll mention it rather than change it.

## Approach

1. Branch `fix/dataset-sample-types-empty` from `main`. Plan folder
   `docs/plans/2026-11-19-<HHMMSS>-dataset-sample-types-empty/` with `plan.md` + `tasks.md`
   (synced immediately, ticked per step).
2. **Red — unit tests**, new `services/api/tests/test_postgres_querier.py` (no DB; build a
   `Querier` with `object.__new__` and replace `_query` with a recorder returning canned rows):
   - no samples → returns `[]` and issues only the first query;
   - with samples → first call is `... WHERE dataset_uuid = %s` with `(dataset_uuid,)`, second is
     `... WHERE sample_uuid IN %s` with `(tuple(sample_uuids),)`; no UUID appears in either SQL
     string; returns distinct non-empty types in first-seen order (current behaviour).
   Run `make test-api PYTEST_ARGS="-k postgres_querier"` → expect failures.
3. **Red — integration test** in the same file, `@pytest.mark.integration`, using `platform_db`:
   an unknown dataset UUID → `[]`; a dataset with two mapped samples (types `a`, `b`, plus a
   duplicate) → `["a", "b"]`. This checks the real SQL, in particular that the parameterised
   UUIDs compare correctly against the `uuid` columns. Insert only the rows the schema needs.
4. **Green** — rewrite the method:
   ```python
   sql = "SELECT DISTINCT sample_uuid FROM dataset_mapping WHERE dataset_uuid = %s"
   sample_uuids = [row["sample_uuid"] for row in self._query(sql, (dataset_uuid,))]
   if not sample_uuids:
       return []
   sql = "SELECT sample_type FROM sample WHERE sample_uuid IN %s"
   resp = self._query(sql, (tuple(sample_uuids),))
   ... (dedupe loop unchanged)
   ```
   `IN %s` with a tuple (psycopg2 expands it to `('…', '…')`, untyped literals that coerce to
   `uuid`) rather than `= ANY(%s)` with a list, which would send `text[]` and fail `uuid = text`.
5. Remove item 7 from `docs/future_refactoring.md` (no lasting guidance to move).
6. Verify (below), then report. No commit until you ask.

## Critical files

- `services/api/src/digitaltwins/postgres/querier.py` — the fix (reuse existing `_query(sql, values)`)
- `services/api/tests/test_postgres_querier.py` — new tests
- `docs/future_refactoring.md` — remove item 7
- `docs/plans/<ts>-dataset-sample-types-empty/{plan,tasks}.md`

## Verification

- `make test-api` — full unit suite passes (new tests included).
- Integration test by hand: throwaway `postgres:16` on its own labelled network, PY311 image with
  `.cache/ci/api/venv`, mounting `services/api` and `services/postgres` as the Makefile does,
  `-m integration -k postgres_querier`; then `docker rm -f -v` the containers by label.
- `make lint`, `make docs-check`.
- Docker: the API image bakes in `src/`, so after the change rebuild and restart only the API:
  `docker compose build api && docker compose up -d api`. (Note: Airflow DAGs use the pinned PyPI
  `digitaltwins` release, so they don't see this fix until the pin moves.)

## Outcome

- Done as planned. The integration test failed before the fix with the expected
  `syntax error at or near ")"` on `IN ()`, and passes after it.
- `make test-api`: 427 passed, 1 skipped, 216 deselected. `make lint` and `make docs-check` pass.
- No local stack was running, so the API container wasn't rebuilt; run
  `docker compose build api && docker compose up -d api` on a host running the stack.
- Follow-up: added debt item "REST API 7. Postgres `Querier` formats values into SQL strings" to
  `docs/future_refactoring.md` for the other methods in `querier.py` (out of scope here).
