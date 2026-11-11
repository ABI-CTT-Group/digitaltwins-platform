# Plan: "workflows" dataset upload (script / notebook / gui)

## Context

The dataset upload API (`services/api`) can ingest a **tool** dataset as one unit:
- registers it in SEEK as a Workflow tagged `tool` + type;
- stores its files in MinIO `tools/<uuid>/`;
- stores its metadata in Postgres;
- optionally pushes a FHIR ActivityDefinition.

We now want the same for **workflow** datasets, using the examples
`tests/data/workflow_image_conversion` (script) and `tests/data/workflow_volview` (gui).

A workflow dataset is SDS-shaped like a tool dataset:
- `primary/workflow_*.cwl` (`class: Workflow`) plus a copy of each step's `primary/tool_*.cwl`;
- the code lives in `code/`.

Uploading one registers each step's tool as its own tool dataset, then the workflow itself:
- MinIO `workflows/<uuid>/`;
- Postgres;
- a SEEK Workflow tagged `workflow` + type. This is already what `seek/querier.py:170` lists;
- FHIR, opt-in as for tools (`fhir=auto` or `fhir_descriptions`): one ActivityDefinition per tool, then a PlanDefinition for the workflow whose actions link to those ActivityDefinitions (§5).

**Decisions from the interview**

| Topic | Decision |
|---|---|
| Tools | Each distinct tool CWL becomes a **separate tool dataset**: `tools` bucket, its own SEEK entry tagged `tool` + type, `tool_type = workflow_type`. |
| Code split | 1. If `code/<tool_stem>/` exists, it becomes that tool's `code/`.<br>2. Otherwise, a **script** tool gets the top-level `code/<tool_stem>.*` files; it is a 400 if there are none.<br>3. Otherwise, a **notebook/gui** tool (always the only step) gets all of `code/`. |
| Category/bucket | Share `workflows` with the existing assay workspace outputs and portal builds. Leave those writers untouched. A workflow *definition* is recognised by `dataset.workflow_type IS NOT NULL`, never by category alone. |
| Scope | One-shot `POST /datasets`, resumable `/datasets/uploads`, CLI + Python client, FHIR PlanDefinition, cascade delete. |
| DB | Migration `0004`: `dataset.workflow_type`, `upload_session.workflow_type`, and a link table `workflow_tool`. |
| Delete | `DELETE /datasets/{uuid}` on a workflow needs `delete_tools=true\|false`, else 409 listing the tools. Deleting a tool that a workflow still uses returns 409. Roles stay `admin\|researcher` (`require_upload_role`). |
| FHIR shape | Combined, keyed by CWL step id (see §5). |

**Out of scope:**
- Airflow DAG deployment and generation. The DAG in `code/` is stored, not deployed.
- Portal UI and the portal `workflow_router` approval stub.
- Reusing or deduplicating already-registered tools. Re-uploading a workflow creates new tool datasets.

## Design

### 1. Layout validation: new `src/digitaltwins/workflows/`

- `__init__.py` sets `CATEGORY = "workflows"`.
- `validation.py` provides `load_workflow(staging, workflow_type) -> WorkflowLayout`.
  - `WorkflowLayout` is a dataclass: `root`, `workflow_cwl`, `steps: [Step(step_id, tool_cwl)]`, `tools: {tool_cwl: [code paths]}`.
  - The dataset root is found with `resolve_project_root` (`measurements/validation.py:63`).
- Validation rules. Each failure raises `ValueError`, which surfaces as a 400.
  - `primary/` contains exactly one `workflow_*.cwl` file, and it has `class: Workflow`.
  - `steps` may be in map or list form. Every step's `run` is a string naming a `tool_*.cwl` in `primary/`. An inline `run` or a missing file fails.
  - Each tool CWL has `class: CommandLineTool`.
  - Every `primary/tool_*.cwl` is used by some step.
  - `notebook` and `gui` workflows have exactly one step.
  - Two steps that run the same tool CWL share one tool dataset.
  - The code is split as in the table above. The split is applied per *tool* (keyed by the CWL stem), not per step.

### 2. SEEK: `src/digitaltwins/seek/writer.py`

