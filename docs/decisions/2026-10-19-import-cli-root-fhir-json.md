# Import CLI picks up a measurement dataset's root fhir.json as its annotation

- **Date:** 2026-10-19
- **Status:** Accepted

## Context

The portal's legacy measurement importer (`backend/app/cli/import_measurement.py`, removed in DigitalTWINS-Portal PR97) looked for a pre-annotated `fhir.json` at the dataset root. It checked the file against the dataset and pushed it to FHIR. The replacement in digitaltwins-api (`python -m digitaltwins.cli.import_dataset`) only offered `--fhir none|auto`, so a root `fhir.json` was uploaded as an ordinary data file and the hand-made annotation was lost. The REST API and `UploadClient` already accept an annotation as `fhir_descriptions` (`fhir_mode=descriptions`).

## Alternatives Considered

### Option A: Auto-detect `<root>/fhir.json` (measurements only)
- Pros: same behaviour as the legacy importer, so existing prepared datasets import unchanged; no new option to learn.
- Cons: `fhir.json` at the root of a measurement dataset becomes a reserved name: it is used as the annotation (overriding `--fhir`) and is not stored as data.

### Option B: Explicit `--fhir-descriptions FILE` for every category
- Pros: explicit; matches `UploadClient`'s `fhir_descriptions`; works for models, tools and workflows too.
- Cons: datasets prepared for the legacy importer need an extra flag; a root `fhir.json` would still be published silently as data unless separately handled.

### Option C: No annotation input; annotate in the portal afterwards
- Pros: no CLI change.
- Cons: a regression from the legacy importer for batch imports of annotated datasets.

## Decision

Option A. The goal was to restore the legacy CLI's measurement behaviour on top of the current upload-session pipeline. The file is checked with the same `check_descriptions_match` the REST finalize uses, passed as `fhir_descriptions`, and removed from the staged copy (never from the user's source). An invalid or mismatching file exits 2 before any session is created.

## Consequences

- Prepared measurement datasets with a root `fhir.json` import with their annotation, as with the legacy importer.
- A measurement dataset can't ship a data file named `fhir.json` at its root through the CLI. The platform already writes the pushed bundle to `<dataset_uuid>/fhir.json` in MinIO, so such a file would have been overwritten anyway.
- Models, tools and workflows still have no CLI annotation input. Option B can be added later if it is needed; it doesn't conflict with this decision.
- The `--fhir` default stays `none` (same as REST and `UploadClient`), unlike the legacy importer, which always pushed.
