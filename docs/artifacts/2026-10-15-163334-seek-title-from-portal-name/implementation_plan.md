# Implementation plan: SEEK title from the portal name

- **Date:** 2026-10-15
- **Status:** Approved 2026-10-15, implemented (see [walkthrough.md](walkthrough.md))
- **ADR:** [docs/decisions/2026-10-15-seek-title-from-portal-name.md](../../decisions/2026-10-15-seek-title-from-portal-name.md)

## Problem

When a tool or workflow is registered from the portal, the user types a name (prefilled from the folder name). That name is stored as `dataset.dataset_name` in Postgres, but it is never sent to SEEK. SEEK's title comes from the CWL `label`, or from the CWL file stem when there is no label (`_build_crate` in `services/api/src/digitaltwins/seek/writer.py`).

Two uploads that share a CWL, such as a package and a renamed copy of it, therefore show the same title in SEEK and can't be told apart. The portal list and SEEK also disagree on what the item is called.

SEEK sets the workflow title from the RO-Crate root `name` (`lib/seek/workflow_extractors/ro_crate.rb`, `m[:title] = crate['name']`). This was checked in the running `ldh:v0.3.2` image. Changing the crate's root `name` is therefore enough.

## Change

Title precedence for the crate root `name`: **portal name → CWL `label` → CWL file stem**. A blank or whitespace-only name counts as missing.

| What is registered | Portal name used | SEEK title |
|---|---|---|
| Tool upload (portal) | the session `name` | portal name |
| Workflow upload (portal) | the session `name` | portal name |
| Each step tool registered by a workflow upload | none | CWL `label` → stem (unchanged) |
| `POST /datasets` direct ingest (no name parameter) | none | CWL `label` → stem (unchanged) |

Unchanged:
- The crate root `description` stays the CWL `doc`.
- The main-entity file's `name` stays the CWL `label` or stem, because it describes the CWL file itself.
- Tags, `internals`, the single-POST flow and the rollback logic are not touched.

## Steps (TDD)

1. **Red: writer tests** (`services/api/tests/test_seek_writer.py`)
   - `build_tool_crate(cwl, "script", title="My tool")` → root `name == "My tool"`, root `description` is still the CWL `doc`, main-entity `name` is still the CWL label.
   - Same for `build_workflow_crate(..., title="My workflow")`.
   - `title=None` and `title="  "` fall back to the label (existing tests already cover label → stem).
   - `Writer.register_tool(..., title=...)` / `register_workflow(..., title=...)` put that title in the posted crate.
   - verify: these tests fail.
2. **Red: pipeline tests**
   - `services/api/tests/conftest.py` `FakeSeek.register_tool` / `register_workflow`: accept a `title=None` keyword and record it.
   - `test_dataset_uploads_tools_api.py`: approving a tool upload registers the session name as the SEEK title.
   - `test_dataset_uploads_workflows_api.py`: the workflow is registered with the session name; its step tools with `title=None`.
   - Existing equality asserts on `client.seek.workflows[...]` get the new `title` key.
   - verify: these tests fail.
3. **Green**
   - `seek/writer.py`: `_build_crate(main_cwl, keywords, extra_cwls=(), title=None)`, root `name = (title or "").strip() or label or stem`. Thread `title=None` through `build_tool_crate`, `build_workflow_crate`, `Writer.register_tool` and `Writer.register_workflow`.
   - `tools/pipeline.py` `commit_tool`: `writer.register_tool(cwl_path, tool_type, seek_project_id, title=dataset_name)`.
   - `workflows/pipeline.py` `commit_workflow`: `writer.register_workflow(..., title=dataset_name)`; step-tool registration unchanged.
   - Update the module docstring and the `_build_crate` docstring.
   - verify: the full API suite passes in a throwaway container (no new failures beyond the known pre-existing ones).
4. **Docs**
   - ADR above → `Accepted`. Add a pointer from the 2026-09-30 ADR (its Option C says the title comes from the CWL `label`).
   - Check `docs/` for SEEK integration pages that say the title comes from the CWL label, and update them.
5. **Deploy and check**
   - Rebuild and restart `digitaltwins-api` (the portal frontend and backend are unchanged).
   - Manual check: register a tool and a workflow from the portal under a name that differs from the CWL label, and confirm the SEEK titles.
6. **Artifacts**
   - [x] Sync artifacts to `docs/artifacts/` after each document change.
   - [x] Walkthrough after implementation.

## Out of scope

- Renaming SEEK workflows that are already registered (no backfill).
- Renaming a SEEK workflow when the portal dataset is renamed later (there is no rename flow today).
- Adding a name parameter to the `POST /datasets` direct-ingest route.

## Open questions (defaults proposed, all accepted at approval)

1. **CWL label when a portal name is given.** Proposed: the label is dropped from the SEEK title. It is still visible in the CWL that SEEK shows, and the description stays the CWL `doc`. Alternative: put the label at the start of the description.
2. **Step tools of a workflow upload.** Proposed: keep the CWL label. The user names only the workflow, and the step tool's portal name is just the CWL stem (`tool_x`), which reads worse than the label.
3. **Direct ingest without a name.** Proposed: keep the label → stem fallback. Alternative: use the folder name, which is what Postgres records there.
