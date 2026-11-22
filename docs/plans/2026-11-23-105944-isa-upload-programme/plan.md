# ISA projects page: one upload, a programme per project, no source badges

## Context

Follow-up to the hierarchy change on `/catalogue/isa-project` (plan
`docs/plans/2026-11-23-104544-isa-hub-hierarchy/`). The user asked for three things:

1. Remove the "Example" badge from the cards.
2. When uploading an ISA project, the user chooses which programme it goes in. Today every project
   sits under one built-in programme, "Te Whatu Ora Radiology Reporting" (`SANDBOX_ID` in
   `sandbox.ts`).
3. One upload button instead of two, taking either a single JSON or a bundle (folder or .zip).

UI only: everything stays in the browser store, nothing reaches the API, and shared production
components don't change.

Decisions (from the questions):
- **Badges:** remove both "Example" and "Uploaded". Uploads still show their approval line, and the
  menu still offers Remove for uploads and Reset for examples.
- **One upload:** one "Upload ISA project" button opens the existing bundle dialog, renamed. It takes
  a folder or .zip in the shared drop area (unchanged), or a single JSON through a "pick a JSON file"
  link in the dialog. Both go through the same review step before "Add project".
- **Programme choice:** on that review step. Pick a programme the page knows, or "New programme…"
  and type a name. The default is Te Whatu Ora Radiology Reporting.
- **Programme list:** Te Whatu Ora Radiology Reporting, always listed, plus every programme a
  project sits in. A named programme exists only while it holds projects.
- **No moving:** a project can't change programme after it's added; remove it and upload it again.
- **Not in the JSON:** the programme is where this page files the project. The draft JSON format
  doesn't change, and a re-upload asks again.
- **Grouping:** the page groups cards under programme headings, so it reads programme → project →
  investigation → study. The study dashboard lists each programme at its top level.

## Model

- `IsaProjectEntry.programme?: { id: string; name: string }` in `sandbox.ts`. When it's missing
  (examples, and entries already stored in browsers), the project is in the built-in programme. No
  `EXAMPLE_RELEASE` bump is needed.
- **Programme ids:** the built-in one stays `te-whatu-ora-radiology-reporting`, so existing links
  and the demo URLs keep working. A named one is `isa-<slug of the name>` (lower case, a–z, 0–9 and
  `-`; `isa-programme` if nothing is left). A name whose slug matches a programme already listed is
  that programme, under its existing name. `isSandboxId` accepts the built-in id and any `isa-` id.
- **sandbox.ts:**
  - `sandboxProgramme(entries)` becomes `sandboxProgrammes(entries)`: the built-in programme first,
    then the others in the order their first project was added. Each is described by its project
    count.
  - A programme's children are only its own projects.
  - `parseSandboxId` returns the programme id too.
  - `resolveSandboxTrail` starts from the programme list.
- **Store:** `addBundle(project, bundled, programme)` stores the programme. A project with the same
  id is still replaced in place, and goes to the newly chosen programme.
  - `store.upload` loses its only caller, so it is removed. `fixtureSource.parseUpload` goes too if
    nothing else uses it.
  - The store tests that used `store.upload` as a helper switch to `addBundle`.
  - The "a later upload uses a registered item" test moves to `readBundle` on a lone JSON with the
    registered catalogue.
- **Lone JSON in `readBundle` (`adapter/isaBundle.ts`):** a lone JSON is a bundle of one file. It
  needs one wording fix. When the upload has no `datasets/` folders, an unknown id reads "…unknown
  dataset X (not on the platform: upload a folder or .zip with datasets/X/)". It no longer says
  "no datasets/X/ folder in the bundle".

## Design

The look stays as it is, with HubShell, the aurora tokens and the hub accent.

- **Toolbar:** one solid button, "Upload ISA project", with a one-line note under it: "A JSON file,
  or a folder or .zip with the datasets it needs that aren't on the platform yet."
- **Dialog:**
  - The title becomes "Upload ISA project".
  - The intro covers both uploads. The bundle layout tree stays, introduced as "To bring datasets,
    workflows or tools that aren't on the platform yet:".
  - Under the drop area: "Or pick a JSON file", plus a hidden `.json` input.
  - The review is unchanged for a folder or .zip. For a lone JSON it skips the "Bundled items"
    section and shows only "Already on the platform: …".
  - Above the actions, a "Programme" field: a native `<select>` styled like the dialog. It lists
    the known programmes, then "New programme…", which shows a name input.
  - "Add project" stays disabled until the project reads cleanly and a programme is chosen; a new
    programme needs a non-blank name.
  - The "The JSON upload would do." hint goes.
