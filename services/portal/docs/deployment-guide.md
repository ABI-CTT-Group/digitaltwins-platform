# Clinical Dashboard — Deployment Guide (Portal Frontend Nginx)

**Audience:** Ops / platform team running `clinical-dashboard`, either standalone or as the `DigitalTWINS-Portal` submodule inside `digitaltwins-platform`.

**Date:** 2026-07-13
**Status:** Active — supersedes the `entry.sh` + dual-template approach. TLS and platform-level routes now live in the platform's own edge gateway.

---

## 0. TL;DR

`portal-frontend`'s nginx serves **only what the portal owns**: the SPA, `/api/` → portal-backend, `/tools/` → the public MinIO bucket, and the dynamically generated `/plugin/*` routes.

- **HTTP only.** There is no SSL template and no `entry.sh` anymore. TLS terminates at the platform gateway (`digitaltwins-platform/services/nginx`), which proxies everything it doesn't recognise back to `portal-frontend` via `location /`.
- **Standalone is a development inner loop**, not a deployment target. Real deployments go through the platform.
- **Config is rendered by the official nginx image.** `frontend/nginx.conf.template` is copied to `/etc/nginx/templates/default.conf.template`; the stock entrypoint runs `envsubst` over it at container start. No custom shell script.
- **Host ports come from `docker-compose.override.yml`**, which only the standalone stack loads.

---

## 1. Standalone and the platform cannot run at the same time

Both stacks derive their identity from the same `PROJECT_NAME=digitaltwins-platform`, so they collide on three things at once:

| Resource | Value in both |
|---|---|
| `container_name` | `digitaltwins-platform-portal-frontend` |
| Docker network | `digitaltwins-platform` |
| Host port | `80` |

Starting one while the other is up will fail on the container-name conflict — and recovering from that can take the *other* stack's containers and network with it. **Bring one down before bringing the other up.**

```bash
# switching from platform to standalone
cd digitaltwins-platform && docker compose down
cd ../clinical-dashboard && docker compose up -d
```

Named volumes survive `down`, so no data is lost either way.

---

## 2. What's in the repo

```
clinical-dashboard/
├── docker-compose.yml               # base: NO host ports (the platform gateway owns 80/443)
├── docker-compose.override.yml      # dev-only: publishes 80. Auto-merged by `docker compose up`
└── frontend/
    ├── Dockerfile                   # EXPOSE 80. Stock nginx entrypoint, no ENTRYPOINT override
    └── nginx.conf.template          # the only nginx config. HTTP only
```

`entry.sh`, `nginx.http.conf.template`, and `nginx.ssl.conf.template` are **gone**. If you still see them, your checkout is stale.

There is no `certs/` requirement for the portal anymore — certificates belong to the gateway.

---

## 3. Running it standalone (development)

```bash
cd clinical-dashboard
docker compose up -d --build
```

Browse `http://localhost/`.

> **Use `docker compose up`, not `docker compose -f docker-compose.yml up`.** Compose only auto-merges `docker-compose.override.yml` when you don't pass `-f`, and port 80 is published in that override. With an explicit `-f` the stack comes up with no published ports and nothing is reachable.

That asymmetry is deliberate: the platform consumes this repo through `extends: { file: docker-compose.yml, service: portal-frontend }`, which reads only the file it names. So the platform never picks up the override, and 80/443 stay free for the gateway.

---

## 4. Environment variables

```dotenv
# Hostname the portal is reached at. Used for CORS origins and generated URLs.
PORTAL_BACKEND_HOST=localhost

# Public scheme of the portal. Decides whether the backend emits http:// or https://
# in generated URLs (workflow metadata, MinIO presigned links, CORS origins).
#
# Behind the platform gateway this must match how a *browser* reaches the gateway —
# including the case where TLS is terminated by a load balancer in front of it
# (then SSL=true even though the gateway itself speaks plain HTTP).
SSL=false

# portal-backend's port. Rendered into the nginx proxy_pass targets.
BACKEND_PORT=8000

# Upload ceiling, in MB. Rendered into client_max_body_size on the upload-source
# location, enforced by portal-backend, and surfaced to the frontend dropzone via
# GET /api/measurement/config — so all three layers move together.
MAX_UPLOAD_MB=20480

# Per-chunk body cap for measurement chunked-upload PUTs. Must stay >= the backend's
# MEASUREMENT_PART_SIZE_BYTES (default 8 MiB).
MAX_PART_SIZE_MB=16
```

