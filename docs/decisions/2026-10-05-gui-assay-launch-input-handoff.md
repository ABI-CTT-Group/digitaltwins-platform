# Launch a gui assay in /tool-view and hand its input files to the tool through the portal

- **Date:** 2026-10-05
- **Status:** Accepted

## Context

A study-dashboard assay tagged `gui` (for example "Test Assay 3: image visualisation", SEEK 43, linked to the VolView workflow) could be configured but not launched: the portal answered "GUI based workflow launch is under development", and `POST /assays/{id}/run` only knows `script` (Airflow) and `notebook` (JupyterHub).

A gui workflow's tool is a Vue UMD bundle the portal builds and serves (ADR 2026-10-02-build-gui-workflow-tools) and mounts in `/tool-view` from the Tool Hub, with nothing passed to it. Launching from an assay has to open that same tool **with the assay's configured inputs loaded**: the input dataset, its sample type and the cohort subjects, i.e. the samples `_discover_samples` would hand to an Airflow run.

Dataset files live in private MinIO buckets (one per category, objects under `<dataset_uuid>/primary/<subject>/<sample>/`). Only `tools` and `tool-builds` have an nginx route; measurement buckets have none.

VolView (the first gui tool) reads `urls`, `names` and `token` from the page query at mount, as bracketed comma lists, and sends the token as a bearer header on every file fetch.

## Alternatives Considered

### How the tool opens
- **A new tab at `/tool-view?assay=<seek id>` (chosen).** The page describes itself, so a refresh re-loads the context; the dashboard stays where it was, like notebook launches.
- **In the dashboard tab via the persisted `remoteApp` store.** Same mount, but the dashboard is lost and a refresh of `/tool-view` has no assay to re-load.

### How files reach the browser
- **An authenticated portal proxy (chosen):** `/api/dashboard/assays/{id}/input-files/{bucket}/{key}` → API `/assays/{id}/input-files/...` → MinIO. The API checks the key against the assay's non-model input datasets (`<dataset_uuid>/primary/` prefixes, no `..`), as the calling user.
  - Pros: MinIO stays private; per-user API permissions apply; no new nginx route.
  - Cons: every file streams through two services.
- **MinIO presigned URLs.** Fewer hops, but needs a public nginx route to MinIO and signatures made against the public host.

### How the tool authenticates its fetches
- **The user's Keycloak token in a path-scoped cookie (chosen, after the browser test).** `/tool-view` sets `dt_assay_file_token=<token>; path=/api/dashboard/assays/<id>/input-files; max-age=300; samesite=strict[; secure]` before the plugin mounts and clears it on unmount; the file proxy takes the bearer from the `Authorization` header, else from that cookie. Generic plugins can also call `assayContext.getAccessToken()`.
- **VolView's own `?token=` query param (the plan's first choice — did not work).** It only feeds VolView's legacy `$fetch` and DICOMweb client; the `urls=` import pipeline (`openUriStream` → `CachedStreamFetcher` → request pool) uses the browser's plain `fetch`, so the first browser run got 401 on every file. A plain same-origin fetch carries cookies but no custom header, hence the cookie.
- **Signed short-lived file tokens.** No bearer needed, but the proxy would then call the API with a service credential and we would own a signing key.

### Generic contract vs. VolView convention
- **Both (chosen).** `RemoteComponentApp` `provide()`s `assayContext = {assayId, tool, inputs[{name, datasetUuid, sampleType, files[{name, subjectId, sampleId, url}]}], getAccessToken}` for any plugin; the VolView query is set as well so VolView runs unchanged.
- **Query params only.** Every future tool would have to adopt VolView's URL convention.
- **Context only.** VolView would need a fork.

### One URL per file vs. one zip per sample
- **One URL per file (chosen).** Plain object streams, per-file progress in VolView.
- **One zip per sample.** VolView unzips archives, which would shorten the query and dodge the comma caveat below, at the cost of on-the-fly zipping on the API.

### When the workflow has no portal-built tool
- **Launch fails with a toast (chosen)**, consistent with ADR 2026-10-02: a gui workflow registered through REST/CLI has no expose name and is not launchable. The tool is resolved from the portal's `workflow_builds.seek_id` with `served_workflow_build` + `workflow_bundle_path`, exactly as the Tool Hub does.

## Decision

Portal `/assay-launch` gains a `gui` branch returning `{type: "gui", data: "/tool-view?assay=<id>"}` (or the "no launchable GUI tool" message). `/tool-view?assay=` calls `/assay-gui-context`, which resolves the bundle and maps the API's `gui-inputs` to proxy URLs. The API gains `GET /assays/{id}/gui-inputs` (reusing `_fetch_assay_configs` and `_discover_samples`) and `GET /assays/{id}/input-files/{bucket}/{key}`; the MinIO `Downloader` gains `find_bucket`, `list_objects` and `open_object`.

## Consequences

- Any gui tool can now be launched from an assay with its inputs; VolView works without changes, other tools read `assayContext`.
- **Comma caveat.** vtk.js percent-decodes each query value before VolView splits on `,`, so a file whose name holds `,`, `[` or `]` cannot be passed in the query; the builder skips it with a console warning. The `assayContext` list is complete regardless.
- `_discover_samples` dedups on `(subject_id, sample_id)` across inputs, so two inputs sharing sample ids would lose files; inherited from script runs, irrelevant while VolView has one input.
- Outputs from a gui tool (Submit) are not covered; that is a follow-up.
- The user's access token is readable by scripts on the page as a cookie for ~5 minutes, but only sent on the assay's `input-files` path; the plugin already runs in the same page as the token-holding SPA, so this adds no new exposure. Files fetched after the cookie expires get 401 — tools that load lazily should use `assayContext.getAccessToken()`.
