# Smoke tests

Post-deploy checks of a running platform. They go through the gateway as a user does and answer
one question: is every service up and wired correctly? Run them after a deploy, an upgrade or a
config change, against local, staging or demo. They aren't part of `make test` or CI, because they
need a live stack.

```bash
make smoke                                     # http://localhost
make smoke SMOKE_URL=https://<platform-domain> # another host
make smoke PYTEST_ARGS="-v -k keycloak"        # narrow or detail a run
```

Run it from the repo root. You need Docker and GNU make. The first run needs internet access to
install pytest and httpx into `.cache/ci/smoke/`; later runs reuse them. For staging or demo, run it
on the host's checkout or from your own machine: both work, because the checks go through the public
gateway.

`SMOKE_URL` must be the platform's public URL, the one users type: one check compares it with the
issuer in Keycloak's tokens.

The signed-in checks need an account. A dedicated Keycloak user without the `admin` realm role is
best: the checks don't need it. Set the credentials in your shell first, and clear them after:

```bash
export SMOKE_USERNAME=<username>
read -rsp 'Password: ' SMOKE_PASSWORD; echo; export SMOKE_PASSWORD
make smoke
unset SMOKE_USERNAME SMOKE_PASSWORD
```

`make smoke` passes them to the container by name, so the values never appear in the command or its
output. Without them, those checks skip and the rest still run.

## Reading a failure

| What fails | Likely cause |
|---|---|
| Every test, with `Connection refused` | Nothing is listening at `SMOKE_URL` |
| One service's test, e.g. `test_service_answers[/seek/]` | That service is down, or its gateway route is broken |
| `test_keycloak_issuer_matches_the_public_url` | `SMOKE_URL` isn't the URL users type, or `PLATFORM_PROTOCOL`/`PLATFORM_DOMAIN` is wrong for this host |
| `sign-in failed: HTTP 401` | Wrong username or password |
| `test_airflow_components_are_healthy` | The failure lists which Airflow component isn't healthy |

## What is checked

| File | Checks |
|---|---|
| `test_public.py` | The portal page, `/api/health`, Keycloak's issuer, Airflow's component health, JupyterHub, SEEK and HAPI FHIR answer; the builder refuses an unsigned request |
| `test_signed_in.py` | Sign-in through `/api/login` returns a token; the API accepts it; the dashboard lists programmes; the builder lists workflows |

MinIO isn't checked: its health endpoint isn't routed through the gateway. Orthanc isn't checked: its
routes are best-effort ([services/nginx/README.md](../services/nginx/README.md)).

## Adding a check

These tests run against real data, so **they must only read**. Use GET requests that have no side
effects. Some GETs do: `/api/dashboard/assay-launch` starts an Airflow run, the download endpoints
build archives, and the builder's `/build`, `/approval` and `/execute` routes build, write or run
containers. Never call those here.

Keep each check to one service or one hop, so a failure names what is broken. Use the `client`
fixture for requests and `token` for a signed-in user (`conftest.py`).
