# Walkthrough: PR3, wizard routes, resume drafts, inline errors, optional FHIR step

Plan: [plan.md](plan.md). Tasks: [tasks.md](tasks.md). ADR: [SDS-only workflow registration](../../decisions/2026-11-06-sds-only-workflow-registration.md).

## What changed
- **Wizards have URLs.** Each hub's `index.vue` is a layout (HubShell + `<router-view>`; the Tools hub also keeps the log console). Its children are the list (`''`), a new item's wizard (`new`) and an existing item's wizard (`:id/register?step=…`). Roles sit on the hub route, so they cover all three. Route names: `RegisterTool`, `ContinueToolRegistration`, and the same for workflows, measurements and models. The list routes keep their names (`UploadToolDataset`, ...).
- **One tool and workflow wizard.** `components/RegisterWizard.vue` replaces `UploadToolForm.vue`, `UploadWorkflowForm.vue` and `BaseCompleteStep.vue`. Its steps are Source → FHIR annotation (optional) → Build.
  - Saving step 1 creates the item once and `router.replace`s to `/catalogue/<hub>/<id>/register?step=annotation`. There, step 1 is a read-only summary (name, type, version, source), so it can't be submitted twice.
  - Starting the build opens the build log (tools) and returns to the hub.
- **Continue registration.** A never-built tool or workflow offers Continue registration. `registrationSteps.ts` `nextStep` opens the annotation step until the item has one, and the build after that.
- **Editing the annotation.** Tool and SDS workflow cards have Add/Edit FHIR annotation until the item is in the platform. A saved annotation is filled in, port by port.
- **Builder fix.** Saving a workflow's annotation again now updates it in place, as for tools; before, every save inserted another row.
- **Inline errors.** `BaseInformationStep`, `BaseAnnotateStep` and `BaseBuildStep` take an async `submit` prop, await it, and show a failure under their buttons: the server's `detail`, or the status in words (`apiError.ts` `describeApiError`). Before, the tool and workflow wizards dropped these errors silently. The Models hub's toasts use the same helper.
- **SDS-only workflows.** Step 1 of the Workflow wizard refuses a source that isn't an SDS package: "This folder isn't an SDS package (no dataset_description.xlsx). Only SDS workflow packages can be registered for now." The non-SDS paths stay in place, marked `follow-up: non-SDS workflows`.
- **The FHIR annotation is optional.** The tool, workflow and measurement steps are titled "FHIR annotation (optional)" and have **Skip for now**. The model step is renamed to match.
- **Leave guard.** `useLeaveGuard` asks before leaving step 1 with input in it or an upload running, both for in-app navigation (confirm) and for closing or reloading the tab (`beforeunload`). Creating the item and moving on don't trigger it. Cancelling a measurement or model upload doesn't either, because the upload is already cancelled.
- **Tokens.** Step 1's git token is kept in the tab's memory only (`pendingAuth.ts`), so the same registration's annotation and first build can use it after the URL changes. Continuing a registration later asks for it again in `RebuildAuthDialog`, which has new `title`, `note` and `verb` props ("Repository access", "Continue with Token").
- **Measurements and models.** `/catalogue/<hub>/new` uploads, then moves to `<id>/register?step=annotation`. Resume upload opens `?step=upload`, and Add/Edit FHIR annotation opens `?step=annotation`.
- **WizardFrame.vue.** The three wizards share one frame. On phones the stepper becomes "Step n of m: …", and the annotation ports stack one per row.

## Deviations from the plan
- The plan's wireframe showed the steps as a side list on wide screens. The wizards keep the horizontal stepper (not clickable), with the compact "Step n of m" line on phones.
- The Complete step is gone: starting the build returns to the hub, where the card shows "Building…" (and, for tools, the build log opens).

## Verification
- `make test`: api 407, builder 260 (12 skipped), frontend 267, util 5. The new specs were red first: `registrationSteps`, `RegisterWizard`, `dataset_wizards`, `useLeaveGuard`, `apiError`, `BaseBuildStep`, the new cases in `BaseInformationStep`, `BaseAnnotateStep`, `cards`, `cardStatus` and `catalogue_routes`, and the builder upsert test.
- `make lint` and `make docs-check`: clean.
- `builder` and `portal-frontend` rebuilt and restarted.
- Headless Firefox (Playwright, signed in as an admin; existing items stubbed in the browser so nothing was created):
  - From the Tools hub: Continue registration → the annotation step at its own URL → Skip for now → the build step.
  - The token prompt for a GitLab tool continued later.
  - The leave guard on step 1: dismissing stays, accepting returns to the hub.
  - The measurement wizard's first step.
  - The annotation step at 360px. Its first capture showed overlapping step labels and squeezed ports, which led to `WizardFrame` and the phone rules.
