# Plugin System — How It Actually Works

**Date:** 2026-04-20
**Status:** Describes the current implementation in `backend/app/builder/`, `backend/app/models/db_model.py`, `frontend/src/plugins/`, and the nginx templates.

---

## 0. One-minute summary

A **plugin** is a mini-application (Vue frontend + optional Python/Docker backend) that the portal installs at runtime — no portal rebuild, no hand-edited nginx config.

The portal does four things when you click "install plugin":

1. **Builds** the plugin's Vue source into a single UMD JS file.
2. **Stores** that UMD file in MinIO's public `tools` bucket so the browser can `<script src=…>` it later.
3. **Deploys** the plugin's backend Docker container onto the shared `digitaltwins` network.
4. **Writes** an nginx `location /plugin/<name>/ { proxy_pass … }` snippet into a shared volume and hot-reloads nginx so `https://<host>/plugin/<name>/` starts routing to that container.

Everything else in this document is the detail behind those four steps.

---

## 1. Glossary

| Term | Meaning |
|---|---|
| `expose_name` | The unique slug for a plugin, e.g. `medical-image-annotator-dev-ab12`. Used as nginx location prefix, Docker compose project name, MinIO folder name, and `window[expose_name]` global in the browser. |
| **SPARC dataset** | A standardized folder layout (`code/`, `primary/`, metadata) produced by the `sparc-me` library. We use it as the transport format between build and deploy. |
| **UMD bundle** | A single JS file that registers itself on `window` when loaded via `<script>`. The portal dynamically `<script>`-loads this to mount the plugin's Vue component. |
| **`tools` bucket** | The only **public** MinIO bucket. Holds built plugin UMD bundles so the browser can fetch them without credentials. |
| **`digitaltwins` network** | The Docker bridge network shared by portal-backend, portal-frontend, and every plugin backend. This is how nginx resolves `proxy_pass http://<plugin-container>:<port>/`. |
| **`nginx_plugin_configs` volume** | A named Docker volume mounted into both portal-backend (at `/nginx-plugins-conf`) and portal-frontend (at `/etc/nginx/conf.d/plugins`). Backend writes, nginx reads. |
| `PLUGIN_ROUTE_PREFIX` | Env var `= /plugin/<expose_name>`. Injected into the plugin frontend at build time (via `.env`) and into the plugin backend at deploy time (via `docker compose` env). |

---

## 2. The four planes

```
┌──────────────────────────────────────────────────────────────────────┐
│                              Browser                                  │
│  ┌───────────────────┐    ┌──────────────────────────────────────┐   │
│  │   portal HTML     │    │  <script src="MinIO/.../name.umd.js">│   │
│  │   (Vue SPA)       │    │  dynamically loaded at runtime  ◄(A) │   │
│  └────────┬──────────┘    └───────────────────┬──────────────────┘   │
│           │ /api/…                             │ /plugin/<name>/…     │
└───────────▼────────────────────────────────────▼─────────────────────┘
            │                                    │
    ┌───────┴────────────────────────────────────┴────────┐
    │                 nginx (portal-frontend)              │
    │   /api/           →  portal-backend:8000            │
    │   /plugin/<name>/ →  <plugin-container>:<port> ◄(D) │
    │   include /etc/nginx/conf.d/plugins/*.conf          │
    └───────┬─────────────────────────────────┬───────────┘
            │                                 │
    ┌───────▼──────────┐             ┌────────▼──────────┐
    │  portal-backend  │             │  plugin-backend   │
    │  (FastAPI)       │             │  (Docker compose) │
    │  builder/        │             │  must join        │
    │  - build_tool    │             │  digitaltwins     │
    │  - deploy_tool   │             │  network          │
    └──┬──────┬────┬───┘             └───────────────────┘
       │      │    │
     write  write  write
       │      │    │
  ┌────▼───┐ ┌▼────────────┐ ┌───────▼──────────────┐
  │ MinIO  │ │   SQLite    │ │  nginx_plugin_       │
  │ tools/ │ │ plugin_     │ │  configs volume      │
  │(public)│ │ registry.db │ │  /conf.d/plugins/    │
  │  UMD   │ │ Plugin /    │ │  <expose>.conf       │
  │bundles │ │ PluginBuild │ │  (read by nginx      │
  │  ◄(A)  │ │ Deployment  │ │   include directive) │
  └────────┘ └─────────────┘ └──────────────────────┘
```

