# Unify tool dataset ingest in digitaltwins-api

- **Date:** 2026-10-01
- **Status:** Accepted

## Context

This is the tool-dataset counterpart of [2026-09-28-unified-dataset-ingest-in-digitaltwins-api.md](2026-09-28-unified-dataset-ingest-in-digitaltwins-api.md). Tool datasets can be uploaded in two ways, and the two are inconsistent.

**Portal GUI.** The flow is `/upload-tool-dataset`, backed by portal-backend `/api/tools/*`.
- It is a build pipeline: it clones or receives source, runs `npm run build:plugin` for GUI plugins, packages a SPARC folder, and can `docker compose up` a plugin backend.
- Metadata goes only into `portal.*`. Files go to MinIO `tools/<name>_<8hex>/`. SEEK and `public.*` are never touched.
- Approval is a TODO. It pushes an `ActivityDefinition` keyed by a placeholder `sparc-tool-$<uuid4>`, and the tool's CWL I/O annotation is saved but never used.
- The backend checks no token, even though deploy runs `docker compose` on the host's docker socket.
- It has GUI and Script types. GUI datasets carry no CWL.

**REST API.** The endpoint is digitaltwins-api `POST /datasets?category=tools`, plus the chunked `/datasets/uploads/*` sessions.
- It checks the Keycloak JWT (`admin` or `researcher`).
- It writes `public.dataset`, with a UUID from the DB, and stores files in MinIO `tools/<dataset_uuid>/`.
- It registers the tool in SEEK as a Workflow from a single RO-Crate, all-or-nothing ([2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md](2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md)).
- It has no FHIR support, and it parses `subjects.xlsx` / `samples.xlsx` if they are present.
- It uploads to MinIO *before* calling SEEK with the caller's token.

The requirements:
- Keycloak authentication
- optional FHIR annotation keyed by real dataset UUIDs
- no subjects or samples
- uploads from both the GUI and the REST API
- metadata in platform Postgres, files in platform MinIO, and registration in SEEK

Keycloak access tokens last 300 s (`services/keycloak/import/digitaltwins-realm.json`). SEEK checks project membership against the caller's token.

## Alternatives Considered

### Ingest ownership

#### Option A: the portal builds, the API ingests, and the handoff happens at Approval (chosen)
- Pros:
  - Only portal-backend has npm and the docker socket, so building and deploying stay there.
  - Ingest has one implementation, in the API.
  - The portal keeps its Build & Test step and its Approval step.
- Cons:
  - portal-backend gains an API client and a handoff state machine.
  - The bytes cross from portal-backend to the API once.

#### Option B: separate upload from build
The browser uploads an SDS folder straight to the API, and building becomes a later action on a tool that has already been ingested.
- Cons: the git-clone and build flow no longer produces the dataset, and the portal wizard has to be restructured.

#### Option C: drop the portal build
- Cons: git-sourced and built GUI plugins are lost.

#### Option D: unify only script and notebook tools
- Cons: GUI tools, the main portal use case, stay inconsistent.

### Handoff credentials

#### Option A: forward the user's token when they click Approve (chosen)
- Pros:
  - SEEK registers the tool as the user, so project membership checks still mean something.
  - The token is fresh, because the handoff starts from a click.
- Cons: the token has to outlive the transfer (see below).

#### Option B: open a staged session when the build finishes
- Cons: builds run in the background for minutes, so the token has expired by then.

#### Option C: a portal service account
- Cons: SEEK would register every tool as the service identity.

### Large transfers against 300 s tokens

#### Option A: chunked session plus an in-memory token relay (chosen)
portal-backend drives `/datasets/uploads/*`. The portal page polls the handoff status every few seconds, and each poll carries a token that keycloak-js keeps fresh. The job keeps only the newest token, in memory. If a part PUT gets a 401, the job pauses as `awaiting_reauth` and resumes from the API's chunk status on the next poll.
- Pros:
  - No new infrastructure.
  - No user action while the tab is open.
  - An internal transfer inside one token window covers tool sizes we see in practice (MBs to hundreds of MB).
- Cons: if the tab is closed, a long handoff pauses until the page is opened again.

#### Option B: shared staging volume with zero-copy adopt (deferred)
portal-backend writes the built folder to a volume shared with the API and calls an "adopt folder" endpoint.
- Pros: nothing crosses the network, and the token is needed only for two short calls.
- Cons: couples the two containers through a volume, and adds an API entry point that takes a path.
- **Deferred:** revisit if tool datasets grow to tens of GB.

#### Option C: offline tokens, with portal-backend refreshing them
- Cons: portal-backend would hold long-lived user credentials.

### SEEK ordering

The chosen order is **SEEK first, then Postgres and MinIO**; if the storage step fails, the SEEK workflow is deleted. The RO-Crate needs only the CWL, so it doesn't need the dataset UUID. Registering first means the token is used within seconds of finalize, however long the MinIO upload takes. The current order (storage first) fails whenever the upload outlasts the token, and rolls back the whole dataset.

### Tool FHIR

#### Option A: the same pattern as measurements (chosen)
- `fhir=none|auto` plus optional `fhir_descriptions` (`workflow_tool`: `model`, `software`, `input`, `output`, `description`).
- The server owns `uuid`, which equals `dataset_uuid`, and also `name`, `title` and `version`.
- The annotation is stored in `dataset_fhir_annotation`, and one `ActivityDefinition` is pushed after commit.
- A failed push leaves the dataset committed with `fhir_status=failed`, and it can be retried.
- Pros: one mental model and one set of endpoints for every category.

#### Option B: auto only
- Cons: loses the CWL I/O mapping that workflow annotation needs.

#### Option C: all-or-nothing together with SEEK
- Cons: a HAPI outage would block tool uploads, and the behaviour would differ from measurements.