- Generalise `build_tool_crate` into `_build_crate(main_cwl, keywords, extra_cwls=())`.
  - `build_tool_crate` stays as a thin wrapper, so its tests don't change.
  - Add `build_workflow_crate(workflow_cwl, tool_cwls, workflow_type)`.
    - `keywords` are `["workflow", workflow_type]`.
    - `mainEntity` is the workflow CWL.
    - The tool CWLs go in `hasPart`, and their files go in the zip, so that `run: tool_x.cwl` resolves.
- Extract the existing POST into `_post_crate(...)`, used by both `register_tool` and a new `register_workflow(workflow_cwl, tool_cwls, workflow_type, project_id)`.
  - Same request shape as today: Authorization header only (see the 09-30 ADR).

### 3. Commit pipeline: `src/digitaltwins/workflows/pipeline.py`

- `commit_workflow(root, workflow_type, seek_project_id, api_token, dataset_name=None)` is all-or-nothing.
- It does all SEEK work first, because the caller's token lives only 300 s; the storage uploads after that can be slow.
  1. `load_workflow(...)`.
  2. Build each tool dataset in a temp dir under `staging_root()`. It contains:
     - the root `*.xlsx`, `README.md` and `CHANGES` from the workflow dataset;
     - `primary/<tool>.cwl`;
     - `code/` from the code split.
  3. Register each tool in SEEK with `register_tool`, then register the workflow with `register_workflow`.
  4. Store each tool. Extract the store + `_link` half of `tools/pipeline.commit_tool` as `store_tool(root, tool_type, seek_id, dataset_name)`; `commit_tool` keeps calling it.
     - The tool dataset name is the tool CWL stem.
  5. Store the workflow with `Uploader().upload_dataset(root, category="workflows", dataset_name=..., skip_tables=("subject","sample"))`.
     - Then run `UPDATE dataset SET seek_id, workflow_type`.
     - Then `INSERT workflow_tool` rows, one per step.
  6. On any failure, undo everything created so far (every SEEK entry, every stored dataset) using `tools.pipeline._undo`, and raise `SeekRegistrationError`. The router already maps that to 502.
- It returns `{dataset_uuid, seek_id, tools: [{step_id, dataset_uuid, seek_id}]}`.
- The workflow dataset is stored **as uploaded** (`workflows/<uuid>/...`). The tool code also lives in the tool datasets.

### 4. Postgres: migration `0004_workflow_dataset.sql`

```sql
ALTER TABLE public.dataset        ADD COLUMN IF NOT EXISTS workflow_type varchar(20);
ALTER TABLE public.upload_session ADD COLUMN IF NOT EXISTS workflow_type varchar(20);
CREATE TABLE IF NOT EXISTS public.workflow_tool (
  workflow_dataset_uuid uuid NOT NULL REFERENCES public.dataset(dataset_uuid) ON DELETE CASCADE,
  step_id               varchar(255) NOT NULL,
  tool_dataset_uuid     uuid NOT NULL REFERENCES public.dataset(dataset_uuid),  -- no cascade: blocks deleting a used tool
  PRIMARY KEY (workflow_dataset_uuid, step_id));
```

- Check the `dataset_uuid` column type in `services/postgres/digitaltwins_schema.sql` before writing the migration.
- `sessions.create_session` gains `workflow_type=None`.

### 5. FHIR: `src/digitaltwins/workflows/fhir.py`

The client sends `fhir_descriptions` in this shape; every part is optional, and `fhir=auto` is the same as `{}`:

```json
{"workflow": {"version","description","purpose","usage","author",
              "action": [{"step": "<step_id>", "input": [{"id","resource_type"}], "output": [{"id","resource_type"}]}]},
 "workflow_tools": {"<step_id>": { <workflow_tool client fields, as tools/fhir.py> }}}
```

- **Validation**, with 400 on failure:
  - unknown fields;
  - a step or port id that isn't in the CWL;
  - a `resource_type` other than ImagingStudy, DocumentReference or Observation. These are the only types the library keeps.
  - Tool sections are validated with `tools/fhir.build_descriptions`.
- **Server-owned fields:**
  - the workflow `uuid`, `name` and `title` (from the CWL `label`);
  - one `action` per step, with `title` = step id, `description` = the tool label, and `related_tool_uuid` = the tool dataset UUID;
  - `goal: []` (the library iterates it, so it must be present).
- **Build our own descriptions.** `fhir_cda.WorkflowAnnotator` crashes on `run: file.cwl`.
- **Storage:**
  - each tool dataset gets its own `{"workflow_tool": ...}` annotation (via `annotate_tool`);
  - the workflow gets `{"workflow": ...}`;
  - every one of those datasets gets `fhir_status=pending`.
