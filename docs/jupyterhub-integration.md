# JupyterHub Integration

Replaces the previous single-user JupyterLab service with JupyterHub, providing
per-user isolated notebook containers with Keycloak OIDC authentication.

## Architecture

- JupyterHub runs at `/jupyterhub/` behind the nginx reverse proxy
- Each user gets their own Docker container (DockerSpawner) with a persistent named volume
- Authentication is via Keycloak OIDC (GenericOAuthenticator); group membership
  controls access (`researcher`, `admin`) and admin rights (`admin`)

## Key configuration gotchas

### nginx proxy
The `/jupyterhub/` location block must **not** strip the prefix — JupyterHub handles
its own path routing via `base_url = /jupyterhub/`. Use:
```nginx
proxy_pass http://digitaltwins-platform-jupyterhub:8000;
```
not `http://digitaltwins-platform-jupyterhub:8000/` (no trailing slash).

### HTTPS behind proxy
JupyterHub sees plain HTTP from nginx and would generate `http://` OAuth callback
URLs. Two settings are required in `jupyterhub_config.py` to force `https://`:
```python
c.JupyterHub.tornado_settings = {'headers': {'X-Forwarded-Proto': 'https'}}
c.GenericOAuthenticator.oauth_callback_url = f'{_platform_url}/hub/oauth_callback'
```
where `_platform_url` comes from the `JUPYTERHUB_PUBLIC_URL` env var.

### Keycloak internal vs public URL
JupyterHub makes two kinds of Keycloak calls:
- **Browser redirect** (authorize) — must use the public URL (`https://${PLATFORM_DOMAIN}/auth`)
- **Server-side token exchange** — must use the internal container URL with the `/auth` context path: `http://keycloak:8080/auth`

The `/auth` path suffix on the internal URL is required — omitting it causes a 404
on the token endpoint.

### Docker network name
The `DOCKER_NETWORK_NAME` env var tells DockerSpawner which network to attach
spawned user containers to. The default in Chinchien's compose was
`${COMPOSE_PROJECT_NAME}_digitaltwins` which doesn't match the actual network name
(`digitaltwins`). Fixed by:
```yaml
- DOCKER_NETWORK_NAME=${DOCKER_NETWORK_NAME:-digitaltwins}
```
and setting `DOCKER_NETWORK_NAME=digitaltwins` in `.env`.

The network declaration in `services/jupyterhub/docker-compose.yml` must also
reference the external network rather than creating a new one:
```yaml
networks:
  digitaltwins:
    external: true
    name: digitaltwins
```

### Keycloak realm
The `jupyterhub` client must be present in the realm with:
- Redirect URI: `https://${PLATFORM_DOMAIN}/jupyterhub/hub/oauth_callback`
- A `groups` protocol mapper so group membership is included in the userinfo response

## Access control

Only users in the `JUPYTERHUB_ALLOWED_GROUPS` groups (default: `admin,researcher`) can log in. Clinicians and other roles are intentionally excluded.

If a user logs in with an account that doesn't have access, they will receive a 403 with no logout option on the page. To escape, navigate directly to:

```
https://<PLATFORM_DOMAIN>/jupyterhub/hub/logout
```

This clears both the JupyterHub session and the Keycloak SSO session.

## Orthanc Explorer 2 proxy

Orthanc Explorer 2 serves its assets at paths like `/ui/assets/...`, not just `/ui/app/`. The nginx block must cover the entire `/ui/` subtree:

```nginx
location /ui/ {
    proxy_pass http://digitaltwins-orthanc:8042/ui/;
    ...
}
```

Using `/ui/app/` alone causes a black screen because the browser fetches `/ui/assets/...` and gets a 404 from nginx.

### Keycloak redirect URI for Orthanc

The orthanc Keycloak client must include a wildcard redirect URI:

```
https://<PLATFORM_DOMAIN>/ui/app/*
```

Without this, Keycloak rejects the OIDC callback with `Invalid parameter: redirect_uri`.

## Env vars (add to `.env`)
| Variable | Example | Notes |
|---|---|---|
| `JUPYTERHUB_PORT` | `8017` | Host port — must not clash with `REDIS_PORT` (8016) |
| `DOCKER_NETWORK_NAME` | `digitaltwins` | Network for spawned user containers |
| `JUPYTERHUB_CLIENT_ID` | `jupyterhub` | Keycloak client ID |
| `JUPYTERHUB_CLIENT_SECRET` | `...` | From Keycloak client credentials tab |
| `JUPYTERHUB_ALLOWED_GROUPS` | `admin,researcher` | Comma-separated Keycloak groups |
| `JUPYTERHUB_ADMIN_GROUPS` | `admin` | Comma-separated Keycloak groups |
| `JUPYTERHUB_ADMIN_USERS` | `admin` | Fallback static admin list |
| `JUPYTERHUB_CRYPT_KEY` | `...` | 64-char hex string — generate with `openssl rand -hex 32` |
