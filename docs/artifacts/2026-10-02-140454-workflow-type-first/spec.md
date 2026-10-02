# Design: workflow type asked first; SDS detected by the build

- **Date:** 2026-10-02
- **Status:** Draft, awaiting review
- **ADR (draft):** [2026-10-02-workflow-type-independent-of-sds](../../decisions/2026-10-02-workflow-type-independent-of-sds.md)

## Problem

In the portal Workflow wizard (`/upload-workflow-dataset`), the **Choose the workflow type** radio only appears after a source has been selected, and only if that source is an SDS package. It is shown at the bottom of the form, after Description. The Tool wizard asks for its type first, every time.

The cause is decision 2 of [2026-10-02-portal-sds-workflow-approval](../../decisions/2026-10-02-portal-sds-workflow-approval.md): "this workflow is an SDS package" is defined as "`workflows.workflow_type` is set". So the type can only be asked after SDS detection, and root-`.cwl` workflows must not have one.

## Goal

- The Workflow wizard asks for the workflow type first and always requires it, as the Tool wizard does.
- Whether a workflow is an SDS package is detected on the server, the same way tools do it: the build inspects the layout. It is never a user input and is never sent by the client.
- Root-`.cwl` workflows stay supported and keep their current approval path (user decision, 2026-10-02).
- Both wizards default their type to Script and list the options in the same order: Script, Notebook, Web GUI.

## Agreed decisions

| # | Decision | Source |
|---|---|---|
| 1 | Option B: ask the type first, and stop using `workflow_type` to mean SDS. | user, 2026-10-02 |
| 2 | Keep root-`.cwl` workflows, and add an `is_sds` column. | user, 2026-10-02 |
| 3 | Detect SDS the way tools do: the build decides; nothing is sent at create. | user, 2026-10-02 |
| 4 | The type radios in both wizards default to **Script**. | user, 2026-10-02 |
| 5 | Both wizards list the types in the same order: **Script, Notebook, Web GUI**. | user, 2026-10-02 |
| 6 | The tool form's "has backend?" defaults to **No**, and is shown only when Web GUI is selected. | user, 2026-10-02 |

## Design

### 1. Data (`services/portal/backend/app/models/db_model.py`, `app/database/database.py`)

- Add `Workflow.is_sds = Column(Boolean, nullable=True)`. `NULL` means the workflow has not been built yet; every reader treats `NULL` the same as `false`.
- **One-time backfill.** Before this change, `workflow_type IS NOT NULL` meant SDS. So when the column is first added, run `UPDATE workflows SET is_sds = (workflow_type IS NOT NULL)`, then never again. After this change root-`.cwl` workflows also get a type, so re-running the backfill would wrongly mark them as SDS. It runs in a dedicated startup step that adds the column and backfills in one transaction, and only when the column is missing. That step runs before the generic `migrate_add_missing_columns`.

### 2. API contract

- `WorkflowCreate.workflow_type` becomes **required** (`Literal["script", "notebook", "gui"]`). It stays `Optional` on `WorkflowResponse`, because older rows have `NULL`.
- `WorkflowResponse` gets `is_sds: Optional[bool]`. The frontend sees it as `isSds`.
- `WorkflowCreate` gets **no** `is_sds` field.
- `GET /api/workflow/{id}/cwl` adds `is_sds` to its response (`read_workflow_cwl`).

### 3. Build: the only place that decides `is_sds` (`app/builder/build_workflow.py`, `app/utils/builder_utils.py`)

- `WorkflowBuilder.build` already runs `detect_workflow_layout`. It adds `"is_sds": layout.is_sds` to its result.
- When a build succeeds, `execute_build_in_background` writes `result["is_sds"]` to `build_record.workflow.is_sds`, but only if the result has the key. Only the workflow builder returns it, so tool builds are unaffected. A failed build doesn't change `is_sds`.
- Validation:
  - Keep: an SDS package needs a type.
  - Drop: "a workflow type is set, but the source is not an SDS workflow package". Root-`.cwl` workflows now have a type.

### 4. Router (`app/router/workflow_router.py`)

| Where | Before | After |
|---|---|---|
| `POST /{id}/approval` (SDS handoff), line 478 | `if not workflow.workflow_type` → 409 | `if not workflow.is_sds` → 409 |
| `GET /{id}/approval` (legacy), line 519 | `if workflow.workflow_type` → 409 | `if workflow.is_sds` → 409 |
| `DELETE /{id}`, line 599 | `in_platform(workflow) and workflow.workflow_type` | `in_platform(workflow)` |

The delete condition doesn't need `is_sds`: `in_platform` is true only for a real, non-placeholder dataset UUID, which only the SDS handoff assigns. Removing the type check keeps the behaviour the same.

The `POST /{id}/approval` check runs together with the existing "the latest build has completed" check. The latest completed build is the one that wrote `is_sds`, so the two always agree.

