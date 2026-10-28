# Agent notes: services/builder

Read the root AGENTS.md first; this file adds only what's specific to this service.

Layout, connections, configuration and the migration steps are in [README.md](README.md).

## Where changes go

- **Routes** live in `app/router/workflow_tool_plugin.py` (`/api/builder/tools`) and
  `app/router/workflow_router.py` (`/api/builder/workflow`). Both routers depend on
  `get_current_user`; write routes add `require_any_role("admin", "researcher")` (`WRITER`). A new
  router needs a prefix under `/api/builder/` and an `include_router` in `app/main.py`;
  `tests/test_route_prefixes.py` fails on anything else.
- **Build and deploy logic** goes in `app/engine/`; the approval handoff to the platform API in
  `app/services/`; one-off commands in `app/cli/<name>.py` (`python -m app.cli.<name>`).
- **A schema change** is two edits: the model in `app/models/db_model.py`, and the next
  `app/database/migrations/NNNN_<name>.sql`, with names qualified by `portal.`. Never edit a shipped
  migration. Then run `tests/test_postgres_integration.py` against a throwaway Postgres (its docstring
  has the command; it needs `BUILDER_TEST_DB_*`, and CI skips it).
- **`app/database/migration_runner.py` and `app/client/keycloak_verifier.py`** are verbatim copies of
  the API's. Make the change in `services/api/src/digitaltwins/` and copy the file here unchanged.
  `tests/test_shared_with_api.py` compares them byte for byte.

## The security boundary

The builder holds the host Docker socket and runs third-party build and deploy commands.

- Never give it API credentials. `tests/test_service_separation.py` rejects any variable matching
  `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*`, `API_PUBLIC_URL` or `KEYCLOAK_CLIENT_SECRET` in
  the builder's merged environment (this folder's compose file plus the root one). It also checks
  that the API never mounts the Docker socket.
- Plugin commands get the builder's environment minus `BUILDER_DB_*`
  (`plugin_subprocess_env` in `app/engine/proc_stream.py`, tested by
  `tests/test_subprocess_env_scrub.py`). Any other variable you add reaches plugin code.
- Plugin compose files interpolate against that environment too, so don't add generic names
  (`HOST`, `PORT`, `DEBUG`).
- The builder reaches the API only over HTTP, as the calling user. Don't import API code.

## Tests

- `tests/__init__.py` refuses to load when `BUILDER_DB_HOST` is set, and points `DATABASE_PATH` at a
  temporary SQLite file. Tests get their tables from the models; migrations aren't run.
- For route tests, import `tests.tool_app` before any `app.*` module. It builds SQLite tables and
  accepts fake tokens: `admin`, `admin2`, `researcher` and `viewer` (no portal role), optionally
  suffixed `#<n>`; anything else is rejected like an expired token.
- Some tests read files outside this folder (portal-frontend's `nginx.conf.template`, the root and API
  compose files, the API's two shared files). `make test-builder` mounts exactly those, read-only. If
  a test needs another, add the mount there and the path to the builder job's filter in
  `.github/workflows/ci.yml`.
- A change to portal-frontend's `nginx.conf.template` must keep every `proxy_pass` behind a `set`
  variable: `tests/test_frontend_nginx_template.py`.

## Runtime behaviour to keep in mind

- On start, `_reconcile_plugin_state` in `app/main.py` matches deployments marked up against the
  running containers and rewrites or removes their nginx route files. On stop, the lifespan hook shuts
  every plugin backend down (`stop_grace_period: 60s`).
