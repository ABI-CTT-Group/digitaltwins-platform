# JupyterHub

Interactive notebooks at `/jupyter`: one notebook server per user, each in its own container.

## Purpose

Users sign in with Keycloak and get a JupyterLab server spawned from the single-user image. The API
also drives the hub as a service: for a notebook assay it starts the user's server and stages the
assay's workspace (`assay_<id>/`) into it.

## Status

Active. The root `docker-compose.yml` includes this folder's `docker-compose.yml`.

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | `jupyterhub`, and `singleuser`, which only builds the notebook image and exits |
| `Dockerfile` | The hub: `jupyterhub/jupyterhub:5.4.6` plus `oauthenticator` and `dockerspawner` |
| `Dockerfile.singleuser` | The per-user notebook image, `quay.io/jupyter/scipy-notebook`, pinned by digest |
| `jupyterhub_config.py` | All hub settings: Keycloak login, groups, `base_url`, DockerSpawner, and the `api` service and its token |
| `tests/test_service_token.py` | Tests that the `api` service token is required and that old configured tokens are revoked |

## Connects to

| Peer | How |
|---|---|
| Keycloak | Client `jupyterhub` (`JUPYTERHUB_CLIENT_ID`, `JUPYTERHUB_CLIENT_SECRET`). The browser is sent to `KEYCLOAK_PUBLIC_URL`; token and userinfo calls go to `KEYCLOAK_INTERNAL_URL`. Group membership comes from the `groups` claim |
| api | The hub registers a service named `api` with the admin role and token `JUPYTERHUB_API_TOKEN`. The API sends the same token to `JUPYTERHUB_INTERNAL_URL` (default `http://digitaltwins-platform-jupyterhub:8000/jupyter`) |
| gateway | `/jupyter/` → `jupyterhub:8000`, unrewritten; the hub serves under `c.JupyterHub.base_url = '/jupyter/'` |
| Host Docker daemon | `/var/run/docker.sock`, so DockerSpawner can start user containers on the platform network (`DOCKER_NETWORK_NAME`) |
| Volumes | `${PROJECT_NAME}_jupyterhub_data` (the hub's SQLite database), and one `digitaltwins-platform_jupyterhub_user_<username>` volume per user |

## Configuration

Set in the root `.env` (rendered from `.env.template`); the secrets come from `secrets.env`.
`jupyterhub_config.py` reads most of these with `os.environ[...]`, so the `${X:-...}` defaults in
`docker-compose.yml` are the only defaults.

| Variable | Use |
|---|---|
| `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_REALM` | Keycloak, browser-facing and container-to-container |
| `JUPYTERHUB_CLIENT_ID`, `JUPYTERHUB_CLIENT_SECRET` | The `jupyterhub` client (the secret is required) |
| `JUPYTERHUB_PUBLIC_URL` | The hub's public URL; must match the gateway route and the client's redirect URIs |
| `JUPYTERHUB_CRYPT_KEY` | Encrypts users' auth state |
| `JUPYTERHUB_API_TOKEN` | Required. The `api` service's token; the API reads the same variable |
| `JUPYTERHUB_ALLOWED_GROUPS`, `JUPYTERHUB_ADMIN_GROUPS`, `JUPYTERHUB_ADMIN_USERS` | Who may sign in, and who is a hub admin |
| `JUPYTERHUB_PORT` | Host port (8016) |
| `DOCKER_NETWORK_NAME`, `DOCKER_NOTEBOOK_IMAGE`, `DOCKER_NOTEBOOK_DIR`, `DOCKER_MEM_LIMIT`, `DOCKER_CPU_LIMIT` | DockerSpawner; set in `docker-compose.yml`, not in `.env` |

## Run & test

```bash
make test-jupyterhub                                    # from the repository root
make test-jupyterhub PYTEST_ARGS="-k revoked"           # one test
```

The target builds the hub image and runs `tests/` inside it, because the tests load
`jupyterhub_config.py` with the hub's own packages. CI runs it as `jupyterhub unit tests` when this
folder changes.

To rebuild after a change: `docker compose build jupyterhub singleuser && docker compose up -d jupyterhub`.

## Gotchas

- **Rotating `JUPYTERHUB_API_TOKEN` revokes the old token.** The hub never removes a token that is no
  longer configured, so `jupyterhub_config.py` deletes the `api` service's configured tokens from the
  hub database before each start, and the hub re-adds the current one.
- **Some names are fixed to the default project name** and don't follow `PROJECT_NAME`: the container
  `digitaltwins-platform-jupyterhub` (used by `hub_connect_url` and by the API's default
  `JUPYTERHUB_INTERNAL_URL`), the image `digitaltwins-platform-jupyter-singleuser:latest`, and the
  per-user volumes `digitaltwins-platform_jupyterhub_user_<username>`.
- **It holds the host Docker socket**, like the builder, so it can start containers on the host.
- **Logout must match the realm.** The `post_logout_redirect_uri` is built from
  `JUPYTERHUB_PUBLIC_URL`, and Keycloak checks it against the `jupyterhub` client's redirect URIs.
- Two comments in `jupyterhub_config.py` say the group and admin variables aren't forwarded by
  `docker-compose.yml`. They are now, so the values in `.env` apply.

## Related ADRs

- [Make the JupyterHub service token a per-deployment secret](../../docs/decisions/2026-10-16-jupyterhub-service-token-secret.md)
- [Stage a notebook assay's workspace in JupyterHub at launch](../../docs/decisions/2026-10-16-stage-notebook-assay-workspace.md)
