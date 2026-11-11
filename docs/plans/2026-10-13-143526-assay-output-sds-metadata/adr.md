# Build an assay output's manifest from the files it actually contains

- **Date:** 2026-10-13
- **Status:** Accepted

## Context

A script assay's output dataset (SDS) is created before its Airflow runs start, so its
`manifest.xlsx` has to name files that do not exist yet. It guesses fixed names
(`image.nrrd`, `breast_mri_rai.nii.gz`). The DICOM conversion tools now name their
output after the DICOM Series Description, so the guesses are usually wrong, and the
published dataset's manifest (MinIO and the Postgres `manifest` table) lists missing
files.

## Alternatives Considered

### Option A: Rebuild the manifest from the files when results are submitted
- Pros: Always matches what was produced, whatever tool or naming rule made it.
  One place to change. Works for any future workflow.
- Cons: The workspace draft keeps guessed names until submission.

### Option B: Make the tools write fixed file names again
- Pros: The guessed manifest becomes right with no API change.
- Cons: Undoes the deliberate switch to descriptive names. Couples the API to every
  tool's naming; each new tool needs a matching guess.

### Option C: Have each DAG report its output file names back to the API
- Pros: Exact names, known at run end.
- Cons: Needs a new callback or contract between every DAG and the API. Much more
  work for the same result as A.

## Decision

Option A. The submit step already downloads the whole output, so it can
list the real files and correct the manifest before publishing.

## Consequences

- Published manifests match their files.
- The manifest written at run time is only a draft.
- Datasets published before the fix keep their old manifests unless corrected by hand.