Arrow legend:
- **(A)** — Browser fetches plugin's UMD bundle from public MinIO URL.
- **(D)** — nginx reloads the `plugins/*.conf` includes after each deploy.

The **four persistence planes**:

| Plane | Storage | What it holds |
|---|---|---|
| **1. Plugin frontend assets** | MinIO `tools` bucket (public) | UMD JS, CSS, HTML for the plugin's Vue app, wrapped in a SPARC dataset |
| **2. Plugin backend runtime** | Docker (on `digitaltwins` network) | The running plugin backend container |
| **3. Routing config** | `nginx_plugin_configs` volume | One `.conf` per plugin, loaded by `include` in portal-frontend's nginx |
| **4. Registry** | SQLite `plugin_registry.db` (Docker volume `plugin_database`) | `Plugin`, `PluginBuild`, `PluginDeployment` rows — the portal's memory of what's installed |

---

## 3. Build pipeline (`PluginBuilder` in `backend/app/builder/build_tool.py`)

Triggered by POST to the plugin register/build endpoint. Input: git URL **or** local path under `/plugins/` (mounted volume). Steps:

1. **Resolve source** — clone the git repo into `./tmp/<uuid>`, or use the local plugin directory directly.
2. **Patch `vite.config.(js|ts)`** — forces `lib.formats = ['umd']`, renames `lib.name` to `expose_name`, sets `fileName` so we know what the output bundle is called. Why: we need a single predictable `<name>.umd.js` that self-registers on `window[expose_name]`.
3. **Write `.env`** inside the frontend folder containing `VITE_PLUGIN_ROUTE_PREFIX=/plugin/<expose_name>`. Vite embeds this at build time so the plugin's own API base path is correct. Why: plugin code must never hardcode a host/port — all its API calls go through `/plugin/<expose>/…` which nginx proxies.
4. **`npm install --force` + build** — runs `npm run build:plugin` by default, or the custom build command registered with the plugin. Output appears in `dist/`.
5. **Rewrite UMD asset paths** — in `<name>.umd.js` replace any embedded `http(s)://<host>:<minio_port>/tools/<expose>/primary/` prefixes with just `<expose>`. Why: we don't know the final MinIO URL at build time in every environment, so we use a placeholder and rewrite once we know it.
6. **Create SPARC dataset** — copies `code/` (source) and `primary/` (dist output) into a sparc-me dataset folder. Why: SPARC is the lab's interoperability format; we reuse it instead of inventing another layout.
7. **Upload dataset to MinIO `tools/<expose_name>/`** — public bucket, so the browser can later request `http(s)://<host>:<minio_port>/tools/<expose>/primary/<name>.umd.js` with no auth.
8. **Clean up** the temp clone.
9. **Write row to SQLite** — `Plugin` row (metadata), `PluginBuild` row (build_logs, s3_path, expose_name, dataset_path, status=COMPLETED).

After this, the plugin is **installed** (listed in the portal) but not yet **deployed** (no backend running, no nginx route).

---

## 4. Deploy pipeline (`PluginDeployer` in `backend/app/builder/deploy_tool.py`)

Runs after build for plugins with a backend folder. Steps:

