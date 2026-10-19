# Plan: Harden and document the dataset import CLI (measurements, models, tools, workflows)

## Context

Portal PR97 removed the portal's legacy measurement import CLI (`backend/app/cli/import_measurement.py`, `keycloak_login.py`, `scripts/import-dataset.*`). That CLI was **already ported** into digitaltwins-api on 2026-09-28 (commit 39a52775). It is on `main`:

- `services/api/src/digitaltwins/cli/import_dataset.py` and `keycloak_login.py`
- the host wrappers `services/api/scripts/import-dataset.{sh,command,ps1,bat}`
- the docs page `services/api/docs/import-dataset.md`

It runs the same session pipeline as `POST /datasets/uploads` (`sessions.create_session` → `jobs.run_commit_and_push`), and later commits extended it to models, tools and workflows. The function signatures still match the current REST path.

So nothing needs restoring. What's left is **drift and gaps compared with the REST upload path**, plus **stale or missing docs**. The user chose: harden and document, keep the in-container design, and leave Keycloak's device flow off (password fallback).

## Gaps to close (CLI compared with REST `app/routers/dataset_uploads.py`)

| # | Gap | REST behaviour | Fix |
|---|---|---|---|
| 1 | `--category` is free text (`import_dataset.py:46`). An unknown value goes through SPARC validation and is used as the MinIO bucket name. | 400 unless the category is measurements, models, tools or workflows (`dataset_uploads.py:148-153`) | Add a module constant `MEASUREMENTS = "measurements"`. In `main`, check `args.category in {MEASUREMENTS, models.CATEGORY, tools.CATEGORY, workflows.CATEGORY}` and exit 2 otherwise. The check runs at call time, so tests can monkeypatch it the way they already patch `dataset_uploads.INGEST_CATEGORIES`. |
| 2 | The zip limit is the 5 GiB default in `extract_uploaded_archive`. | `MAX_UPLOAD_MB`, default 20 GiB (`_max_upload_bytes`, `dataset_uploads.py:61-66`, used at :231) | Move `_max_upload_bytes` into `digitaltwins/measurements/staging.py` as `max_upload_bytes()`. The router imports it from there, and the CLI passes `max_total_bytes=max_upload_bytes()`. |
| 3 | Subjects with no sample folders are skipped silently. | finalize returns `sampleless_subjects()` warnings (:272) | For measurements, print each `sampleless_subjects(root)` warning (`measurements/validation.py:82`) as `  ! …` after validation. |
| 4 | A failed commit prints no retry path. | the session stays `failed` and can be retried with `POST /datasets/uploads/{id}/approve` | Add that retry hint to the exit-1 commit-failure message. |
| 5 | The token can expire before it is used. The access token lifespan is 300 s (realm template). Login happens first, then extraction, copy and commit. Tools and workflows register in SEEK with that token, and `is_admin(token)` re-verifies it, which raises once the token has expired. | the portal relays a fresh token | `keycloak_login.login()` also returns the `refresh_token`. A new `refresh(refresh_token) -> access_token` uses the refresh-token grant through the existing `_post_form`. The CLI refreshes just before `run_commit_and_push`. If the refresh fails, it marks the session `failed` ("sign-in expired; retry from the portal or with POST …/approve") and exits 3. |
| 6 | `--move` on a `.zip` leaves the copied zip in `/dataset_staging/import-staging/` until a dataset with the same name is imported again. | n/a | With `--move` and a zip input, delete the source zip after it is extracted. This matches what `--move` already means. |

### Added after comparing with the legacy portal CLI (user decision, see `legacy_cli_comparison.md`)

