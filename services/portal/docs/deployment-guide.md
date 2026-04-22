# Clinical Dashboard — Deployment Guide (Portal Frontend Nginx)

**Audience:** Ops / platform team integrating `clinical-dashboard` into the existing `DigitalTWINS-Portal` stack at `test.digitaltwins.auckland.ac.nz`.

**Date:** 2026-04-20
**Status:** Active — supersedes the prior approach of hand-writing `nginx.conf` and bind-mounting it into the frontend container.

---

## 0. TL;DR

The `portal-frontend` container no longer ships a fixed `nginx.conf`. At container start, `entry.sh` picks **one of two templates** (`nginx.http.conf.template` or `nginx.ssl.conf.template`) based on whether SSL certs are present on disk, then renders it with `envsubst` using `${PORTAL_BACKEND_HOST}` and `${BACKEND_PORT}`.

- **Same image** works for local HTTP dev and production HTTPS — nothing to rebuild between environments.
- **No bind mount of `nginx.conf`** is needed anymore. If your old compose has `./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro`, **remove it** (it will shadow the rendered file and break the plugin system).
- **No new env var** needs to be added. We use the existing `PORTAL_BACKEND_HOST` from your `.env`.

---

## 1. Why this changed

The previous approach had two problems:

1. **Mixed Content on `/api/tools/`.** FastAPI's 307 trailing-slash redirect combined with nginx `X-Forwarded-Proto $scheme` (which is `http` inside the container) produced redirect URLs with the wrong protocol, so the browser blocked them. See [`https-mixed-content-fix.md`](./https-mixed-content-fix.md) for the full analysis.
2. **One fixed `nginx.conf` per environment.** You had to maintain `nginx.conf.http` and `nginx.conf.https` variants and swap them manually. The plugin system also needs `include /etc/nginx/conf.d/plugins/*.conf` which was easy to lose when hand-editing.

The new approach uses **one templated config**, picks HTTP vs HTTPS at runtime from cert presence, and always includes the plugin directory.

---

## 2. What's in the repo

```
DigitalTWINS-Portal/
├── docker-compose.yml                       # portal-frontend env + cert volume
├── certs/                                   # HOST-SIDE dir, mounted read-only
│   ├── .gitkeep
│   └── .gitignore                           # ignores *.crt / *.key
└── frontend/
    ├── Dockerfile                           # EXPOSE 80 443, ships both templates
    ├── entry.sh                             # chooses template, runs envsubst, starts nginx
    ├── nginx.http.conf.template             # HTTP mode (no cert)
    └── nginx.ssl.conf.template              # HTTPS mode (certs present)
```

There is **no** `frontend/nginx.conf` or `frontend/nginx.conf.template` anymore. If you still see one, it's stale — delete it.

---

## 3. Prerequisites

Before deploying:

1. Docker + Docker Compose v2 on the host.
2. The `digitaltwins` external network already created:
   ```bash
   docker network inspect digitaltwins >/dev/null 2>&1 || docker network create digitaltwins
   ```
3. Your existing `.env` must contain:
   ```dotenv
   PORTAL_BACKEND_HOST=test.digitaltwins.auckland.ac.nz
   ```
   If you're running locally, either leave it unset or set `PORTAL_BACKEND_HOST=localhost`.
4. Ports 80 and 443 free on the host (or mapped via reverse proxy).

---

## 4. Step-by-step deployment (production, HTTPS)

### Step 1 — Pull the updated `DigitalTWINS-Portal`

Replace your current `DigitalTWINS-Portal` (or `services/portal/DigitalTWINS-Portal/frontend` if you mount the source tree directly) with this repo's version. The files that **must** be present in the frontend build context:

```
frontend/Dockerfile
frontend/entry.sh
frontend/nginx.http.conf.template
frontend/nginx.ssl.conf.template
```

If any of these are missing, the container will fail to start with either "template not found" or fall back to the wrong mode.

### Step 2 — Verify `.env`

Open your `.env` and confirm:

```dotenv
# Required — used by nginx server_name, SSL cert filename, and backend URL generation
PORTAL_BACKEND_HOST=test.digitaltwins.auckland.ac.nz

# Optional — defaults to 8000. Only change if portal-backend runs on a different port.
BACKEND_PORT=8000

# Optional — path on the HOST where SSL certs live. Defaults to ./certs relative to compose file.
SSL_CERT_DIR=./certs
```

**Do NOT remove** `NGINX_CONF=nginx.conf.http` if it already exists in your `.env`. That variable belongs to the **SEEK** service (in the "Metadata service" section of `.env`) and is unrelated to portal-frontend. Leave it alone.

