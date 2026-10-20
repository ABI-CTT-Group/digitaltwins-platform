# Move the portal backend into the API's codebase as a separate `builder` service

- **Date:** 2026-10-20
- **Status:** Accepted; superseded in part by [2026-10-21-builder-as-its-own-service](2026-10-21-builder-as-its-own-service.md): the builder now lives in its own folder, `services/builder`, with its own Dockerfile, requirements and CI job. Supersedes, in part, [2026-10-20-api-prefix-and-portal-builder-split](2026-10-20-api-prefix-and-portal-builder-split.md): its rejected Option D is chosen here, and `/api/portal` becomes `/api/builder`.

## Context

After the dashboard moved into the API, the portal backend (`services/portal/backend`, service `portal-backend`) was left with only the plugin/workflow builder. We want one codebase for the platform's backend code: one place for its code, one image definition, one test suite and one dependency set.

What the builder does decides how it can live with the API:

- **It runs untrusted code next to the host Docker socket.**
  - A build clones a user's repository, runs `npm install --force` and the plugin's own build command. A GUI workflow's command only has to start with `npm` or `yarn`, which still runs whatever `package.json` says.
  - A deploy runs the plugin's own `docker-compose.yml` against the host daemon, through the mounted `/var/run/docker.sock`.
  - The container runs as root, and nothing sandboxes the builds. Builds run before approval, and any `admin` or `researcher` can start one.
- **Every build and deploy step inherits the service's environment,** except `PORTAL_DB_*`. Inside the API container that environment would include the Postgres superuser password, the JupyterHub API token, the Airflow credentials and the Keycloak client secret.
- **It holds state in memory and owns the plugins' lifecycle.**
  - In memory: build logs (the SSE streams) and relayed user tokens, so it must be a single process.
  - On shutdown it removes every plugin container it started.
- **It has its own data layer:** SQLAlchemy, the `portal` schema and role, and hand-written startup migrations. The API uses psycopg2, `public` and numbered SQL migrations.
- **It needs Python 3.9 tooling plus git, Node 22, yarn and the Docker CLI.** The API image is Python 3.11 with none of those.

## Alternatives Considered

### Option 1: one codebase, one container
Delete `portal-backend`; the API process serves the builder routes too.
- Pros: the simplest to run; the API's GUI-tool lookup becomes a function call.
- Cons:
  - The public API container gets the Docker socket, which is root on the host, and runs untrusted builds next to every platform credential.
  - Every API restart or deploy stops all plugin backends.
  - The API can never run more than one worker.

### Option 2 (chosen): one codebase, two containers
The code, image definition and tests move into `services/api`. The builder runs as its own service from a second Dockerfile target.
- Pros:
  - One codebase, test suite and dependency set.
  - The security boundary stays exactly where it was.
  - Builds work as before.
  - Option 3 can follow later without moving code again.
- Cons:
  - Still two containers.
  - Two migration systems and two Keycloak verifiers now sit in one codebase.
  - The builder's exposure is unchanged: no sandboxing.

### Option 3: one codebase, builds as queued jobs
The API serves every builder route. A small worker, the only thing with the socket, runs build and deploy jobs from a database table. Logs move to the database.
- Pros: the cleanest end state; nothing the public API process does touches the socket.
- Cons: the most work. The in-memory log streams, the token relay and the plugin lifecycle hooks are all rebuilt, which changes how builds behave.

## Decision

Option 2, with four separations, each enforced by `services/api/tests/test_service_separation.py`:

1. **Image targets.**
   - `api` keeps today's contents: no git, Node or Docker CLI, and no builder code.
   - `builder` holds `builder/` and its tools, has no `app/` or `src/`, and does not derive from `api`.
2. **Entry points.** `app.main:app` and `builder.main:app` don't import each other.
3. **Environment.** The builder gets an explicit, minimal set: no `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*` or `API_PUBLIC_URL`. It connects as the `portal` role, not the superuser.
4. **The Docker socket** is mounted on `builder` only.

Details decided with it:
- **Naming.**
  - The service is `builder`, and its public path is `/api/builder/{tools,workflow}`, matching how `/api` names the `api` service. `/api/portal` had not shipped, so renaming it cost nothing.
  - The env vars follow: `BUILDER_DB_*`, `BUILDER_URL`, `BUILDER_PORT`. The `PORTAL_BACKEND_HOST` and `PORTAL_KEYCLOAK_BASE_URL` aliases are replaced by `PLATFORM_DOMAIN` and `KEYCLOAK_PUBLIC_URL`, which carried the same values.
  - Names that hold data keep their names, so no migration is needed: the `portal` schema and role, and the `portal_workspace`, `portal_datasets`, `plugin_database` and `nginx_plugin_configs` volumes.
- **The GUI-tool lookup stays an HTTP call** from the API to the builder, as the user. The API never reads the `portal` schema.
- **The builder's code is a top-level package, `services/api/builder`,** not part of the `digitaltwins` pip package, so the PyPI package doesn't ship Docker-builder code.
- **One CI check.** The builder's tests run in `make test-api` and CI's "api unit tests". The "portal-backend unit tests" check is retired.
- **Ported as they were:** the SQLAlchemy layer, its migrations and its Keycloak verifier.

## Consequences

- **What gets easier.**
  - One place for backend code, one Python version, one dependency set and one test run.
  - The API image is no larger or more privileged than before.
- **Unchanged and still unsafe: builds are not sandboxed.** Anything that can start a build can reach the host Docker daemon. The follow-up is to run builds against an isolated daemon (a Docker-in-Docker sidecar, rootless Docker or a daemonless builder), or to move to Option 3.
- **Two follow-ups for consistency, not done here:**
  - one migration runner for both `public` and `portal`
  - one Keycloak verifier
- **Breaking for deployments.**
  - Rename `PORTAL_DB_PASSWORD` to `BUILDER_DB_PASSWORD` in `secrets.env`, keeping its value, then regenerate `.env`.
  - Rebuild, then `up -d --remove-orphans`. Removing `portal-backend` stops the plugin backends it started; they must be redeployed.
  - An external plugin compose file that reads `${PORTAL_BACKEND_HOST}` or `${PORTAL_KEYCLOAK_BASE_URL}` gets its own default.
  - The standalone portal compose no longer includes a backend.
- **CI.** The repo ruleset "CI required checks" must drop "portal-backend unit tests" before this merges.