The tool's CWL I/O annotation is stored in the API, keyed by `dataset_uuid`, not in `portal.plugin_annotations`. REST-uploaded tools then get it too.

### Pre-approval GUI bundles

#### Option A: a separate portal-owned `tool-builds` bucket (chosen)
- Pros: the `tools` bucket then maps 1:1 to `public.dataset` rows.

#### Option B: keep `tools/<expose_name>/`
- Cons: uncommitted prefixes are mixed in with dataset UUIDs.

#### Option C: serve from the portal volume
- Cons: needs a new serving route, and nginx has no local route today.

### Re-approval of a rebuilt tool

#### Option A: overwrite (chosen)
The new build is committed first, and only then is the previous dataset deleted (Postgres, MinIO, SEEK and FHIR).
- Pros:
  - There is one live version.
  - A failed re-approval leaves the previous version in place.
- Cons: the dataset UUID and SEEK id change on each re-approval.

#### Option B: keep both
- Cons: stale copies build up in SEEK and in the platform.

#### Option C: block re-approval
- Cons: every change would need a new tool.

#### Option D: update in place
- Cons: the API has no update path, and SEEK would issue a new id anyway.

## Decision

- digitaltwins-api owns tool ingest. The portal builds and hands off at Approval, using the chunked session API with `commit_mode=on_finalize`, the user's token, and the in-memory token relay.
- `commit_tool` registers in SEEK before storing, and rolls SEEK back if storing fails.
- Every tool, including GUI and Notebook, has exactly one `primary/tool_*.cwl`. The portal adds a Notebook type.
- Tool FHIR follows the measurement pattern and is keyed by `dataset_uuid`.
- Tool commits don't write `subject`, `sample` or `dataset_mapping` rows. The xlsx files stay in the stored folder.
- `dataset.tool_type` is persisted.
- The portal's `/api/tools/*` endpoints require Keycloak:
  - reads: any valid token
  - writes: `admin` or `researcher`
  - backend deploy: `admin`
- The Tool Hub lists API tools joined with the portal's build state.
- Re-approval overwrites. Deleting a portal tool deletes its platform dataset through the API.
- Existing plugins keep their rows and are migrated by re-approving them. A purge CLI removes legacy `tools/<expose_name>/` objects and `sparc-tool-` ActivityDefinitions.
- `UploadClient` and `cli.import_dataset` support tools.

## Consequences

- There is one ingest implementation for tools. Portal tools get real UUIDs, registration in SEEK, and FHIR.
- portal-backend depends on the API's internal URL, and keeps handoff state on `plugin_builds`.
- If the tab is closed, a long handoff pauses until the page is opened again.
- The `tools` bucket maps 1:1 to `public.dataset`. Test builds live in `tool-builds`.
- Re-approval changes a tool's dataset UUID and SEEK id, so workflows or assays that reference the old ids have to be re-linked.
- Legacy portal plugins have to be re-approved before they appear in the platform.

## Amendments during implementation

- **FHIR `version` can be set by the client.** It isn't read from `dataset_description.xlsx`. The portal sends the plugin's semver; REST clients may pass it in `fhir_descriptions`. `uuid`, `name` and `title` stay server-owned.
- **Tool `GET /fhir/preview`** returns the `workflow_tool` descriptions handed to digitaltwins-on-fhir, not a rendered ActivityDefinition.
- **Portal launch metadata covers portal-built tools only.** The portal's plugin loader needs the bundle's UMD global name (`expose`), and only portal builds inject it (through the vite config). So a GUI tool uploaded through REST is listed in the Tool Hub as a read-only platform entry but can't be launched there. The alternative was a new bundle convention (for example `expose` recorded in the dataset), which is deferred until someone needs it.
- **The SEEK project is chosen in the approval dialog**, not in the registration step, because approval is when it's used. It's stored on the plugin as the default for re-approval.
- **The portal converts the annotation draft.** The Annotation step's CWL port draft is converted into `workflow_tool.input`/`output` by portal-backend at approval, so the frontend sends only `{seek_project_id, fhir}`. For approved tools, `GET /api/tools/plugin/{id}/annotation` returns the platform's annotation converted back to the draft shape, so the workflow editor is unchanged.
- **The API address comes from the portal's existing settings** (`DIGITALTWINS_API_BASE_URL`/`DIGITALTWINS_API_PORT`, i.e. `http://digitaltwins-api:8000`). The plan had proposed a new variable with a wrong host.
- **The CLI's `keycloak_login.login()` returns `(username, token)`,** so tool imports can register in SEEK as the signed-in user.
- **Only the approver's token is relayed.** Any signed-in user can poll a handoff's status, but only a poll from the approving user (`plugin_builds.handoff_user`) relays a token and resumes the job. Otherwise another uploader's poll could make the API finalize, and so register in SEEK, as them.
- **portal-backend reaches Keycloak internally (found in the live test).** Once `/api/tools/*` required a token, every request in the local stack returned 401 and the SPA showed "session ended". portal-backend fetched the realm key from `PORTAL_KEYCLOAK_BASE_URL`, which is the public URL (`http://localhost/auth`) and unreachable from inside the container. The base URL also lacked a trailing slash, so python-keycloak's `urljoin` dropped the `/auth` context path. It now prefers the internal `KEYCLOAK_BASE_URL` (`http://keycloak:8080/auth`, as the API uses), falls back to the public URL when running standalone, and normalises the trailing slash. The issuer isn't validated, so fetching the key internally changes nothing else.
- **Test-build objects are deleted one by one (found in the live test).** Deleting a plugin failed with `MissingContentMD5`: this MinIO rejects multi-object delete without Content-MD5, which boto3 1.36 and later no longer sends. The legacy measurement purge already worked around this.