### Step 3 — Place SSL certificates

The entry script looks for files named exactly `${PORTAL_BACKEND_HOST}.crt` and `${PORTAL_BACKEND_HOST}.key`.

For production, that means:

```
<host path pointed to by SSL_CERT_DIR>/
├── test.digitaltwins.auckland.ac.nz.crt
└── test.digitaltwins.auckland.ac.nz.key
```

If `SSL_CERT_DIR` is unset, the default is `./certs` relative to the compose file. Example:

```bash
mkdir -p DigitalTWINS-Portal/certs
cp /path/to/fullchain.pem DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.crt
cp /path/to/privkey.pem   DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.key
chmod 644 DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.crt
chmod 600 DigitalTWINS-Portal/certs/test.digitaltwins.auckland.ac.nz.key
```

The cert directory is mounted **read-only** into the container at `/etc/nginx/certs`. Permissions on the host are your responsibility.

### Step 4 — Remove any legacy bind-mount of `nginx.conf`

If your root `docker-compose.yml` or the extended compose at `services/portal/DigitalTWINS-Portal/docker-compose.yml` contains any of these lines on the `portal-frontend` service, **delete them**:

```yaml
# DELETE any of these — they will override the rendered default.conf
- ./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro
- ./frontend/nginx.conf.http:/etc/nginx/conf.d/default.conf:ro
- ./frontend/nginx.conf.https:/etc/nginx/conf.d/default.conf:ro
```

Keep only the two volume mounts that `DigitalTWINS-Portal/docker-compose.yml` already declares:

```yaml
volumes:
  - nginx_plugin_configs:/etc/nginx/conf.d/plugins         # for plugin route configs
  - ${SSL_CERT_DIR:-./certs}:/etc/nginx/certs:ro           # for SSL certs
```

### Step 5 — Rebuild the image

```bash
cd DigitalTWINS-Portal   # or wherever the compose file lives
docker compose build portal-frontend
```

This builds a single image with both templates baked in. You do **not** need separate "dev" and "prod" images.

### Step 6 — Bring up the stack

```bash
docker compose up -d
```

### Step 7 — Verify the container picked HTTPS mode

```bash
docker compose logs portal-frontend | head -n 5
```

You should see:

```
SSL certs found for test.digitaltwins.auckland.ac.nz, using HTTPS mode.
Starting Nginx...
```

If you instead see `No SSL certs found ... using HTTP mode`, the cert filenames do not match `${PORTAL_BACKEND_HOST}.crt` / `${PORTAL_BACKEND_HOST}.key`. Check step 3.

### Step 8 — Inspect the rendered config (optional sanity check)

```bash
docker compose exec portal-frontend cat /etc/nginx/conf.d/default.conf
```

You should see `server_name test.digitaltwins.auckland.ac.nz;`, `listen 443 ssl;`, and at the bottom `include /etc/nginx/conf.d/plugins/*.conf;`.

### Step 9 — End-to-end checks

1. `curl -I https://test.digitaltwins.auckland.ac.nz/` → `200` (HTML served).
2. `curl -I https://test.digitaltwins.auckland.ac.nz/api/tools/` → `200` or `401` (not a redirect to `http://`).
3. Open the portal in a browser, install a plugin, confirm the plugin frontend loads and its backend responds via `/plugin/<name>/`.

---

## 5. Local development (HTTP)

No cert files means automatic HTTP mode:

```bash
# .env (or shell export)
PORTAL_BACKEND_HOST=localhost
# no certs in ./certs — that's fine

docker compose up --build
```

Browse `http://localhost/`. The rendered `default.conf` will listen on port 80 only, proxy `/api/` to `portal-backend:8000`, and include the plugin directory.

---

## 6. How the template selection works

`entry.sh` at container startup:

1. Reads `$PORTAL_BACKEND_HOST` (defaults to `localhost`).
2. Checks for `/etc/nginx/certs/${PORTAL_BACKEND_HOST}.crt` **and** `.key`.
3. If both exist → uses `nginx.ssl.conf.template` (HTTP→HTTPS redirect + 443 SSL block).
4. Otherwise → uses `nginx.http.conf.template` (plain port 80).
5. Runs `envsubst` to replace `${PORTAL_BACKEND_HOST}` and `${BACKEND_PORT}` in the chosen template, writes the result to `/etc/nginx/conf.d/default.conf`.
6. Starts nginx in the foreground.

This means the same Docker image is used in dev and prod — only the **host-mounted cert directory** differs.

---

## 7. File reference

