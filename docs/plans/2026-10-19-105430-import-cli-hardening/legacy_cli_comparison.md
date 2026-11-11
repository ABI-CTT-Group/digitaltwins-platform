# Legacy `import_measurement.py` (portal, removed in PR97) vs current `digitaltwins.cli.import_dataset`

Legacy source: DigitalTWINS-Portal `backend/app/cli/import_measurement.py` at the PR97 base commit.

| Aspect | Legacy portal CLI | Current API CLI | Note |
|---|---|---|---|
| Runs in | `portal-backend` container (`uv run python -m app.cli.import_measurement`) | `digitaltwins-api` container (`python -m digitaltwins.cli.import_dataset`) | Wrappers otherwise identical: same staging + `pv`/`docker cp` logic. The API wrapper finds the container by compose label and passes `--move`. |
| Categories | measurements only | measurements, models, tools, workflows | |
| Pipeline | portal service layer: DB row + annotation → `run_measurement_approval` (MinIO + FHIR) | upload session → `jobs.run_commit_and_push` (same as `POST /datasets/uploads`) | Matches the current REST/portal path. |
| Who may import | `admin` only | `admin` or `researcher` | Same as the REST `require_upload_role`. |
| **Pre-annotated `fhir.json` at dataset root** | validated against the dataset (`validate_fhir_matches_dataset`) and used as the annotation | **not supported**; a root `fhir.json` is uploaded as an ordinary file | Regression. |
| **FHIR push default** | always pushed (auto pre-annotation when there is no `fhir.json`) | `--fhir none` by default; `--fhir auto` to push | Behaviour change. |
| Name uniqueness | fails on a name clash | names need not be unique (datasets keyed by UUID) | Intentional. |
| Placeholder IDs | `reset_placeholder_ids` | platform UUIDs stamped at commit | Equivalent. |
| Local copy after success | deleted (input + extraction) | kept as the FHIR build cache; removed after a successful FHIR push or 7 days | Documented. |
| Input zip with `--move` | deleted on success | left in `import-staging/` | Fixed by plan gap #6. |
| Zip size limit | `MAX_UPLOAD_MB` (20 GiB) | 5 GiB hard default | Fixed by plan gap #2. |
| Login errors other than "no role" | caught → exit 1 "Login failed: …" | only `PermissionError` caught; network/timeout errors give a traceback | Gap. |
| Missing path | checked **before** sign-in | checked **after** sign-in | Minor UX gap. |
| Exit codes | 0 ok / 1 user error / 2 pipeline failure | 0 ok / 1 commit or FHIR failed / 2 invalid / 3 not authorised | Changed; documented in `services/api/docs/import-dataset.md`. |
