# Hand every GUI tool one standard launch context

- **Date:** 2026-11-12
- **Status:** Accepted. Amends the "Generic contract vs. VolView convention" section of [2026-10-05-gui-assay-launch-input-handoff.md](2026-10-05-gui-assay-launch-input-handoff.md).

## Context

Launching a gui assay opens its workflow's GUI tool in `/tool-view`. Since ADR 2026-10-05 the portal has
`provide()`d an `assayContext` (assay id, tool record, input files as proxy URLs) to the plugin, and set
VolView's `?urls=` query. Only VolView used either. It was undocumented, so nothing told an author to read it.

A tool that ignores it has to name its data in a config file built into its bundle. The Lesion Ground Truth
Curator does this: its bundled `tool_config.json` names a dataset `volunteer`, and launching it from an assay
failed with "File not found in MinIO: volunteer/subjects.xlsx". Pointing it at an assay's data meant a
rebuild, or editing its settings by hand in every new browser tab, and one build could serve one assay at
most.

That tool also has a backend that reads MinIO itself, with the platform MinIO credentials the builder passes
to every plugin compose file. The context offered it only browser URLs, which a backend can't authenticate
to after the 5-minute cookie expires, and no cohort.

## Alternatives Considered

### How a tool gets its per-launch configuration

#### Option A: one standard object every tool reads (chosen)
- Pros: one documented, versioned contract; the portal knows nothing about any tool's internals; a tool
  changes once, then needs no rebuild for any assay.
- Cons: every existing tool needs a one-time code change to read it.

#### Option B: per-tool templates the portal renders
Each tool ships a template of its own config with placeholders, and declares where the result goes (for
example a `sessionStorage` key). The portal fills it in and writes it before mounting the tool.
- Pros: existing tools work with no code change.
- Cons: the portal has to support every tool's delivery channel and format, and a tool's private storage
  key becomes a platform contract. Changes inside a tool can break the launch without anyone noticing.

### How a tool's backend reaches the files

#### Option A: both a proxy `url` and the MinIO `bucket`/`key` (chosen)
- Pros: browser code keeps the per-user checked proxy; a backend reads directly, as the annotator already
  does, with no token to forward or refresh.
- Cons: backend reads aren't checked per user. The builder already gives every plugin backend MinIO
  credentials, so this adds no access that wasn't there.

#### Option B: proxy URLs only
- Pros: every read is checked per user.
- Cons: only a real gain if MinIO credentials are also taken from plugin backends, which would break the
  annotator. Backends would have to forward and refresh the user's token.

## Decision

The portal provides a **launch context** to a GUI tool opened from an assay, as
`provide('launchContext', …)`. The name `assayContext` goes, since nothing read it. The context holds
`schemaVersion` (1), `assayId`, `cohort` (subject ids, resolved from the assay's stored indices), and
`inputs`: each with its dataset, bucket, sample type and files, and each file with a proxy `url` and a MinIO
`key`. `getAccessToken()` comes with it. A Tool Hub launch provides no context.

The contract is the `LaunchContext` type in the portal's `models/types.ts`, with a filled-in
`launch-context.example.json` beside it that a test keeps in step. Tool authors read
[gui-tool-authoring.md](../gui-tool-authoring.md). VolView keeps its `?urls=` query.

## Consequences

- A tool that reads the launch context needs no rebuild per assay. Existing tools, the annotator first, need
  a one-time change in their own repositories; until then they behave as before.
- The context is deliberately small: no user identity, no outputs, nothing for Tool Hub launches. Each can be
  added later without a breaking change; renaming or removing a field needs a new `schemaVersion`.
- Backends reading MinIO with platform credentials stays allowed. Taking those credentials away from plugin
  backends is a separate, later decision.
- SDS sample ids restart in every dataset, so two inputs can resolve to the same `(subject, sample)` pair.
  `_discover_samples` keeps such a pair once, which suits script runs (one DAG run per sample) but left the
  later input with no files. A GUI launch now keeps each input's samples (`per_input=True`). Script runs still
  keep the pair once, even across datasets, so a second dataset's sample doesn't run; changing that changes
  how many DAG runs an assay triggers, and is a separate decision.
