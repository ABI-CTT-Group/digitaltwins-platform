# Delete the API tutorials

## Context

`docs/future_refactoring.md` ("API tutorials", item 1) asked for a review of `services/api/tutorials/`.

What the review found:

- The folder is material for a single 2-hour 12 LABOURS workshop. `workshop_1_describing_and_storing_data.md` is its
  agenda, and tutorials 1 to 5 are its notebooks. All were first committed on 2023-09-18 and 2023-09-19.
- They depend on a shared-drive layout (`X:\DigitalTWINS\...`, `L:\DigitalTWINS\...`, `/MOUNT_POINT/DigitalTWINS/...`)
  and a workshop feedback survey.
- The code no longer matches the package. Tutorials 2 to 5 call `dts.Querier(config_file)` (and the same for
  `Downloader`, `Uploader` and `Deleter`), `.download()`, `.upload()`, `.delete()`, `.get_all_programs()`,
  `.get_subject()`, `.get_sample()`, `.get_values()` and `.get_metadata()`. None of these exist in
  `services/api/src/digitaltwins/core/` today: the constructors take no config file, and the methods were renamed
  or removed.
- `vph/tutorial_digitaltwins_api.ipynb` (2023) imports `Connection`, which `digitaltwins` no longer exports.
- `vph/tutorial_digitaltwins_on_fhir_api.ipynb` (2024) uses the separate `digitaltwins_on_fhir` package.

**Decision (user):** delete the whole folder, both `vph/` notebooks included, rather than archive it. Git history
keeps the files. An archive would still be linted and link-checked, would be caught by future repo-wide changes,
and would show code that doesn't run to anyone searching the repo for usage examples.

To restore any file: `git show e5e691f6:services/api/tutorials/<file>`. `e5e691f6` is the last commit before the
deletion.

The `api` image copies only `pyproject.toml`, `requirements-prod.txt`, `src/` and `app/`, so no image changes.

## Steps

1. Delete `services/api/tutorials/` with `git rm -r`.
2. `services/api/README.md`:
   - "Using the Digital Twins platform" links only to the workshop page. Remove that paragraph and keep the
     "Uploading a measurement dataset from a script" subsection, promoting it under the same heading.
   - Layout table: `examples/`, `tutorials/` row becomes `examples/` only.
3. `docs/codemap.md`: drop the `tutorials/` link from the API entry.
4. `docs/future_refactoring.md`: remove the "API tutorials" section (resolved), and remove the vph notebook from
   "Imports of names `digitaltwins` no longer exports".
5. Check: no remaining references outside `docs/plans/` (`git grep services/api/tutorials`), `make docs-check`,
   `make lint`, `make gitleaks`.

## Not in this change

- A replacement getting-started tutorial for the current API.
- `services/api/examples/`, which has the same import problems (still listed as debt).
- Older plans in `docs/plans/` that mention the tutorials: they are audit history and stay as written.

## Outcome

Done as planned. No references to `services/api/tutorials/` are left outside `docs/plans/`. `make docs-check`
(0 problems), `make lint` and a gitleaks scan of this plan folder pass. Nothing is committed yet.