1. **Locate backend folder** — `code/<backend_folder>/` inside the SPARC dataset.
2. **Validate** — `docker-compose.yml` must exist in that folder, otherwise fail.
3. **`docker compose -p <expose_name> up --build -d --force-recreate`** — with env var `PLUGIN_ROUTE_PREFIX=/plugin/<expose>` available so the plugin's compose can reference `${PLUGIN_ROUTE_PREFIX}` if it needs to know its own URL. Project name `-p <expose_name>` isolates volumes/networks per plugin and lets us tear down cleanly by name.
4. **Generate nginx location config** — `PluginDeployer.generate_nginx_conf()` writes this to `/nginx-plugins-conf/<expose>.conf` (which is the shared volume):
   ```nginx
   location /plugin/<expose>/ {
       proxy_pass http://<internal_host>:<internal_port>/;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection $connection_upgrade;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_read_timeout 86400;
   }
   ```
   `<internal_host>` is the plugin container's service name on the `digitaltwins` network; `<internal_port>` is its internal port (e.g. `8082`).
5. **Reload nginx** — `docker exec <NGINX_CONTAINER_NAME> nginx -s reload`. Nginx picks up the new file via the `include /etc/nginx/conf.d/plugins/*.conf;` directive that is baked into both `nginx.http.conf.template` and `nginx.ssl.conf.template`.
6. **Write `PluginDeployment` row** with `route_prefix`, `internal_host`, `internal_port`, `has_websocket`, `status=COMPLETED`, `up=true`.

The URL `http(s)://<host>/plugin/<expose>/…` is now live.

---

## 5. Runtime flow — user opens a plugin

1. Browser is already on `https://test.digitaltwins.auckland.ac.nz/` (portal HTML, served by nginx from `/usr/share/nginx/html`).
2. User clicks the plugin card. The portal's Vue router renders `<RemoteComponentApp src=".../<expose>.umd.js" expose="<expose_name>" />` ([RemoteComponentApp.vue](../../frontend/src/components/RemoteComponentApp.vue)).
3. `RemoteComponentApp.vue` appends a `<script>` tag with `src="https://<host>:<minio_port>/tools/<expose>/primary/<name>.umd.js"` to `document.head`.
4. The UMD bundle loads and registers itself on `window[expose_name]`.
5. The Vue component from `window[expose_name]` is mounted via `<component :is="remoteApp" />`.
6. The plugin's own code makes API calls like `fetch(import.meta.env.VITE_PLUGIN_ROUTE_PREFIX + '/some-endpoint')`. Because `VITE_PLUGIN_ROUTE_PREFIX` was baked in at build time as `/plugin/<expose>`, the request goes to `https://<host>/plugin/<expose>/some-endpoint`.
7. nginx matches `location /plugin/<expose>/ { proxy_pass http://<internal_host>:<internal_port>/; }` (loaded from `plugins/<expose>.conf`) and forwards to the plugin backend container.

No portal rebuild, no nginx image rebuild — the plugin showed up because of a MinIO upload, a `docker compose up`, a file written to a shared volume, and an `nginx -s reload`.

---

## 6. Why each design choice

| Choice | Why |
|---|---|
| UMD bundle + `<script>` loading | The only way to add new Vue components to a prebuilt SPA without rebuilding the SPA. The portal cannot know about plugins at build time. |
| `tools` bucket is **public** | The browser must fetch the UMD without credentials. All other buckets (`measurements`, `models`, `workflows`, `processes`) are private because they hold patient / research data. |
| Plugin **backend** on the shared `digitaltwins` network | nginx (inside `portal-frontend`) needs DNS resolution for the plugin container by service name. If the plugin's `docker-compose.yml` doesn't attach to this network as an external network, `proxy_pass` fails with "host not found". |
| Generated nginx `.conf` in a shared volume (instead of rebuilding the nginx image) | Zero-downtime plugin install. `nginx -s reload` only re-reads configs; the portal frontend never restarts. |
| Docker compose `-p <expose_name>` | Scopes the plugin's volumes/networks/containers under the expose name so we can delete them cleanly with `down --rmi all --volumes` and a volume prefix filter. |
| SPARC dataset as the build artifact | Interoperability with the rest of the lab's tooling; the same format is used for workflows and datasets elsewhere on the platform. |
| SQLite registry (not just "read Docker / MinIO") | We need to store plugin metadata (title, description, icon, keywords, annotation mappings) that doesn't live in Docker or MinIO. Also lets us list plugins without expensive directory walks. |
| `PLUGIN_ROUTE_PREFIX` injected at **build** time to frontend, at **deploy** time to backend | Frontend must bake it into JS (Vite env). Backend only reads it at runtime if it cares (e.g. to build self-referential URLs). |

