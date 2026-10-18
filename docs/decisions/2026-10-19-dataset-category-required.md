# Dataset category is required by the upload API, UploadClient and the import CLI

- **Date:** 2026-10-19
- **Status:** Accepted

## Context

Datasets come in four categories: measurements, models, tools and workflows. Measurements came first, so several entry points defaulted to `measurements`:
- `POST /datasets/uploads` (`SessionCreate.category`)
- `UploadClient.upload_dataset`
- the import CLI (`python -m digitaltwins.cli.import_dataset`) and its host wrappers
- `examples/upload_measurement_dataset.py`

The one-shot `POST /datasets` already required `category`. The defaults let a model, tool or workflow be sent as a measurement by omission. Validation catches that (no `sub-*/sam-*` folders), but the error talks about SPARC structure rather than the missing category.

## Alternatives Considered

### Option A: Keep the `measurements` default
- Pros: backward compatible for external scripts and notebooks.
- Cons: inconsistent with the one-shot endpoint; an omission silently picks a category.

### Option B: Require it in the CLI only
- Pros: no API break.
- Cons: the CLI, REST and client disagree.

### Option C: Require it everywhere
- Pros: one rule across all entry points; the caller always states the category.
- Cons: breaking change for external callers of `POST /datasets/uploads` (`422`) and `UploadClient.upload_dataset(path)` (`TypeError`).

## Decision

Option C. In-repo callers already send a category: the portal measurement upload, the portal tool handoff, tests and examples. So the break only affects external clients, and it is documented in `services/api/README.md`. The wrappers ask for a missing category (and a tool's or workflow's type and SEEK project) before copying, so double-click and drag-and-drop imports still work.

## Consequences

- External scripts must add `category=...`; the commit is marked as a breaking change (`feat!`).
- The CLI exits 2 on a missing `--category` before sign-in.
- The portal frontend still sends `"measurements"` when its uploader has no category; that is the frontend's own default, not the API's.
