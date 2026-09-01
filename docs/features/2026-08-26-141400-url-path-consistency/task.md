# Task Checklist: URL Path Consistency

- [x] Update `app/routers/assays.py` to use `POST /assays`
- [x] Update `app/routers/datasets.py` to use `POST /datasets`
- [x] Update `tests/test_assay_api.py` to hit `/assays`
- [x] Update `tests/test_upload_dataset_api.py` to hit `/datasets`
- [x] Update Portal backend `dashboard.py` to use `/assays`
- [x] Update Jupyter notebooks in `my_workspace/pilot-2`
  - [x] `cohort_selection.ipynb`
  - [x] `upload_clinical_report.ipynb`
  - [x] `clinical_report_curation.ipynb`
  - [x] `mri_curation.ipynb`
- [x] Run `pytest` on `digitaltwins-api`
- [x] Run `pytest` on `portal/backend` (Skipped due to broken local venv deps)
- [x] Create `walkthrough.md`
- [x] Sync artifacts to `docs/features/2026-08-26-141400-url-path-consistency/`
