# Walkthrough: SEEK title from the portal name

- **Date:** 2026-10-15
- **Plan:** [implementation_plan.md](implementation_plan.md)
- **ADR:** [docs/decisions/2026-10-15-seek-title-from-portal-name.md](../../decisions/2026-10-15-seek-title-from-portal-name.md) (Accepted)

## What changed

| File | Change |
|---|---|
| `services/api/src/digitaltwins/seek/writer.py` | `_build_crate`, `build_tool_crate`, `build_workflow_crate`, `Writer.register_tool` and `Writer.register_workflow` take an optional `title`. The crate root `name` (the SEEK title) is `title` when it is non-blank, else the CWL `label`, else the file stem. The main-entity file keeps the CWL `label` as its `name`, and the description is still the CWL `doc`. |
| `services/api/src/digitaltwins/tools/pipeline.py` | `commit_tool` passes `title=dataset_name`. |
| `services/api/src/digitaltwins/workflows/pipeline.py` | `commit_workflow` passes `title=dataset_name` for the workflow. The step tools are registered without a title, so they keep the CWL `label`. |
| `services/api/tests/test_seek_writer.py` | New tests: the title overrides the label for tool and workflow crates; a `None` or blank title falls back to the label; `register_tool` / `register_workflow` post a crate with the title. |
| `services/api/tests/conftest.py` | `FakeSeek.register_tool` / `register_workflow` accept and record `title`. |
| `services/api/tests/test_dataset_uploads_tools_api.py` | Approving a tool session registers the session name as the SEEK title. |
| `services/api/tests/test_dataset_uploads_workflows_api.py` | Approving a workflow session titles the workflow with the session name; its step tools get no title. |
| `services/api/tests/test_datasets_tools_api.py`, `test_datasets_workflows_api.py` | Direct ingest (`POST /datasets`, no name) records `title: None`. The spy lambda forwards keyword arguments. |
| `services/api/README.md` | The tool section now describes the title order. |
| `docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md` | Option C points to the new ADR for the title. |

Who gets which title:

| Registered item | SEEK title |
|---|---|
| Tool uploaded through the portal | the portal name |
| Workflow uploaded through the portal | the portal name |
| Step tool registered by a workflow upload | CWL `label` → stem |
| `POST /datasets` direct ingest | CWL `label` → stem |

## Verification

- **Red:** before the code change, the 9 new or updated tests failed (a `TypeError` on the unexpected `title` argument, and `title` recorded as `None`). The rest of those files passed.
- **Green:** full API suite in a throwaway container with live Postgres and MinIO: 466 passed. The 6 failures and 1 error are pre-existing harness problems (`test_delete_dataset_api`, `test_*_workspace_dataset_api`, `test_upload_dataset_api::test_upload_zip`), unrelated to this change.
- SEEK (`ldh:v0.3.2`) takes the title from the crate root `name`: `lib/seek/workflow_extractors/ro_crate.rb`, `m[:title] = crate['name']`.
- `digitaltwins-api` rebuilt and restarted. It is healthy and serves the new `register_tool(..., title=None)` signature.

## Manual check (to do)

Register a tool and a workflow from the portal under a name that differs from the CWL `label`. Each should appear in SEEK under the portal name. The workflow's step tools should keep their CWL `label`.

## Not changed

- SEEK workflows that are already registered keep their titles (no backfill).
- The portal frontend and portal backend: the name was already sent in the upload session.