- **Push** (`jobs.run_fhir_push_job`), branching on `workflow_type IS NOT NULL`:
  1. Push each linked tool with `_push_tool`, setting its `fhir_status`.
  2. Delete the PlanDefinition by its identifier.
  3. Push the workflow with `adapter.digital_twin().workflow().add_workflow_description(d).generate_resources()`.
  - Tools go first because otherwise `definitionCanonical` would silently be `None`.
  - The workflow's `fhir_status` covers the whole push. `POST /datasets/{uuid}/fhir/push` retries the whole push.
- **`app/routers/dataset_fhir.py`:** the tree, annotation PUT and preview endpoints get a workflow branch, next to the tool branches at `:46`, `:75` and `:117`.
  - The tree returns `{descriptions, steps: [{step_id, tool_dataset_uuid, ports}]}`.

### 6. API surface

- **`app/routers/datasets.py`:**
  - Add a `workflow_type: Optional[Literal["script","notebook","gui"]]` query parameter.
  - For `category == "workflows"`, `workflow_type` and `seek_project_id` are required.
  - Add a `_ingest_workflow` function, mirroring `_ingest_tool` (`:233`).
- **`app/routers/dataset_uploads.py`:**
  - `SessionCreate.workflow_type`.
  - `create_upload` accepts `workflows`, with the same required fields and a check of the descriptions shape.
  - `finalize_upload` runs `load_workflow` plus a pre-check of the descriptions.
  - `jobs._commit` gets a workflow branch.
  - `tests/test_dataset_uploads_api.py:191`: `test_other_categories_are_rejected` switches its example category to `models`.
- **Delete** (`app/routers/datasets.py:451` + `core/deleter.py`):
  - New parameter `delete_tools: Optional[bool]`.
  - The checks are made inside `Deleter` and raised as a new `DatasetInUseError`, which the router maps to 409:
    - a workflow dataset with `delete_tools` unset → 409 `{tools: [{dataset_uuid, name, seek_id, step_ids}]}`;
    - a tool dataset that has `workflow_tool` rows → 409 naming the workflows that use it.
  - Deletion order:
    1. The workflow: MinIO, then Postgres (its link rows cascade), then the PlanDefinition and the SEEK workflow (best-effort, as now).
    2. Then, if `delete_tools=true`, each distinct linked tool through the same `delete_dataset` call.
  - The result adds `tools_deleted`.
  - `get_cleanup_info` also returns `workflow_type` and the linked tool UUIDs.
  - `_delete_seek_workflow` and `_delete_fhir_resources` branch on `category == tools` or `workflow_type` being set. Assay outputs stored under `workflows` behave as before.
- **CLI** (`cli/import_dataset.py`): add a `--workflow-type` flag. With `--category workflows` it requires `--workflow-type` and `--seek-project-id`, and validates with `load_workflow`.
- **Client** (`client.py:46`): `upload_dataset(..., workflow_type=None)`, which needs `seek_project_id` too. There is no client delete method, so nothing changes there.
- **Docs:**
  - `services/api/README.md` upload section: describe the workflows category.
  - The docstrings of `POST /datasets` and `DELETE`.

## Implementation order (TDD: write each test red, then make it pass)

0. **Spike against live SEEK**, before step 2.
   - POST a workflow crate whose `run:` refers to tool CWLs packed in it.
   - Confirm SEEK accepts it, applies the tags and extracts `internals` (inputs and outputs).
   - If it rejects file references, fall back to `mainEntity` = workflow CWL without internals, and record that in the ADR.
1. Migration 0004 and `create_session(workflow_type)`. Verify with `test_migrations`/conftest `platform_db`.
2. `workflows/validation.py`, with `tests/test_workflow_validation.py`. Use inline fixtures that mirror both examples, covering:
   - the three code-split modes;
   - every 400 rule.
3. The SEEK crate and writer, with `tests/test_seek_writer.py`: workflow keywords, `hasPart`, the zip contents and the POST shape.
4. `workflows/pipeline.py`, plus the `store_tool` extraction (the existing tool tests must stay green). Extend `FakeSeek` (`tests/conftest.py:280`) with `register_workflow`.
5. One-shot API, with `tests/test_datasets_workflows_api.py` (integration):
   - script: 2 tool datasets, a workflow, link rows, MinIO keys, the type columns and 3 SEEK registrations with the right tags;
   - gui and notebook;
   - the 400 cases;
   - SEEK failure and storage failure both roll back completely.
