# Walkthrough: Harden and document the dataset import CLI

## Summary

The legacy portal measurement importer (removed in DigitalTWINS-Portal PR97) had already been ported to digitaltwins-api as `python -m digitaltwins.cli.import_dataset`, with host wrappers in `services/api/scripts/import-dataset.*`, and later extended to models, tools and workflows. This change closes the gaps between the CLI and the REST upload path and the legacy importer (see `legacy_cli_comparison.md`), and fixes the docs.

## Changes

### CLI (`services/api/src/digitaltwins/cli/`)
- `import_dataset.py`
  - Option checks run **before sign-in**: missing path, unknown `--category` (now limited to measurements, models, tools and workflows), missing tool/workflow options → exit 2.
  - Sign-in errors other than a missing role (Keycloak unreachable, timeout) → exit 3 `Login failed: …`, not a traceback.
  - Zips are extracted with the REST limit `MAX_UPLOAD_MB` (20 GiB by default) instead of a 5 GiB hard default.
  - Measurements: prints a `!` warning for each `primary/<subject>` with no sample folders.
  - Measurements: a root `fhir.json` is checked with `check_descriptions_match` and used as the annotation (`fhir_mode=descriptions`); it is removed from the staged copy. A mismatch or bad JSON → exit 2, no session. See ADR `docs/decisions/2026-10-19-import-cli-root-fhir-json.md`.
  - `--move` on a zip deletes the staged zip once its contents are in the dataset dir.
  - The access token is refreshed just before the commit. If the refresh fails, the session is marked `failed` (stage `auth`) and the CLI exits 3 with the `/approve` retry call.
  - A failed commit prints the `POST /datasets/uploads/{id}/approve` retry call.
- `keycloak_login.py`: `device_login` / `password_login` / `login` also return the refresh token; new `refresh(refresh_token)`.

### Shared
- `measurements/staging.py`: new `max_upload_bytes()`, moved from `app/routers/dataset_uploads.py`; both routers (`dataset_uploads.py`, `datasets.py`) import it.

### Wrappers and docs
- `services/api/scripts/import-dataset.*`: header comments cover all four categories; double-click mode is measurements-only. No logic changes.
- `services/api/docs/import-dataset.md`:
  - rewritten for all categories, with a per-category table;
  - covers the `fhir.json` support, sampleless warnings, the full options synopsis, exit codes with retry calls, and correct `services/api/scripts/` paths;
  - the device flow is now described as optional (off in the stock realm, so password sign-in is the default).
- `services/api/README.md`: the CLI pointers say "from a terminal on the server: `services/api/scripts/...`" (previously "inside the API container"); added a pointer in the measurement section.
- `services/portal/README.md`: fixed the non-existent `services/api/digitaltwins-api/...` paths.
- `docs/populating_data.md`: replaced the API "[todo]" with the CLI and `UploadClient` pointers.

### Category is required (addendum, user decision)
- CLI: `--category` has no default; missing → exit 2 before sign-in.
- Wrappers (`.sh`, `.command`, `.ps1`/`.bat`): without `--category`, ask for it before the copy, plus `--tool-type`/`--workflow-type` and `--seek-project-id` for tools and workflows. Covers double-click and drag-and-drop.
- REST `POST /datasets/uploads`: `SessionCreate.category` has no default (`422` without it). `UploadClient.upload_dataset(path, category, ...)`: required. `examples/upload_measurement_dataset.py`: `--category` required.
- Breaking for external API clients; ADR `docs/decisions/2026-10-19-dataset-category-required.md`. The API README notes it.
- Docs, example usage and a frontend type comment (`measurement_api.ts`) updated.

## Verification

- `make test-api`: 298 passed, 1 skipped (includes the new `refresh` and required-category unit tests).
- API integration suite (`-m integration tests/`) against throwaway Postgres and MinIO containers: 213 passed. This includes 26 CLI integration tests (10 new), the REST upload (including the new missing-category `422`), one-shot and `UploadClient` tests.
- Wrapper prompts (`.sh`, `.command`) checked with a stub `docker` for: tools prompted, `--category` given, no arguments, `--category=x`, and workflows prompted. `.ps1` not run (no PowerShell on the dev host).
- Tests were written first and failed before the implementation (red → green).
- `make lint-python`: 154 findings both before and after the change (pre-existing; report-only in CI); none new.
- `digitaltwins-api` image rebuilt; `python -m digitaltwins.cli.import_dataset --help` runs in it.

## Not changed (noted)
- `services/portal/backend/app/cli/__init__.py:5` still mentions the removed `keycloak_login` module.
- `docs/populating_data.md`: the "portal" bullet still says "[todo. future implementation]", though the portal Upload → Measurements page exists.