---

## 7. Plugin contract (what plugin authors must provide)

### 7.1 Frontend (always required)

- Vue 3 + Vite project with `vite.config.(js|ts)` that builds a `lib:` entry. The builder will rewrite `name`, `formats`, `fileName` — the author just needs the `lib` block to exist and be parseable by the regex patcher.
- A build script named `build:plugin` in `package.json` (default). A custom command can be registered at plugin-install time instead.
- All API calls MUST use `import.meta.env.VITE_PLUGIN_ROUTE_PREFIX` as the base path. **No hardcoded hosts, no hardcoded ports.**
- `config.portal.json` at the repo root with plugin metadata (name, version, icon, etc.).

### 7.2 Backend (optional, only if the plugin needs a server)

- A folder with `docker-compose.yml` at its root.
- The compose service **must** attach to the external `digitaltwins` network so nginx can proxy to it:
  ```yaml
  services:
    my-plugin-backend:
      # ...
      networks:
        - digitaltwins
  networks:
    digitaltwins:
      external: true
      name: digitaltwins
  ```
- If the backend needs to know its own public URL, reference `${PLUGIN_ROUTE_PREFIX}` in the compose env — the deployer passes it in.
- If the backend needs to read `measurements`/`models` from MinIO, the compose should forward `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (from the parent `.env` via `${VAR}` substitution).

### 7.3 Plugin repo layout

```
my-plugin/
├── <frontend_folder>/          # or flat at repo root if frontend-only
│   ├── vite.config.ts
│   ├── package.json
│   └── src/
├── <backend_folder>/           # optional
│   └── docker-compose.yml
└── config.portal.json
```

---

## 8. Delete flow

Triggered by DELETE endpoint for a plugin:

1. `PluginDeployer.delete()` runs `docker compose -p <expose> down --rmi all --volumes` in the plugin's backend dir.
2. Removes `/nginx-plugins-conf/<expose>.conf`.
3. `nginx -s reload` (includes no longer match, route goes away).
4. Removes any Docker volumes whose name starts with `<expose>`.
5. Deletes the MinIO `tools/<expose>/` folder (via MinIO client in the caller).
6. Cascades delete on `Plugin` row removes `PluginBuild` and `PluginDeployment` rows.

After this the plugin is fully gone — no containers, no files, no route, no DB row.

---

## 9. Files map — what lives where

### Portal backend (`DigitalTWINS-Portal/backend/`)

| Path | Responsibility |
|---|---|
| `app/builder/build_tool.py` | `PluginBuilder`: clone → patch vite → npm install → build → SPARC → MinIO upload |
| `app/builder/deploy_tool.py` | `PluginDeployer`: compose up → write nginx conf → reload nginx; also compose down/delete |
| `app/builder/build_workflow.py` | Orchestrates build → deploy, writes to plugin registry |
| `app/models/db_model.py` | `Plugin`, `PluginBuild`, `PluginDeployment`, `PluginAnnotation` tables |
| `app/database/database.py` | DB init + auto-migration (`ALTER TABLE ADD COLUMN` for new model fields) |
| `app/client/minio.py` | MinIO client factory per bucket |

### Portal frontend (`DigitalTWINS-Portal/frontend/`)

| Path | Responsibility |
|---|---|
| `src/components/RemoteComponentApp.vue` | Dynamically `<script>`-loads a plugin UMD bundle and mounts `window[expose]` |
| `src/plugins/plugin_api.ts`, `workflow_api.ts` | Portal's own API client to the plugin registry endpoints |
| `entry.sh` | Picks HTTP or SSL nginx template at runtime based on cert presence |
| `nginx.http.conf.template` | HTTP mode (local dev), includes `plugins/*.conf` |
| `nginx.ssl.conf.template` | HTTPS mode (production), includes `plugins/*.conf` |
| `Dockerfile` | Builds both templates into the image; EXPOSE 80 443 |

### Infra (`DigitalTWINS-Portal/docker-compose.yml`)

| Service | Role in plugin system |
|---|---|
| `portal-backend` | Runs builder/deployer; needs `/var/run/docker.sock`, `nginx_plugin_configs` volume |
| `portal-frontend` | nginx host; mounts `nginx_plugin_configs` at `/etc/nginx/conf.d/plugins`; `container_name: digitaltwins-platform-portal-frontend` so backend can `docker exec` it |
| `minio` + `minio-init` | Creates the 5 buckets; sets public read on `tools` |
| Volumes: `nginx_plugin_configs`, `plugin_database`, `portal_datasets`, `minio_data` | Shared state that must survive container restarts |

---

## 10. Common misunderstandings

**"Why can't you just put the plugin routes directly in the main `nginx.conf`?"**
Because plugins are installed at runtime by end users. We don't know at image-build time which plugins will exist. The `include /etc/nginx/conf.d/plugins/*.conf;` line lets us add routes without rebuilding nginx.

**"Why does `portal-backend` have `/var/run/docker.sock` mounted — isn't that a security risk?"**
Yes, it's a significant privilege. It's there because the deployer literally runs `docker compose up` and `docker exec portal-frontend nginx -s reload`. This is a known trade-off of the self-service plugin model; in a hardened deployment this would be replaced by a privileged helper service.

**"Can plugins run outside the `digitaltwins` network?"**
No. If they don't join this network, nginx can't resolve their hostname for `proxy_pass`. The generated conf would compile (nginx defers DNS) but every request would 502. Always attach plugin backends to the external `digitaltwins` network.

**"Why is the `tools` bucket public when other buckets aren't?"**
Because the browser fetches the UMD JS bundle directly. Giving the browser MinIO credentials is worse than making the bucket public — the UMD bundle contains no secrets, only compiled frontend code. Patient data lives in the private `measurements` bucket and is only accessed by plugin backends with server-side credentials.

**"What happens if two plugins have the same frontend `expose` name?"**
`expose_name` is made unique by the builder (`unique_name()` appends a short hash). Two identical plugin repos installed twice will get distinct expose names and distinct nginx location blocks. A `window[expose_name]` collision is prevented by construction.

**"Do I need to edit the portal's main nginx template when I add a plugin?"**
No. Never. If you find yourself editing `nginx.http.conf.template` or `nginx.ssl.conf.template` to add a plugin, stop — the system is broken elsewhere. All plugin routes must come from the generated `plugins/*.conf` files.

**"Does HTTPS/HTTP mode affect plugins?"**
No. Both templates contain the same `include /etc/nginx/conf.d/plugins/*.conf;` line. The only difference is the surrounding `server { listen … }` block. Plugin routes work identically in both modes; the browser just uses whatever scheme the portal page was loaded with.

---

## 11. Quick sanity checks when plugins misbehave

| Symptom | First thing to check |
|---|---|
| Plugin card shows but clicking it loads blank | Open browser devtools → Network. Is the UMD JS fetched? (200 from MinIO?) Is `window[expose]` defined after load? |
| UMD loads but API calls 404 | `docker compose exec portal-frontend cat /etc/nginx/conf.d/plugins/<expose>.conf` — does the file exist? Is `include plugins/*.conf` still in the rendered `default.conf`? |
| API calls 502 | Plugin container isn't on `digitaltwins` network, or service name in `internal_host` doesn't match. `docker network inspect digitaltwins`. |
| Plugin install fails at build step | Check `PluginBuild.build_logs` in SQLite or backend logs. Usually vite config patch failed or `npm install` failed. |
| Plugin install fails at deploy step | Check `PluginDeployment.status` / logs. Usually the plugin's compose file is missing the `digitaltwins` external network declaration. |
| Delete "succeeded" but plugin card still visible | Registry row not cascade-deleted. Check `Plugin` table in SQLite. |

---

