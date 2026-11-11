# Walkthrough: updated architecture diagram

## What changed

- **`docs/architecture.md` (new).** It has two Mermaid diagrams:
  - a service view: tiers, gateway routes, and calls labelled with protocol or purpose;
  - a container view: one subgraph per compose project, with the logical Postgres databases.

  It also has tables for services, data stores and Keycloak clients, a "not part of the running stack" list, links to the related ADRs, and a pointer to the legacy diagram.
- **`docs/images/architecture_diagram.png` renamed to `docs/images/architecture_diagram_legacy.png`.** The file is kept for history and the README no longer embeds it.
- **`README.md`.** The embedded image is replaced by an `## Architecture` section (summary, service table, link to `docs/architecture.md`), and the section is added to the table of contents.

## Follow-up: high-level overview

Feedback: the service and container views are too detailed to explain the project to external people.

I added an **Overview** diagram with about 12 plain-language boxes and no ports or protocols. It shows:
- **users:** people, scripts using the SDK, and hospital imaging systems;
- **a secure entry point** with single sign-on;
- **the web portal and the API;**
- **two capability groups:** "Run and build analyses" and "Store and describe data".

It is the first view in `docs/architecture.md` and is also embedded in the README Architecture section. The two copies are identical, so update both when either changes. The detailed views stay in `docs/architecture.md` as developer reference.

## Follow-up: overview simplified

User feedback on the overview diagram, applied to both copies (`docs/architecture.md` and README):
- **Removed nodes:** "Hospital imaging systems" and "Scripts and notebooks / Python SDK".
- **Renamed nodes:**
  - The actor is now just "User".
  - "Secure entry point / HTTPS gateway" is now "Gateway / nginx", because it can also run over plain HTTP on localhost.
- **Added node:** "GUI tools and plugins / run in the portal", inside "Run and build analyses", with the edge `builder → deploys`.
  - The builder builds each registered GUI tool, or a GUI workflow's step, into a JavaScript bundle and stores it in MinIO. The portal loads that bundle.
  - If a tool has a backend, the builder runs it as a container, which the portal reaches at `/plugin/<name>`.
  - See `docs/decisions/2026-10-02-build-gui-workflow-tools.md`.
- **Layout fix:** the "Store and describe data" subgraph uses `direction TB`. Once no node in it links outside, Mermaid lays it out on its own and would otherwise stack its unconnected nodes vertically.
- **Text:** the overview paragraph is updated to match.

## Follow-up: rolled back to Mermaid

The draw.io experiment below was reverted at the user's request:
- The three `.drawio.svg` files were removed.
- `docs/architecture.md` and the README are back to the Mermaid version: the overview, service view and container view blocks, plus their original text.
- All four Mermaid blocks still render with mermaid-cli, and all relative links resolve.

The section below is kept as a record of what was tried.

## Follow-up (reverted): draw.io format

Feedback: use draw.io instead of Mermaid. The user chose all three views and asked that the Mermaid blocks be replaced, not kept alongside.

**The diagrams are now draw.io files:**
- `docs/images/architecture_overview.drawio.svg`
- `docs/images/architecture_services.drawio.svg`
- `docs/images/architecture_containers.drawio.svg`

Each file is an SVG with the editable draw.io diagram embedded. GitHub shows it as an image, and you edit it in place with draw.io or the VS Code Draw.io Integration extension. The README and `docs/architecture.md` embed these images, and no Mermaid blocks remain.

**How they were made:**
- A throwaway script generated the diagrams as native draw.io XML with explicit coordinates and orthogonal edge routes.
- I exported them with `rlespinasse/drawio-desktop-headless:v1.75.0` (`-x -f svg --embed-diagram`).
- The exporter adds a PNG fallback image after every HTML label. I stripped those, which cut each file from about 900 KB to 50–110 KB. Browsers render the labels without them, and draw.io's editor saves files without them too.
- The SVGs use draw.io's adaptive `light-dark()` colours, so they stay readable in dark mode.

**Service view simplifications compared with the Mermaid version:**
- Each box shows its gateway path, so the gateway has no edge to every service.
- Keycloak's OIDC links are not drawn; the legend states them instead.
- The portal → MinIO plugin-bundle edge is dropped, because the portal's proxying is described in the text.

## Deviations from the plan

- The container view shows in-network `host:port` values (for example `api:8000`), not host ports. Host ports depend on `.env` and are meant only for debugging; production exposes only the gateway.
- I swapped the separate Postgres container node for a subgraph that holds the four logical databases, because the diagram reads more clearly that way.
- JupyterHub's build-only `singleuser` compose service is mentioned in the text, not drawn.

## How the diagram content was sourced

I drew only edges that have code or config evidence: compose files, `services/nginx/snippets/platform-routes.conf`, `services/portal/frontend/nginx.conf.template`, the API and builder client code, and `services/keycloak/REALM.md`.

I left out edges that are configured but unused:
- Airflow DAGs → api/keycloak (the env vars are injected, but no DAG calls them);
- the Docker socket mount in the SEEK container;
- notebooks → MinIO.

There is no api → Orthanc edge, because the code has none.

## Verification

- Both Mermaid blocks render without errors with `minlag/mermaid-cli:11.4.2`, and I checked the layout visually.
- I compared every service from `docker compose config --services` against the doc. All are present, `singleuser` only as a note.
- All relative links in `docs/architecture.md` and `README.md` resolve.
- `gitleaks detect --no-git` on the new and changed docs found no leaks.
- This change is documentation only, so no containers need rebuilding.

## Stale docs noticed (not changed)

- `services/nginx/README.md` "Known gaps" still says the platform routes don't work.
- `docs/gateway-pathway-access.md` describes the portal as "FastAPI + React".
- `services/portal/docs/plugin-system-architecture.md` still shows a SQLite plugin registry.
- The status table in `services/nginx/snippets/platform-routes.conf` marks the Airflow prefix "NOT live".
