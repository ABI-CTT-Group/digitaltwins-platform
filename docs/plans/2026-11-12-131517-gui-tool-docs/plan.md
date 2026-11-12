# Plan: one guide for GUI tool authors, and the plugin system doc moved to docs/

## Context

Bringing a GUI tool into the platform meant reading four places: `services/portal/docs/plugin-system-architecture.md`
(§7 is the author contract; the rest is how the builder, nginx and MinIO work), `docs/gui-tool-authoring.md`
(the launch context), the portal README (the registration wizard) and ADRs (SDS packaging). The architecture
doc sits under the portal, but most of it describes the builder, which is its own service now, and parts are
stale: it says bundles go to the `tools` bucket (builds go to `tool-builds`; `tools/<dataset_uuid>/` after
approval), that local sources come from a `/plugins/` volume, that `config.portal.json` holds plugin metadata
(the builder only checks it parses; the fields come from the wizard), and its files map names the old
`DigitalTWINS-Portal/` repo.

## Decisions (agreed with the user)

- Split the doc by audience. The author contract (§7) moves into `docs/gui-tool-authoring.md`, which becomes
  the one guide for authors: package, contract, register, launch context.
- The rest moves to `docs/plugin-system.md` (platform developers), with stale facts corrected against the code.
  Its §1 glossary becomes a short "Moving parts" table there, without the terms `docs/glossary.md` already
  defines (expose name, SDS); the rest are implementation details, which the glossary keeps out.
- Docs only: no ADR (no design decision), no code change.

## Steps

1. Branch `docs/gui-tool-docs` from `main`; this plan folder with `plan.md` and `tasks.md`.
2. `docs/gui-tool-authoring.md`: add "Package it" (SDS layout: `dataset_description.xlsx`, `code/`,
   `primary/workflow_*.cwl` with exactly one step, `primary/tool_*.cwl`; CWL input names and `doc` category),
   "What your code must provide" (the old §7: Vite lib, `build:plugin`, `VITE_PLUGIN_ROUTE_PREFIX`, portal
   externals, backend compose on the `digitaltwins` network, `config.portal.json`), and "Register it"
   (wizard steps, build, approval, first-launch backend build, linking an assay). Keep the launch-context
   sections as they are.
3. `git mv` the architecture doc to `docs/plugin-system.md`; remove §1 and §7 (point to the guide); fix the
   stale facts listed above and §9's paths; fix relative links for the new location.
4. Update inbound links: `docs/README.md`, `docs/codemap.md`, `docs/glossary.md`, `docs/request-flows.md`,
   `services/portal/README.md`, and the guide itself. Link the guide from the glossary's GUI tool entry and the
   portal README's registration section.
5. `git add`, then `make docs-check`; `make gitleaks` after committing.

## Verification

- `make docs-check` passes (links, code map, pointer files).
- `git grep plugin-system-architecture` finds no references outside `docs/plans/`.
- Every fact newly stated is traced to the code: `TOOL_BUILDS_BUCKET` and the approval path in
  `services/builder/app/engine/build_tool.py`, `config.portal.json` handling there, `tool_layout.py` (`code/`
  and `primary/tool_*.cwl`), `workflows/validation.py` (one step for gui), `get_workflow_detail` in
  `services/api/app/routers/dashboard.py` (input category from the port description).
