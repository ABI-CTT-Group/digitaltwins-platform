# HAPI FHIR

The platform's FHIR R4 server, holding the clinical metadata that describes datasets, models, tools
and workflows.

## Purpose

The API pushes FHIR resources here when a dataset is registered with a FHIR annotation:

- measurement datasets: per subject a `Patient`, `ResearchSubject`, `Consent` and `Composition`, plus
  `ImagingStudy`, `Observation` and `DocumentReference` resources;
- models: a `Device`;
- tools: an `ActivityDefinition`;
- workflows: a `PlanDefinition` whose actions point to the tools' `ActivityDefinition`s.

Browsers and external clients reach it at `/fhir`.

## Status

Active. The root `docker-compose.yml` `extends` the `hapi-fhir` service from this folder's
`docker-compose.yml`.

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | The `hapi-fhir` service (`hapiproject/hapi:latest`) |
| `application.yaml` | HAPI's Spring configuration: FHIR R4, CORS, cascading deletes, expunge, bulk export. Mounted at `/app/config/application.yaml` |
| `HealthCheck.class` | A compiled Java class, mounted at `/app/HealthCheck.class`. The container healthcheck runs it (`java -cp /app HealthCheck`); it requests `http://localhost:8080/fhir/metadata`. Its source isn't in the repository |

## Connects to

| Peer | How |
|---|---|
| Postgres | The `hapi` database: `SPRING_DATASOURCE_URL` (`database:5432/hapi`), as `POSTGRES_USER` |
| api | Pushes and deletes resources at `FHIR_ENDPOINT` (`http://hapi-fhir:8080/fhir`) |
| builder | Deletes a workflow's `PlanDefinition` when the workflow is deleted, at `FHIR_ENDPOINT` (default `hapi-fhir:8080/fhir`; the client adds `http://` when the value has no scheme) |
| gateway | `/fhir/` → `hapi-fhir:8080`, prefix kept (`services/nginx/snippets/platform-routes.conf`) |

## Configuration

No variables of its own. The compose file sets `SPRING_CONFIG_LOCATION` and the three
`SPRING_DATASOURCE_*` variables, the last two from `POSTGRES_USER` and `POSTGRES_PASSWORD` in the root
`.env`.

## Run & test

No automated tests. The API's tests use an in-memory stand-in, `FakeHapi` in
`services/api/tests/conftest.py`.

For a quick look, the host publishes port 8013: HAPI's web tester UI is at `http://localhost:8013/`,
and the REST API at `http://localhost:8013/fhir`.

## Gotchas

- **The datasource in `application.yaml` is overridden.** Its `datasource` block names a
  `hapi-fhir-postgres` host the platform doesn't run. The `SPRING_DATASOURCE_*` environment variables
  win over the file. The comment in `.env.template` about "a dedicated Postgres container" is out of
  date.
- **The web tester UI isn't routed through the gateway.** It lives at the container's `/`, which would
  collide with the portal. Moving it under a prefix would also move the REST API and every
  `FHIR_ENDPOINT` (see the comment above `location /fhir/` in `platform-routes.conf`).
- **The gateway must pass `X-Forwarded-*`.** HAPI builds the absolute URLs in `Bundle.link` and
  `fullUrl` from the request.
- **No `depends_on` on the database.** `restart: on-failure` retries until Postgres is up.
- **Fixed names.** The container is always named `hapi-fhir` (not prefixed with `PROJECT_NAME`), and
  the image tag is `latest`, not pinned.
- `services/portal/hapi/application.yaml` is a separate copy, used only by the portal's standalone
  stack.

## Related ADRs

- [Unify measurement dataset ingest in digitaltwins-api](../../docs/decisions/2026-09-28-unified-dataset-ingest-in-digitaltwins-api.md)
- [A registered model is described in FHIR as a Device](../../docs/decisions/2026-10-12-model-fhir-device.md)
- [Import CLI picks up a dataset's root fhir.json as its annotation](../../docs/decisions/2026-10-19-import-cli-root-fhir-json.md)