6. Sessions, CLI and client, in a new `tests/test_dataset_uploads_workflows_api.py` and the existing `tests/test_import_dataset_cli.py` and `tests/test_upload_client.py`.
7. FHIR, in a new `tests/test_workflow_fhir.py` and as cases added to the API test from step 5.
   - Extend `FakeHapi` (`conftest.py:145`) with `workflow()` / `add_workflow_description`. It should store the PlanDefinition with a `{"reference": "ActivityDefinition/<id>"}` per action.
   - Cover: `fhir=auto` gives 2 ActivityDefinitions and 1 PlanDefinition linked to them; validated descriptions; retrying a push.
8. Delete, in `tests/test_delete_dataset_cleanup.py`:
   - 409 without `delete_tools`;
   - `false` keeps the tools;
   - `true` removes everything, including SEEK and FHIR;
   - deleting a tool that is in use returns 409;
   - an assay-output dataset under `workflows` deletes as before.
9. README and docstrings, the ADR, and the artifacts sync.

**Process notes (AGENTS.md):**
- After approval, copy this plan to `docs/artifacts/2026-10-02-<HHMMSS>-workflow-dataset-upload/plan.md` straight away, and re-sync it on every change.
- Write the ADR `docs/decisions/2026-10-02-workflow-dataset-ingest.md` from `TEMPLATE.md`. It should record:
  - separate tool datasets versus embedded tools;
  - the hybrid code split;
  - sharing the `workflows` bucket, with `workflow_type` as the discriminator;
  - the SEEK-first ordering across N+1 registrations;
  - building our own FHIR descriptions instead of using fhir_cda's annotator;
  - the `delete_tools` confirmation.
- Use `<REDACTED>` in every artifact. The example DAG in `code/` contains a default MinIO secret, so don't quote it.
- Do not commit unless asked.

## Critical files

**New:**
- `services/api/src/digitaltwins/workflows/{__init__,validation,pipeline,fhir}.py`
- `.../postgres/migrations/0004_workflow_dataset.sql`

**Modified:**
- `.../seek/writer.py`
- `.../tools/pipeline.py` (extract `store_tool`)
- `.../measurements/{jobs,sessions}.py`
- `.../core/deleter.py`
- `.../postgres/deleter.py`
- `.../cli/import_dataset.py`
- `.../client.py`
- `services/api/app/routers/{datasets,dataset_uploads,dataset_fhir}.py`
- `services/api/tests/conftest.py`
- `services/api/README.md`

## Verification

- **Tests:**
  - `cd services/api && MINIO_ENDPOINT=http://localhost:8011 MINIO_SERVER_ACCESS_KEY=<REDACTED> MINIO_SERVER_SECRET_KEY=<REDACTED> pytest tests`
  - This uses a scratch DB through `platform_db`; never run against the live database.
  - Everything should pass except the 3 known legacy failures: `test_delete_existing_dataset`, `test_upload_workspace_datasets_jupyter` and `test_upload_zip`.
- **End to end against the running stack:**
  1. `POST /datasets?category=workflows&workflow_type=script&seek_project_id=<id>&fhir=auto`, uploading `tests/data/workflow_image_conversion` as a zip. Then check:
     - the response has 1 workflow UUID and 2 tool UUIDs;
     - `http://localhost/seek/workflows` shows 1 entry tagged `workflow` + `script` and 2 tagged `tool` + `script`;
     - `GET /workflows` lists it;
     - MinIO has `workflows/<uuid>/primary/workflow_image_conversion.cwl` and `tools/<uuid>/code/tool_dicom_to_nifti.py`;
     - Postgres has the `workflow_tool` rows;
     - HAPI has a PlanDefinition whose actions point to the 2 ActivityDefinitions.
  2. Repeat with `tests/data/workflow_volview` and `workflow_type=gui`: 1 tool, whose `code/` is the whole VolView tree.
  3. `DELETE` the workflow:
     - without `delete_tools` it returns 409 listing both tools;
     - with `delete_tools=true` it removes everything in SEEK, MinIO, Postgres and HAPI.
