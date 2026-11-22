# Tasks: demo step titles

- [x] Write the plan (plan.md)
- [x] Sync plans to docs/plans/
- [x] 1. Red: update fixture-derived title expectations and add a "no title starts with Assay" check; `make test-frontend` fails on exactly those
- [x] 2. Green: rename the 14 titles in the fixture and bump `EXAMPLE_RELEASE` to 3; `make test-frontend` passes, `make lint` matches main
- [x] 3. Update the `platformRun.ts` comment and check `docs/glossary.md`; `make docs-check` passes
- [x] Sync plans to docs/plans/
- [x] 4. Rebuild and restart `portal-frontend`; screenshot the breast pilot page showing the numbered titles

## Part 2: no "mock" where the audience can see it

- [x] Write the Part 2 plan
- [x] Sync plans to docs/plans/
- [x] 1. Red: tests expect the new package and catalogue names, and no "mock" in the packages (xlsx included); they fail
- [x] 2. Green: rename and reword the four packages; edit the xlsx cells; rename the catalogue fixture names; `make test-api`, `make test-frontend` and `make lint` pass
- [x] 3. Update the populate script, glossary, codemap, SCRIPTS.md and platformRun.ts comment; bump `EXAMPLE_RELEASE` to 4; `make docs-check` passes
- [x] Sync plans to docs/plans/
- [x] 4. Add `util/swap-isa-mock-workflows.sh` (dry run, asks before deleting); list it in SCRIPTS.md; the dry run shows the right ids
- [x] 5. Run the swap locally (confirm the deletions); clear the stale Jupyter assay folders (confirm); rebuild `portal-frontend`; check Airflow, Jupyter, SEEK, the catalogue and the prototype, with screenshots
- [x] 6. Sync plans to docs/plans/; decide whether an ADR is needed (no ADR: a one-off data swap for demo items, using existing APIs)

## Part 3: drop the platform wording from the study page

- [x] 1. Red: the two specs expect no note and no "Platform assay N" link; `make test-frontend` fails on exactly those two
- [x] 2. Green: remove the note and the link with their styles; `make test-frontend` (527) and `make lint` pass
- [x] 3. Rebuild and restart `portal-frontend`; screenshot shows neither text, and Launch is still enabled
- [x] Sync plans to docs/plans/

## Part 4: deploy to the demo host

- [x] 1. Bring the demo checkout up to these changes; rebuild and restart `portal-frontend`; the served bundle has the numbered titles and no "Platform assay" or note text
- [x] 2. Dry-run, then run the swap script there; SEEK titles have no "mock"; Airflow shows "Inference" and "Generate breast model" tagged `breast-pilot`
- [x] Sync plans to docs/plans/