### 5. Handoff (`app/services/workflow_handoff.py`)

Unchanged. It still sends `workflow_type` to digitaltwins-api.

### 6. Frontend

- **`BaseInformationStep.vue`**
  - The workflow type radio moves to the top of the form, in the same place as the tool type radio.
  - It is always shown and required, defaults to `script`, and lists Script, Notebook, Web GUI.
  - `validate()` requires `workflowType` for every workflow.
  - The payload always sends `workflowType`, and the alert text is updated to match.
- **`BaseInformationStep.vue`, Tool wizard**
  - The tool type radio lists Script (with its "Python scripts only" tooltip), Notebook, Web GUI, and defaults to `Script`, not `GUI`.
  - `hasBackend` starts as `false` (user decision, 2026-10-02). The "has backend?" radio still appears only when Web GUI is selected, because the whole GUI block is already behind `v-if="formData.label === 'GUI'"`.
  - `handleLabelChange` is unchanged. Switching away from Web GUI still sets `hasBackend = false`, so Script and Notebook tools are always saved with `has_backend = false`, which matters because several readers don't check the label. A GUI tool keeps whatever the user picked.
- **`BaseAnnotateStep.vue`**
  - `isSdsWorkflow` changes from a computed value based on `workflowType` to a ref set by one loader, `loadWorkflowCwls`. That loader replaces both `loadWorkflowCwl` and `loadSdsWorkflowCwls`.
  - The loader takes `isSds` from the source it already reads:
    - **local:** `is_sds` from `/cwl`;
    - **public GitHub:** whether `dataset_description.xlsx` is in the root listing it already fetches;
    - **other Git and private GitHub:** `isSds` from `/probe-source`, which already returns it.
  - Until it resolves, the step shows a loading state instead of the non-SDS form.
- **`WorkflowCard.vue`**, line 62: `Submit to approval` emits `approve-platform` when `workflow.isSds` is set, and runs `onSubmit` otherwise. The type chip (line 17) still shows `workflowType`.
- **`models/types.ts`**:
  - `WorkflowResponse.isSds?: boolean | null`;
  - `WorkflowInformationStep.workflowType` becomes required;
  - the `/cwl` response type gets `isSds`.

## Behaviour changes

- The Tool wizard now opens on Script instead of Web GUI, so the GUI-only fields (backend, folders, build command) are hidden until the user picks Web GUI. A GUI tool now opens on "has backend? No", which was "Yes" before, so the frontend and backend folder pickers stay hidden until the user picks Yes.
- New root-`.cwl` workflows store a type. Nothing reads it yet apart from the card's type chip.
- Before its first successful build, a workflow is not treated as SDS. `Submit to approval` takes the legacy path, which already fails without a completed build.
- Existing rows: SDS rows, which have a type, get `is_sds = true`. Root-`.cwl` rows get `is_sds = false` and keep `workflow_type = NULL`.

## Testing (written first, red → green)

Backend tests run locally (SQLite) only, never inside the live portal container.

- **Build** (`tests/test_workflow_build_dataset.py`):
  - a root-`.cwl` workflow with a type builds and reports `is_sds = false`;
  - an SDS package reports `is_sds = true`;
  - an SDS package without a type still fails;
  - the "type needs an SDS package" test is replaced.
- **Executor:** a successful workflow build writes `workflows.is_sds`, and a failed one doesn't change it.
- **Create:** a missing `workflow_type` returns 422.
- **Router** (`tests/test_workflow_handoff.py`, and others where they already exist):
  - `POST /approval` uses `is_sds`, not `workflow_type`;
  - the legacy `GET /approval` returns 409 for `is_sds`;
  - delete reaches the platform only for `in_platform`.
- **`/cwl`:** the response has `is_sds`.
- **Backfill:**
  - the first run sets `is_sds` from `workflow_type`;
  - a second startup doesn't change rows (for example, a root-`.cwl` row that has a type).
- **Frontend:**
  - `cards.spec.ts`: the WorkflowCard action depends on `isSds`, not `workflowType`;
  - a new `BaseInformationStep` spec:
    - the workflow type radio renders before any source is chosen, with Script selected and the options in the order Script, Notebook, Web GUI;
    - the tool radio uses the same order and default;
    - a fresh tool form has `hasBackend = false`, the "has backend?" radio is hidden until Web GUI is selected, and after GUI → Yes → Script the submitted `hasBackend` is `false`;
  - an annotation-loader spec, if the loader can be pulled out as a pure function: it returns `isSds` for each source kind.
- `vue-tsc --noEmit` must report no new errors.

## Out of scope

- Making the legacy approval use the type.
- Inferring the type from the package.
- Changes to digitaltwins-api.
- The "Workflow Name" heading that also appears on the tool form (`CommonInfoForm.vue:131`). It is listed only as a nearby defect.