> `SSL` used to be read as `USE_SSL` by the backend while every `.env` shipped `SSL` — so the flag was permanently `false` and HTTPS deployments silently emitted `http://` URLs. The key is now `SSL` everywhere. If you have `USE_SSL` in an old `.env`, it does nothing; rename it.

> **Do NOT remove `NGINX_CONF=nginx.conf.http`** if it exists in your `.env`. That belongs to **SEEK**, not to portal-frontend.

---

## 5. How the config is rendered

The official `nginx` image's entrypoint runs `envsubst` over `/etc/nginx/templates/*.template` and writes the result to `/etc/nginx/conf.d/`. The Dockerfile copies `nginx.conf.template` there; nothing else is needed.

By default that entrypoint treats **every defined environment variable** as substitutable, which would happily replace nginx's own `$host` / `$scheme` / `$connection_upgrade` with empty strings. `docker-compose.yml` narrows it:

```yaml
- NGINX_ENVSUBST_FILTER=^(BACKEND_PORT|MAX_UPLOAD_MB|MAX_PART_SIZE_MB)$$
```

(`$$` escapes compose interpolation, so the container sees a single `$`.)

Sanity check after a deploy:

```bash
docker compose exec portal-frontend nginx -t
docker compose exec portal-frontend cat /etc/nginx/conf.d/default.conf
```

You should see `proxy_pass http://portal-backend:8000;` (substituted), `proxy_set_header Host $host;` (**not** substituted), and at the bottom `include /etc/nginx/conf.d/plugins/*.conf;`.

---

## 6. Deploying under the platform

The platform builds this repo as a git submodule and adds its own edge:

```
browser → gateway (digitaltwins-platform/services/nginx, owns 80/443 + TLS)
            ├── /seek/ /jupyter/ /auth/ /airflow/ /minio/
            └── /  →  portal-frontend  (this repo: SPA, /api/, /tools/, /plugin/*)
```

Gateway config is bind-mounted, so operators change a route and `nginx -s reload` — no image rebuild. See `digitaltwins-platform/services/nginx/README.md`.

**Never edit `services/portal/DigitalTWINS-Portal/` from the platform side.** It is a git submodule; editing it dirties the working tree and the next `git submodule update` will conflict. Portal changes are made here, pushed, and picked up by bumping the submodule SHA.

---

## 7. What NOT to change

- **`NGINX_CONF=nginx.conf.http` in `.env`** — belongs to SEEK.
- **The shared network name** (real name `digitaltwins-platform`, = `${PROJECT_NAME}`). Plugin backends join it and nginx resolves their container hostnames through it. Renaming it — or `PROJECT_NAME` — breaks plugin routing.
- **`include /etc/nginx/conf.d/plugins/*.conf;`** at the bottom of `nginx.conf.template`. Removing it breaks the plugin system.
- **The `nginx_plugin_configs` volume mount** — portal-backend writes, portal-frontend reads. Do not rename its path.
- **`NGINX_ENVSUBST_FILTER`** — dropping it lets envsubst eat nginx's own variables.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Nothing on `http://localhost/` after `docker compose up` | You passed `-f docker-compose.yml`, so the override with `ports: 80:80` was skipped | Drop the `-f` |
| `Conflict. The container name "digitaltwins-platform-portal-frontend" is already in use` | The other stack (platform or standalone) is still up — they share `PROJECT_NAME` | `docker compose down` the other one first (§1) |
| Rendered `default.conf` has `proxy_set_header Host ;` — empty values | `NGINX_ENVSUBST_FILTER` missing or its `$` not escaped as `$$` in compose | Restore the filter |
| Backend emits `http://` URLs on an HTTPS deployment | `SSL` not set to `true`, or still using the dead `USE_SSL` key | Set `SSL=true` and rebuild portal-backend |
| Plugin URLs return 404 | Plugin `include` line missing, or `nginx_plugin_configs` not mounted | Check the template's last line and the compose volume list |
| 502 from `/api/` | portal-backend not ready, or on a non-default port | `docker compose ps portal-backend`; check `BACKEND_PORT` |
| SSE build logs arrive in one delayed burst instead of streaming | A proxy hop is buffering — most likely the gateway's fallback `location /` | Confirm `proxy_buffering off` in `services/nginx/snippets/portal-fallback.conf` |
| Uploads fail with **413** at the edge | The gateway's fallback is capping the body | The edge must be transparent (`client_max_body_size 0`); the real cap belongs to portal-frontend's `MAX_UPLOAD_MB` |