| File | Purpose |
|---|---|
| `frontend/entry.sh` | Chooses HTTP/SSL template at runtime based on cert presence, renders via envsubst, starts nginx. |
| `frontend/nginx.http.conf.template` | Port 80 only. Used when certs are absent (local dev). |
| `frontend/nginx.ssl.conf.template` | Port 80 redirect + 443 SSL. Uses `${PORTAL_BACKEND_HOST}` for `server_name` and cert paths. |
| `frontend/Dockerfile` | Copies both templates into the image; `EXPOSE 80 443`. |
| `docker-compose.yml` (portal-frontend service) | Ports 80/443, env vars `PORTAL_BACKEND_HOST` and `BACKEND_PORT`, volume mounts for certs and plugin configs. |
| `certs/` | Host directory for SSL certs. `.gitignore` keeps certs out of VCS, `.gitkeep` keeps the empty folder in the repo. |

---

## 8. What NOT to change

- **`NGINX_CONF=nginx.conf.http` in `.env`** — belongs to SEEK, keep as-is.
- **Shared external network `digitaltwins`** — plugin backends join this network and nginx resolves their hostnames through it. Changing the network name will break plugin routing.
- **`include /etc/nginx/conf.d/plugins/*.conf;`** — present in both templates. Removing it breaks the plugin system.
- **The `nginx_plugin_configs` volume mount** — shared between `portal-backend` (writer) and `portal-frontend` (reader). Do not change its name or path.

---

## 9. Rollback plan

If the new config misbehaves in production:

1. Restore the previous `frontend/` directory (with the old `nginx.conf`) from git.
2. Re-add the bind mount on `portal-frontend` in compose:
   ```yaml
   volumes:
     - ./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro
     - nginx_plugin_configs:/etc/nginx/conf.d/plugins
   ```
3. `docker compose up -d --force-recreate portal-frontend`.

Note: rolling back loses the Mixed Content fix — see [`https-mixed-content-fix.md`](./https-mixed-content-fix.md) for the other two fixes (frontend trailing-slash URLs and uvicorn `--proxy-headers`) that must stay in place.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `No SSL certs found ..., using HTTP mode` on production | Cert filename mismatch | Rename certs to `${PORTAL_BACKEND_HOST}.crt` / `.key`. |
| `nginx: [emerg] cannot load certificate` | `.crt`/`.key` unreadable inside container | Check host-side permissions; the mount is `:ro` but the files still must be world-readable for the nginx user. |
| Plugin URLs return 404 | `include /etc/nginx/conf.d/plugins/*.conf;` missing, or `nginx_plugin_configs` volume not mounted | Re-check both templates and compose volume list. |
| `Mixed Content: ... http:// ...` blocked in browser | Old frontend bundle or missing `--proxy-headers` on backend | Rebuild `portal-frontend` and ensure `portal-backend` Dockerfile has `CMD uv run uvicorn ... --proxy-headers --forwarded-allow-ips *`. |
| `default.conf` inside container still shows old server block | A bind mount is overriding the rendered file | Remove any `- ./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro` from compose. |
| 502 from `/api/` | `portal-backend` not ready or on wrong port | Check `docker compose ps portal-backend`; adjust `BACKEND_PORT` in `.env` if backend listens on a non-default port. |

---

## 11. PR checklist for merging into `DigitalTWINS-Portal`

When opening the PR against `ABI-CTT-Group/DigitalTWINS-Portal`:

- [ ] Replace `frontend/entry.sh` with the new version.
- [ ] Replace `frontend/Dockerfile` with the new version (`EXPOSE 80 443`, copies both templates).
- [ ] Add `frontend/nginx.http.conf.template` and `frontend/nginx.ssl.conf.template`.
- [ ] Delete `frontend/nginx.conf` and `frontend/nginx.conf.template` if present.
- [ ] Update the root `docker-compose.yml` (or `services/portal/DigitalTWINS-Portal/docker-compose.yml`) `portal-frontend` section:
  - [ ] Add `ports: - "443:443"` (keep existing `"80:80"`).
  - [ ] Add `environment: - PORTAL_BACKEND_HOST=${PORTAL_BACKEND_HOST:-localhost}` and `- BACKEND_PORT=${BACKEND_PORT:-8000}`.
  - [ ] Add `volumes: - ${SSL_CERT_DIR:-./certs}:/etc/nginx/certs:ro`.
  - [ ] Remove any `./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro` bind mount.
- [ ] Confirm `.env` already has `PORTAL_BACKEND_HOST` (it does, per `test/.env`).
- [ ] Place production certs as `${PORTAL_BACKEND_HOST}.crt` / `.key` under `SSL_CERT_DIR`.
- [ ] Do NOT touch the SEEK-related `NGINX_CONF` variable.