| # | Gap | Fix |
|---|---|---|
| 7 | The legacy CLI used a pre-annotated `fhir.json` at the dataset root; the current CLI uploads it as an ordinary file. | Measurements only: if `<root>/fhir.json` exists, load it, check it with `check_descriptions_match` (as REST finalize does), and create the session with `fhir_mode="descriptions"` and `fhir_descriptions=<it>`. Bad JSON or a mismatch exits 2 with no session. The file is removed from the staged copy (never from the user's source), so it isn't published as data. It takes precedence over `--fhir`. |
| 8 | Sign-in errors other than "no upload role" (network, timeout, Keycloak errors) give a traceback. | Catch them: exit 3 with `Login failed: …`. |
| 9 | A missing path is reported only after sign-in. | Check that the path exists before signing in. |

The default stays `--fhir none` (same as REST/UploadClient); the docs note that the legacy CLI always pushed.

Out of scope (user decision): an explicit `--fhir-descriptions` flag, `--commit-mode on_approve`, a host-side HTTP CLI, enabling the device flow.

## Implementation (TDD: red → green per gap)

0. **Artifacts first.** Create `docs/artifacts/2026-10-19-<HHMMSS>-import-cli-hardening/`, copy this plan in as `implementation_plan.md`, add `task.md` with a "Sync artifacts" item after every doc step, and run the gitleaks check. Use repo-relative paths only, with no local ops details.
1. **Tests first:** `services/api/tests/test_import_dataset_cli.py`
   - Unit: `refresh()` posts `grant_type=refresh_token` and returns the access token, with `_post_form` monkeypatched as the existing `device_login` test does. `login()` returns a 3-tuple. The password-fallback test is updated to match.
   - Integration (`cli_env`): change the `login` stub to return `("alice", "t", "r")` and stub `import_dataset.refresh` to return `"t2"`. Patch `import_dataset.MEASUREMENTS` to the bucket, and drop `--category bucket` from the measurement tests.
   - New tests:
     - an unknown `--category` exits 2 with no session created;
     - a zip larger than `MAX_UPLOAD_MB` exits 2 (set the env var to a tiny value);
     - a sampleless subject prints its warning (build the fixture as `test_dataset_uploads_api.py` does for its warnings test);
     - a failed commit (monkeypatch the commit to raise) exits 1 and mentions `/approve`;
     - the tools import registers in SEEK with the **refreshed** token `"t2"`;
     - when `refresh` raises, the session ends up `failed` and the CLI exits 3;
     - `--move` on a zip removes the zip.
2. **Code:** `cli/import_dataset.py`, `cli/keycloak_login.py`, `measurements/staging.py` (gains `max_upload_bytes`), `app/routers/dataset_uploads.py` (imports it instead of defining `_max_upload_bytes`). Update the module docstring's flow description.
3. **Wrappers** `services/api/scripts/import-dataset.*`: change the header comments from "measurement dataset import" to "dataset import (measurements, models, tools, workflows)", add one example per category, and note that double-click mode only does measurements. No logic changes.
4. **Docs**, then sync artifacts:
   - `services/api/docs/import-dataset.md`:
     - generic title, and a per-category table (layout required, required flags, what the commit does: SEEK for tools and workflows, DAG deploy for an admin's script workflow, `--name` becomes the SEEK title);
     - a complete Options synopsis;
     - wrapper paths given as `services/api/scripts/`;
     - the prerequisite reworded: the device flow is optional and password sign-in is the stock behaviour;
     - exit codes made generic, plus the new retry hints.
   - `services/api/README.md` (lines ~163, 193, 246): "Inside the API container: `scripts/import-dataset.sh`" becomes "From the host: `services/api/scripts/import-dataset.sh`". Add a CLI pointer to the measurement section (~136-151).
   - `services/portal/README.md:112-118`: fix the non-existent `services/api/digitaltwins-api/...` paths and make the section title generic.
   - `docs/populating_data.md:60-65`: replace the "[todo. add details]" with a short pointer to the CLI and `UploadClient`.
   - Noted but not changed: the stale `keycloak_login` mention in `services/portal/backend/app/cli/__init__.py:5`. I'll flag it to the user.
5. **ADR:** none. The scope choice was the user's call, and refreshing the token rather than moving the login step is a minor implementation detail. Check this again at task end.

## Verification

- `make test-api`: the unit suite must stay green (baseline 287 passed) and include the new unit tests.
- Run the CLI integration tests with the throwaway-container recipe (`--network digitaltwins-platform`, `pytest -m integration tests/test_import_dataset_cli.py tests/test_dataset_uploads_api.py tests/test_upload_client.py`). The REST tests are included because `_max_upload_bytes` moved.
- `make lint`, `make gitleaks`.
- Rebuild and restart the API: `docker compose up -d --build digitaltwins-api` (repo root).
- Manual smoke test (ask the user before writing to the live stack): `services/api/scripts/import-dataset.sh <example measurement dataset> --password`. Expect exit 0, the dataset shown as completed in the portal, and a warning line for any sampleless subject.
- Before handing over, sync the final `walkthrough.md` to the artifact folder, with no secrets or local paths.

## Addendum (2026-10-19): category is required everywhere (user decision)

- **CLI:** `--category` has no default; a missing one exits 2 before sign-in. The wrappers prompt for it (and a tool's or workflow's type and SEEK project) when it isn't passed. The prompt comes before the copy, which covers double-click, drag-and-drop and interactive terminal use.
- **REST `POST /datasets/uploads`:** `SessionCreate.category` has no default; a missing one returns 422. This matches the one-shot `POST /datasets`.
- **`UploadClient.upload_dataset(path, category, ...)`:** `category` is required.
- **`examples/upload_measurement_dataset.py`:** `--category` is required.
- All in-repo callers (portal measurement upload, portal tool handoff, tests) already send a category. This is a **breaking change for external API clients**, so the commit is marked `feat!` and the docs note it.
- Tests first: CLI unit test (missing category → 2, no sign-in); REST integration test (missing category → 422); `UploadClient` test (missing category → `TypeError`); example test (missing `--category` → argparse exit 2).
