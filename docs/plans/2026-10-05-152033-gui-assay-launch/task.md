# Task: Launch a GUI assay with its configured inputs preloaded

- [x] API: tests for `gui-inputs` and `input-files` (red)
- [x] API: implement `gui-inputs` and `input-files` (green)
- [x] Portal backend: tests for gui launch, gui-context, file proxy (red)
- [x] Portal backend: implement (green)
- [x] Frontend: tests for gui launch branch + volviewParams (red)
- [x] Frontend: implement types, api, launch, tool-plugin-view, RemoteComponentApp (green)
- [x] ADR `docs/decisions/2026-10-05-gui-assay-launch-input-handoff.md`
- [x] Sync artifacts to docs/artifacts/
- [x] Rebuild + restart api, portal-backend, portal-frontend
- [x] E2E (backend via curl; browser step left for the user): relink assay 43 to workflow 95, launch, verify VolView loads
- [x] Walkthrough + final artifact sync
- [x] Browser test failed (401 on files): VolView's `?token=` does not apply to `urls=` downloads → token in a path-scoped cookie, proxy accepts it (TDD)
- [x] Rebuild portal-backend + portal-frontend (curl: cookie-only 200, no auth 401, bad cookie 401); browser re-test: works (user confirmed)
- [x] UML design diagrams (`design_uml.md`: sequence, components, data contract)