- **Page:**
  - Each programme is a heading in `--font-ui` 600 at about 1.05rem, with its project count in
    `--text-faint` (for example "Te Whatu Ora Radiology Reporting  1 project"). Its cards follow.
  - The meta line loses the badge, leaving "1 investigation, 2 studies, 14 assays".
  - The upload errors box goes; errors now show inside the dialog.
- **Links:** "Open in study dashboard" and the tree rows build their trail from the entry's
  programme id.

## Steps (TDD)

Plan folder: `docs/plans/<YYYY-MM-DD-HHMMSS>-isa-upload-programme/` with `plan.md` and `tasks.md`.
Tick each task as its check passes, and sync after every doc edit.

1. **Red:**
   - **`sandbox.spec.ts`:**
     - The programme list is the built-in one plus each named programme, with project counts.
     - A programme's children are only its projects.
     - An `isa-` id parses, with its programme.
     - A trail resolves through a named programme.
     - The built-in id still resolves the demo trail.
   - **`isaProjectStore.spec.ts`:**
     - `addBundle` stores the programme.
     - Replacing a project moves it to the newly chosen programme.
     - The tests that used `store.upload` switch to `addBundle`.
   - **`isaBundle.spec.ts`:**
     - A lone JSON reads with nothing bundled.
     - A lone JSON with an unknown dataset gets the new hint.
   - **`BundleUploadDialog.spec.ts`:**
     - The title is "Upload ISA project".
     - Picking a JSON file reaches the review.
     - The programme select defaults to the built-in programme and lists the existing ones plus
       "New programme…".
     - A blank new name disables Add.
     - Add emits `{ project, bundled, programme }`.
   - **`IsaProjectHub.spec.ts`:**
     - There is one `[data-test=upload]` button, which opens the dialog.
     - No "Example" or "Uploaded" text appears.
     - Cards are grouped under `[data-test=isa-programme]` headings.
     - An added project lands under its programme, and its Open and tree links use that
       programme's id.
     - The replace confirmation still asks.
     - The file-input tests are rewritten through the dialog's `add` event.

   → verify: `make test-frontend` fails on exactly those tests.
2. **Green:**
   - `sandbox.ts`, `isaProjectStore.ts`, `adapter/isaBundle.ts`.
   - `components/BundleUploadDialog.vue` gets the JSON link and the programme field.
   - `IsaProjectHub.vue` gets one button, programme groups and no badges, and loses the JSON input
     and the errors box.
   - `StudyDashboardPrototype.vue` only if `parseSandboxId`'s new shape needs it.
   - Remove `store.upload` and `parseUpload` if they are orphaned.

   → verify: `make test-frontend` and `make lint` pass.
3. **Glossary (`docs/glossary.md`):**
   - "ISA project (prototype)": uploads pick a programme (Te Whatu Ora Radiology Reporting by
     default, or a new one), and they're uploaded through one dialog.
   - "ISA project bundle (prototype)": a lone JSON is also accepted.

   → verify: `make docs-check` passes.
4. **Rebuild** and restart `portal-frontend` only.

   → verify with headless Firefox: upload a JSON into a new programme "Radiology research". The
   page shows two programme groups with no badges. The study dashboard's top level lists both
   programmes, and the new project opens under its programme. Check the dialog at 1440px and
   390px. Critique the screenshots and fix before reporting.

## What changed during the build

- **Empty bundles:** the screenshots showed a lone-JSON upload's card saying "with nothing
  bundled". `addBundle` now keeps `bundled` only when the upload brings an item, as the old JSON path
  did. A store test and a hub test cover it.
- **Accents in slugs:** programme slugs drop accents rather than letters, so "Ōtautahi" becomes
  `isa-otautahi`.

## Not in this plan

- Moving a project between programmes, a programme field in the JSON, or empty programmes.
- Reading SEEK's real programmes.
- Committing, pushing or deploying to the demo host: each needs a separate request. The earlier
  hierarchy change is uncommitted too.

## Critical files

- `services/portal/frontend/src/views/isa-project/sandbox.ts`
- `services/portal/frontend/src/views/isa-project/isaProjectStore.ts`
- `services/portal/frontend/src/views/isa-project/adapter/isaBundle.ts`, `adapter/isaProjectSource.ts`
- `services/portal/frontend/src/views/isa-project/components/BundleUploadDialog.vue`
- `services/portal/frontend/src/views/isa-project/IsaProjectHub.vue`
- Their specs in `views/isa-project/__tests__/`
- `docs/glossary.md`
