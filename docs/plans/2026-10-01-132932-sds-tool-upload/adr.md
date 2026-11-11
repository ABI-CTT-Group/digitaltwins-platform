# Accept SDS-packaged tools in the portal tool wizard

- **Date:** 2026-10-01
- **Status:** Accepted

## Context

The portal tool wizard (`/upload-tool-dataset`) accepts a Git URL or a local folder/zip of **source code**. The source must have exactly one `.cwl` at its root. Portal-backend packages it into a SPARC dataset (`code/` + `primary/tool_<stem>.cwl`) and hands it to digitaltwins-api at Approval. That flow is Option A of [2026-10-01-unified-tool-dataset-ingest.md](2026-10-01-unified-tool-dataset-ingest.md).

Some tools already exist as SDS packages, for example `tests/data/tool_dicom_to_nifti`. These packages have `dataset_description.xlsx`, `code/`, and their CWL file at `primary/tool_*.cwl`. The API ingests them over REST and the CLI, but the wizard rejects them because there is no root `.cwl`. Uploading the packaged folder as source is also wrong: the builder would put the whole SDS inside a new dataset's `code/`.

This ADR amends the unified tool ingest ADR, and Option A stays in place.

## Alternatives Considered

### Option A: Auto-detect SDS packages in the existing portal pipeline (chosen)
A source root with a top-level `dataset_description.xlsx` counts as an SDS package. It must contain exactly one `primary/tool_*.cwl`, the same rule as the API's `find_tool_cwl`. The tool's source is its `code/` folder. The wizard steps stay the same: Annotation, then Build & Test, then Approval, then handoff.
- Pros:
  - Same review, test-launch and approval gate as for source tools.
  - The handoff and the API are unchanged.
  - It works for local folder/zip and for Git sources.
- Cons:
  - The detection rule exists in three places: the browser, portal-backend and the API.

### Option B: Browser uploads the SDS straight to the API
- Pros: the measurements uploader already does this; little portal-backend work.
- Cons:
  - No Build & Test step, no portal approval, and no test launch.
  - GUI tools still need the portal build.
  - This is the Option B the earlier ADR rejected.

### Option C: An explicit third source option, "SDS package"
- Pros: the intent is explicit, which allows clearer error messages.
- Cons:
  - An SDS hosted on Git would need yet another mode.
  - Users must pick the right option for something the system can detect.

### GUI SDS packages: build from `code/` (chosen) vs ship a prebuilt bundle
- **Prebuilt bundle:** the portal's build renames the UMD library to a unique per-tool `expose_name`, and the launcher looks it up as `window[expose]`. A prebuilt bundle would need a new naming convention and a uniqueness check, so this is deferred.
- **Build from `code/` (chosen):** keeps the `expose_name` rewrite. The fixture `tests/data/tool_volview` already ships its source in `code/`.

### SDS metadata: pass through (chosen) vs regenerate via sparc-me
- **Regenerate:** consistent, but it discards metadata the user curated.

## Decision

Option A, with two further choices:
- GUI SDS packages are built from `code/`. `frontend_folder`, `backend_folder` and `config.portal.json` are relative to `code/`. The bundle is written into `primary/`.
- The SDS's metadata files are copied through untouched.

Workflows keep the root-CWL rule.

## Consequences

- One wizard handles every tool source: a Git source repo, local source, a local SDS package, and a Git-hosted SDS package.
- A source tree with a stray root `dataset_description.xlsx` is treated as SDS and must then have `primary/tool_*.cwl`.
- An SDS package without `code/` is accepted, as the API accepts it. A GUI one then fails at the npm step.
- If a GUI SDS's `primary/` already holds a bundle, it is overwritten by the build output when the names collide.
- The rule is small and duplicated in three places. Backend tests pin the portal-backend version. A change to the API's `find_tool_cwl` must also be made in portal-backend and the frontend.
- Deferred:
  - Prebuilt GUI bundles.
  - Prefilling wizard fields from `dataset_description.xlsx`.
