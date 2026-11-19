# Fix SQL injection in the API's Postgres access

## Context

Debt item "REST API 7" in `docs/future_refactoring.md`: `services/api/src/digitaltwins/postgres/querier.py`
formats request values into SQL. It is reachable by any signed-in user, e.g.
`GET /datasets?categories=x')+OR+('1'='1` (`get_datasets`), `GET /datasets/{dataset_uuid}`
(`get_dataset`) and `GET /datasets/{uuid}/samples?sample_type=…` (`get_dataset_samples`). The API
connects as `POSTGRES_USER`, the database superuser, so injected SQL can do anything.

A repo-wide search for the same pattern (SQL built with `.format()`, f-strings or `+`) found two
more places, and nothing else (builder, airflow, jupyterhub and util only interpolate constant
table or schema names):
- `services/api/src/digitaltwins/metadata/querier.py`: an older copy of the querier with the same
  injection. Nothing imports it (one commented-out line in `digitaltwins/__init__.py`).
- `services/api/src/digitaltwins/core/uploader.py`: INSERT column names come from uploaded
  spreadsheet headers (unmapped headers are only lower-cased, with spaces and hyphens turned into
  `_`). Values are already parameters, but a crafted header such as `x)values(1);drop/**/table…`
  injects SQL. Needs the upload role; the spreadsheets come from outside the platform team.

Decisions (from your answers): delete `metadata/querier.py`; delete `get_samples` and
`get_workflow` from `postgres/querier.py` (they query `subject_sample` and `workflow`, tables that
don't exist, and nothing calls them); parameterise the other eight; in the uploader, reject column
names that aren't plain identifiers (safe whatever the spreadsheet contains).

## Approach

1. Branch `fix/postgres-sql-injection`, stacked on `fix/dataset-sample-types-empty` (it builds on
   that branch's tests and debt item). Plan folder `docs/plans/2026-11-19-<HHMMSS>-postgres-sql-injection/`
   with `plan.md` and `tasks.md`, synced and ticked per step.
2. **Red: unit tests** in `services/api/tests/test_postgres_querier.py`, reusing its `_querier`
   recorder. For each of `get_datasets` (categories), `get_dataset`, `get_dataset_uuid_by_seek_id`,
   `get_dataset_descriptions`, `get_subjects`, `get_subject_by_sample`, `get_sample`,
   `get_dataset_samples`: the value goes in `values`, never in the SQL text. Also
   `get_datasets(categories=[])` still queries every dataset with no values. Run → red.
3. **Red: integration tests** (`@pytest.mark.integration`, `platform_db`), one per method, on a
   seeded dataset (dataset with `seek_id`, `dataset_description`, subject, two samples,
   `dataset_mapping`). Plus injection checks that pass only after the fix:
   `get_datasets(categories=["x') OR ('1'='1"])` returns `[]` (today: every dataset), and
   `get_dataset_descriptions("<uuid>' OR '1'='1")` raises `psycopg2.DataError` instead of
   returning every row. Run against a throwaway `postgres:16` → red.
4. **Green**: rewrite the eight methods to `_query(sql, values)` with `%s`; categories as
   `IN %s` with `tuple(categories)`. Delete `get_samples` and `get_workflow`. Behaviour is
   otherwise unchanged (e.g. `get_dataset` still indexes `[0]`, a non-UUID still raises).
5. **Uploader, red then green**: unit tests that `_insert_metadata_rows`, `_insert_subject` and
   `_insert_sample` raise `ValueError` and execute nothing for a column like `x) VALUES (1); --`,
   and that every column in `resources/version_2_0_0/element_mapping.xlsx` passes the check. Then
   add one helper `_column_list(columns)` in `core/uploader.py` that checks each name against
   `^[A-Za-z_][A-Za-z0-9_]*$` and returns the joined string; use it at the four `col_str` sites.
   A name failing the check would already fail today (no schema column has other characters), so
   no upload that works now breaks; the ValueError rolls back like today's SQL error.
6. **Delete** `services/api/src/digitaltwins/metadata/` and the commented
   `# from .metadata.querier import Querier` line in `digitaltwins/__init__.py`.
7. **Docs**: remove item 7 from `docs/future_refactoring.md` (no guidance to move); check
   `docs/codemap.md` and `services/api/README.md` for mentions of `metadata/`.
8. Verify (below), sync plan, report. No commit until you ask.

No ADR: these are routine security fixes; the two deletions are of unused, broken code.

## Critical files

- `services/api/src/digitaltwins/postgres/querier.py`
- `services/api/src/digitaltwins/core/uploader.py`
- `services/api/src/digitaltwins/metadata/querier.py` (deleted), `services/api/src/digitaltwins/__init__.py`
- `services/api/tests/test_postgres_querier.py`, new `services/api/tests/test_uploader_columns.py`
- `docs/future_refactoring.md`

## Verification

- `make test-api`, `make lint`, `make docs-check`.
- By hand against throwaway `postgres:16` and MinIO containers (labelled, removed with
  `docker rm -f -v` afterwards): `-m integration -k "postgres_querier or upload_measurement_example"`.
  The measurement-upload test runs real SDS spreadsheets through the uploader, so it shows the
  column check doesn't reject valid headers.
- Grep again for formatted SQL in `services/` and `util/`: only constant identifiers left.
- Docker: no local stack is running, so give `docker compose build api && docker compose up -d api`.
  Airflow DAGs use the pinned PyPI `digitaltwins`, so they don't get this until that pin moves.

## Outcome

- Done as planned. Before the fix, the integration tests showed the injection: a crafted category
  returned every dataset, a crafted UUID returned rows instead of raising, and crafted text in
  `seek_id` and `sample_type` broke the SQL. All pass after it.
- The removed debt item's SQL advice (`IN %s` with a tuple, column names through `_column_list`)
  moved to `services/api/AGENTS.md`, since it stays true after the fix.
- `digitaltwins/__init__.py` also lost two commented imports of `metadata.uploader` and
  `metadata.exporter`, which pointed into the deleted package.
- `make test-api`: 446 passed, 1 skipped, 224 deselected. `make lint` and `make docs-check` pass.
  All 224 API integration tests pass against throwaway Postgres and MinIO, including the
  measurement uploads that run real SDS spreadsheets through the uploader.
- Formatted SQL left in `services/` and `util/` only interpolates table or column names: constants,
  the allowlist in `measurements/sessions.py`, and uploader columns checked by `_column_list`.
- No local stack was running, so the API container wasn't rebuilt; run
  `docker compose build api && docker compose up -d api` on a host running the stack.
