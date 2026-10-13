# Assay output SDS metadata: manifest file names and subject/sample IDs

- **Status:** Implemented 2026-10-13
- **ADR:** [2026-10-13-assay-output-manifest-from-files.md](../../decisions/2026-10-13-assay-output-manifest-from-files.md)

## Problem

A script assay's output dataset is created by `_create_sds_output` in
`services/api/app/routers/assays.py` before the Airflow runs start. Two of the
metadata files it writes are wrong, and `upload_workspace_datasets` publishes them
unchanged.

1. **Manifest file names are guessed.** The manifest lists
   `sub-N/sam-M/image.nrrd` for nrrd outputs and `sub-N/sam-M/breast_mri_rai.nii.gz`
   for nifti outputs. Since the DICOM tools were changed to name their output after
   the DICOM Series Description (falling back to `image`), the real files are, for
   example, `image.nii.gz` or `ax_t1.nrrd`. The published manifest then lists files
   that do not exist, both in MinIO and in the Postgres `manifest` table.
2. **Subject and sample IDs lose their prefixes.** `subjects.xlsx` and
   `samples.xlsx` are written with `1`, `2`, ... instead of `sub-1`, `sam-1`, while
   the folders are `primary/sub-1/sam-1/`. The published dataset's
   `dataset_mapping` rows then hold bare numbers. Any later assay that uses this
   dataset as an input builds paths from those IDs and finds no files.

## Proposed changes

### 1. Prefixed IDs at creation time (`_create_sds_output`)
- Write `sub-<n>` in `subjects.xlsx` "subject id" and in `samples.xlsx` "subject id".
- Write `sam-<m>` in `samples.xlsx` "sample id".
- Folder layout and `output_mappings` stay as they are (they already use the prefixes).

### 2. Manifest rebuilt from the files at submit time (`upload_workspace_datasets`)
- Add a helper, `_reconcile_manifest(dataset_dir)`, called on each downloaded dataset
  folder before `uploader.upload_dataset`.
- It lists the files under `primary/` and rewrites the manifest so each row names a
  file that exists:
  - a row whose `sub-N/sam-M/` folder holds exactly one file gets that file's name,
    keeping its description, timestamp and file type;
  - a file with no row gets a new row, with the description of its sample folder's row
    when there is one;
  - a row whose folder holds no file is dropped and logged (that run produced nothing).
- `_create_sds_output` keeps writing its predicted rows: they carry the description and
  file type, and remain a reasonable draft if someone downloads the workspace before
  submitting.
- Notebook (Jupyter) outputs go through the same helper. They already carry their own
  manifest; rows that match real files are left untouched.

## Tests first (Red, then Green)

New file `services/api/tests/test_assay_sds_output.py`, no live services:

1. `_create_sds_output` with two samples and nrrd + nifti outputs writes
   `sub-1`/`sam-1` style IDs in `subjects.xlsx` and `samples.xlsx`
   (MinIO uploader patched; read the saved xlsx from the temp dir).
2. `_reconcile_manifest` renames a guessed row to the one real file in its folder.
3. `_reconcile_manifest` keeps a row that already matches.
4. `_reconcile_manifest` adds a row for an unlisted file and drops a row whose folder
   is empty.
5. `upload_workspace_datasets` calls the reconcile step before `upload_dataset`
   (downloader and uploader patched).

Run in a throwaway API container, as the existing suite is run.

## Verification after Green

- Rebuild and restart `digitaltwins-api`.
- Run a script assay end to end on a test dataset, submit its results, and check that
  the published dataset's manifest rows (MinIO and Postgres) match its files and that
  `dataset_mapping` holds `sub-`/`sam-` IDs.

## Verification result

- New tests: 9 pass (`tests/test_assay_sds_output.py`). One more test was added
  during Green, for renaming rows after a dropped row.
- Full API suite: no new failures. The 6 failures and 1 error that remain fail the same
  way without this change (401s from conflicting auth overrides across test modules,
  a missing `bucket_name` fixture, and a test that reads stdin).
- Rebuilt and restarted `digitaltwins-api`. A script assay re-run on the rebuilt API
  wrote `sub-`/`sam-` IDs in its output's subjects and samples sheets, and the
  reconcile step turned its guessed manifest rows into the files the tools wrote.
  The output was checked without publishing it, to avoid a duplicate platform dataset.

## Out of scope

- Correcting datasets published before this fix (done by hand where needed).
- Changing the DICOM tools' output naming.

## Task checklist

- [x] Draft plan and ADR
- [x] Sync artifacts to docs/artifacts/
- [x] Approval
- [x] Red: write the tests above, see them fail
- [x] Green: implement changes 1 and 2
- [x] Sync artifacts to docs/artifacts/
- [x] Rebuild and restart digitaltwins-api; end-to-end check
- [x] Update ADR status; sync artifacts to docs/artifacts/
