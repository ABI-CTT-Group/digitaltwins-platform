# Task: unify tool dataset ingest

Plan: plan.md. ADR: docs/decisions/2026-10-01-unified-tool-dataset-ingest.md

- [x] Plan approved and synced
- [x] ADR written
- [x] Sync artifacts to docs/artifacts/
- [x] A1 SEEK-first commit_tool (test first)
- [x] A2 skip subjects/samples for tools
- [x] A3 dataset.tool_type migration
- [x] A4 tool FHIR (builder, push, delete, routers, jobs)
- [x] A5 UploadClient + CLI tool support
- [x] A6 README
- [x] B7 portal-backend auth
- [x] B8 build output (CWL rule, Notebook, tool-builds bucket)
- [x] B9 handoff job + approval endpoints
- [x] B10 annotation conversion + workflow router reads API
- [x] B11 Tool Hub / metadata merge
- [x] B12 delete via API
- [x] B13 legacy purge CLI
- [x] C14-18 frontend + nginx + minio + compose
- [x] Full test suites
- [x] Live REST E2E (one-shot + UploadClient session, FHIR, delete)
- [x] Live portal E2E via the /api/tools endpoints (Script local zip + VolView git: build, approve, re-approve, delete). Token relay is unit-tested only.
- [x] Live partial: migrations, portal schema, tool-builds bucket, 401 without token, /tool-builds/ route
- [x] Walkthrough + ADR amendments (draft; finish after live E2E)
- [x] Sync artifacts to docs/artifacts/
- [x] gitleaks detect --source docs/artifacts/ --no-git

## Amendments (for ADR at task end)
- Tool FHIR `version` is client-settable (the portal sends the plugin semver). It isn't read from dataset_description.
- For tools, `GET /fhir/preview` returns the workflow_tool descriptions handed to digitaltwins-on-fhir, not a rendered ActivityDefinition.
- The portal's `/api/tools/metadata` (the launch lookup) covers portal-built tools only. REST-uploaded GUI tools can't be launched in the portal, because the loader needs the bundle's UMD global name (`expose`), and only portal builds set it. They show in the Tool Hub as read-only platform entries, which the frontend lists from the API. Follow-up: a convention for REST GUI bundles, e.g. `expose` in the dataset.
- The approval request is `{seek_project_id?, fhir: bool}`. The portal-backend converts the Annotation-step draft into `workflow_tool.input`/`output` (plus the plugin version), so the frontend doesn't send descriptions.
- `GET /api/tools/plugin/{id}/annotation` returns the platform's annotation, converted back to the draft shape, for approved tools. The workflow editor is unchanged.
