# Task: Harden and document the dataset import CLI

- [x] Create artifact folder with implementation plan
- [x] Sync artifacts to docs/artifacts/
- [x] Compare with legacy portal import_measurement.py (legacy_cli_comparison.md); extend plan (gaps 7–9)
- [x] Sync artifacts to docs/artifacts/
- [x] Red: write failing tests (categories, zip limit, sampleless warnings, retry hint, token refresh, --move zip, fhir.json, login errors, path check)
- [x] Green: implement CLI / keycloak_login / staging changes
- [x] Update wrapper script header comments
- [x] Update docs (import-dataset.md, api README, portal README, populating_data.md)
- [x] Sync artifacts to docs/artifacts/
- [x] Verify: make test-api, integration tests, make lint-python (no new findings)
- [x] Rebuild digitaltwins-api image (stack not running, so no restart)
- [x] Write walkthrough.md
- [x] ADR: docs/decisions/2026-10-19-import-cli-root-fhir-json.md
- [x] Sync artifacts to docs/artifacts/
- [x] Make category required: CLI, wrappers (prompt), REST sessions, UploadClient, example (tests first)
- [x] Update docs; ADR docs/decisions/2026-10-19-dataset-category-required.md
- [x] Verify: unit 298 passed, integration 213 passed, lint unchanged; image rebuilt
- [x] Sync artifacts to docs/artifacts/
