# How the plugin system works

How the platform builds, deploys, routes and removes GUI tools (plugins), for people working on the
builder, the portal or the gateway. To write a GUI tool and bring it into the platform, read
[gui-tool-authoring.md](gui-tool-authoring.md) instead.

The code is in `services/builder/app/engine/`, `services/builder/app/models/db_model.py`,
`services/portal/frontend/src/components/RemoteComponentApp.vue` and
`services/portal/frontend/nginx.conf.template`. Terms such as *plugin*, *GUI tool* and *expose name* are
in the [glossary](glossary.md).

---

## 0. One-minute summary

A **plugin** is a built GUI tool: a Vue frontend plus an optional Docker backend, which the platform
installs at runtime, with no portal rebuild and no hand-edited nginx config.

1. The builder **builds** the tool's Vue source into a single UMD JS file.
2. It **stores** that bundle in MinIO's public-read `tool-builds` bucket, so the browser can
   `<script src=…>` it. Once the build is approved, the platform API ingests it into the `tools` bucket under
   the tool's dataset UUID, and the portal loads it from there.
3. On the tool's first launch, the builder **deploys** its backend containers onto the shared Docker network.
4. It **writes** an nginx `location /plugin/<expose>/ { proxy_pass … }` snippet into a shared volume and
   reloads nginx, so `https://<host>/plugin/<expose>/` routes to that backend.

The rest of this page is the detail behind those four steps.

---

## 1. Moving parts

| Part | What it is |
|---|---|
| **UMD bundle** | A single JS file that registers itself on `window[<expose>]` when loaded with `<script>`. The portal loads it to mount the tool's Vue app. |
| **`tool-builds` and `tools` buckets** | The only public-read MinIO buckets. `tool-builds/<expose>/` holds builds not yet approved; `tools/<dataset_uuid>/` holds approved tools. Both hold compiled frontend code only. |
| **Platform network** | The Docker network `${PROJECT_NAME}` (default `digitaltwins-platform`), shared by the builder, portal-frontend and every plugin backend. nginx resolves `proxy_pass http://<plugin-container>:<port>/` over it. |
| **`nginx_plugin_configs` volume** | Mounted into the builder at `/nginx-plugins-conf` and into portal-frontend at `/etc/nginx/conf.d/plugins`. The builder writes route files; nginx reads them. |
| `PLUGIN_ROUTE_PREFIX` | `/plugin/<expose>`. Written into the tool frontend's `.env` at build time (as `VITE_PLUGIN_ROUTE_PREFIX`) and passed to the backend's compose at deploy time. |

---

## 2. The four planes

```
┌──────────────────────────────────────────────────────────────────────┐
│                              Browser                                  │
│  ┌───────────────────┐    ┌──────────────────────────────────────┐   │
│  │   portal HTML     │    │ <script src="/tool-builds/…/my-app.  │   │
│  │   (Vue SPA)       │    │  umd.js"> or /tools/…, at runtime ◄(A)│   │
│  └────────┬──────────┘    └───────────────────┬──────────────────┘   │
│           │ /api/builder/…                     │ /plugin/<name>/…     │
└───────────▼────────────────────────────────────▼─────────────────────┘
            │                                    │
    ┌───────┴────────────────────────────────────┴────────┐
    │                 nginx (portal-frontend)              │
    │   /api/builder/   →  builder:8000                   │
    │   /tool-builds/, /tools/ →  MinIO                   │
    │   /plugin/<name>/ →  <plugin-container>:<port> ◄(D) │
    │   include /etc/nginx/conf.d/plugins/*.conf          │
    └───────┬─────────────────────────────────┬───────────┘
            │                                 │
    ┌───────▼──────────┐             ┌────────▼──────────┐
    │  builder         │             │  plugin-backend   │
    │  (FastAPI)       │             │  (Docker compose) │
    │  engine/         │             │  must join the    │
    │  - build_tool    │             │  platform network │
    │  - deploy_tool   │             │                   │
    └──┬──────┬────┬───┘             └───────────────────┘
       │      │    │
     write  write  write
       │      │    │
  ┌────▼─────┐ ┌▼────────────┐ ┌───────▼──────────────┐
  │ MinIO    │ │  Postgres   │ │  nginx_plugin_       │
  │tool-     │ │  `portal`   │ │  configs volume      │
  │builds/   │ │  schema     │ │  /conf.d/plugins/    │
  │(public   │ │ Plugin /    │ │  <expose>.conf       │
  │ read)    │ │ PluginBuild │ │  (read by nginx      │
  │  ◄(A)    │ │ Deployment  │ │   include directive) │
  └──────────┘ └─────────────┘ └──────────────────────┘
```

Arrow legend:
- **(A)**: the browser fetches the tool's UMD bundle from a public-read bucket, through portal-frontend's nginx.
- **(D)**: nginx reloads the `plugins/*.conf` includes after each deploy.

The **four persistence planes**:

| Plane | Storage | What it holds |
|---|---|---|
| **1. Plugin frontend assets** | MinIO `tool-builds/<expose>/` before approval, `tools/<dataset_uuid>/` after (both public read) | The UMD bundle and the tool's other built assets, in an SDS dataset |
| **2. Plugin backend runtime** | Docker, on the platform network | The running plugin backend containers |
| **3. Routing config** | `nginx_plugin_configs` volume | One `.conf` per plugin, loaded by `include` in portal-frontend's nginx |
| **4. Registry** | The `portal` schema in the platform Postgres (`database` service). SQLite on the `plugin_database` volume only when the builder runs standalone | `Plugin`, `PluginBuild`, `PluginDeployment` rows (and the workflow equivalents): the builder's record of what's built and deployed |

---

## 3. Build pipeline (`PluginBuilder` in `services/builder/app/engine/build_tool.py`)

Triggered by the build endpoint of a registered tool. A gui workflow's single tool is built the same way, by
`services/builder/app/engine/build_workflow.py`. Steps:

1. **Resolve source**: clone the Git repository, or use the uploaded archive the builder staged at
   registration (`local_archive_path`, under the builder's `tmp/`). That staged copy doesn't survive the
   builder container being recreated, and a rebuild of a local-source tool needs it. For an SDS package, the
   source is its `code/` folder.
2. **Patch `vite.config.(js|ts)`**: forces `lib.formats = ['umd']`, renames `lib.name` to the expose name, and
   sets `fileName`, so the output is one predictable bundle that registers itself on `window[<expose>]`.
3. **Write `.env`** in the frontend folder with `VITE_PLUGIN_ROUTE_PREFIX=/plugin/<expose>` (tools with a
   backend only). Vite embeds it at build time, so the tool's own API calls go through `/plugin/<expose>/…`,
   which nginx proxies.
4. **`npm install --force` + build**: runs `npm run build:plugin` by default, or the build command registered
   with the tool. Output appears in `dist/`.
5. **Check `config.portal.json`**: if the source has one, it must be valid JSON, or the build fails. Its
   fields aren't used; the registration form supplies the tool's name, folders and commands.
6. **Rewrite UMD asset paths**: embedded `http(s)://<host>:<minio_port>/…/<expose>/primary/` prefixes become
   the expose name, because the final MinIO URL isn't known at build time in every environment.
7. **Create the SDS dataset**: copies `code/` (source) and `primary/` (the `dist` output) into an SDS dataset
   folder with sparc-me.
8. **Upload it to MinIO `tool-builds/<expose>/`**, a public-read bucket, so the browser can load the bundle
   without credentials while the build is tested.
9. **Clean up** the temporary clone, and **write the registry rows**: `PluginBuild` with its logs, paths,
   expose name and status.

After this the tool can be launched from the Tool Hub, but it has no backend running and no nginx route yet.
**Approving** the build hands it to the platform API, which registers it in SEEK and ingests it as a tool
dataset into `tools/<dataset_uuid>/`; the portal then loads the approved bundle from there.

---

## 4. Deploy pipeline (`PluginDeployer` in `services/builder/app/engine/deploy_tool.py`)

Runs for tools with a backend folder the first time the tool is launched (see §5), or when its last deploy
failed. Steps:

1. **Locate the backend folder**: `code/<backend_folder>/` inside the SDS dataset.
2. **Validate**: `docker-compose.yml` must exist in that folder, otherwise fail.
3. **`docker compose -p <expose> up --build -d --force-recreate`**, with `PLUGIN_ROUTE_PREFIX=/plugin/<expose>`
   in the environment so the compose file can use `${PLUGIN_ROUTE_PREFIX}`. The project name `-p <expose>`
   isolates volumes and networks per plugin and lets them be removed by name. Compose interpolates against the
   builder's own environment, not the platform `.env` (the pass-through block in
   `services/builder/docker-compose.yml`).
4. **Generate the nginx location**: `PluginDeployer.generate_nginx_conf()` writes this to
   `/nginx-plugins-conf/<expose>.conf` (the shared volume):
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
   `<internal_host>` is the plugin container's service name on the platform network; `<internal_port>` is its
   internal port (e.g. `8082`).
5. **Reload nginx**: `docker exec <NGINX_CONTAINER_NAME> nginx -s reload`. nginx picks up the new file through
   the `include /etc/nginx/conf.d/plugins/*.conf;` directive in `nginx.conf.template`.
6. **Write the `PluginDeployment` row** with `route_prefix`, `internal_host`, `internal_port`,
   `has_websocket`, `status=COMPLETED`, `up=true`. Each build has one such row; a redeploy reuses it, and a
   failed deploy stores its reason in `error`.

The URL `http(s)://<host>/plugin/<expose>/…` is now live.

---

## 5. Runtime flow: a user opens a plugin

1. The browser is on the portal (`https://<host>/`), served by portal-frontend's nginx.
2. The user clicks Launch on the Tool Hub card, or on a gui assay. Both open `/tool-view`, which first calls
   `POST /api/builder/tools/backend/<expose>/start` and polls `GET /api/builder/tools/backend/<expose>` until
   the backend is `running` (or the tool has none). The builder runs `docker compose -p <expose> up -d` on the
   build's existing deployment, or the deploy pipeline (§4) when there is none. Any signed-in user can trigger
   this; an admin can stop a backend from the card's menu
   ([ADR](decisions/2026-11-05-start-gui-backends-on-launch.md)).
3. `/tool-view` renders
   [`RemoteComponentApp`](../services/portal/frontend/src/components/RemoteComponentApp.vue) with the bundle's
   path and expose name.
4. `RemoteComponentApp.vue` appends a `<script>` tag to `document.head` with the bundle's path:
   `/tool-builds/<expose>/primary/my-app.umd.js` for a build not yet approved, or
   `/tools/<dataset_uuid>/primary/my-app.umd.js` once approved.
5. The UMD bundle loads and registers itself on `window[<expose>]`.
6. The Vue component from `window[<expose>]` is mounted in its own Vue app. When `/tool-view` was opened from
   a gui assay, the app is given `provide('launchContext', …)`: the assay's cohort and input files
   ([guide](gui-tool-authoring.md), [ADR](decisions/2026-11-12-gui-tool-launch-context.md)).
7. The tool's own code calls its API at `import.meta.env.VITE_PLUGIN_ROUTE_PREFIX + '/some-endpoint'`. That
   was baked in at build time as `/plugin/<expose>`, so the request goes to
   `https://<host>/plugin/<expose>/some-endpoint`.
8. nginx matches `location /plugin/<expose>/ { proxy_pass http://<internal_host>:<internal_port>/; }` (from
   `plugins/<expose>.conf`) and forwards to the plugin backend container.

No portal rebuild and no nginx image rebuild: the tool appeared because of a MinIO upload, a
`docker compose up`, a file written to a shared volume, and an `nginx -s reload`.

---

## 6. Why each design choice

| Choice | Why |
|---|---|
| UMD bundle + `<script>` loading | The only way to add new Vue components to a prebuilt SPA without rebuilding it. The portal can't know about plugins at build time. |
| `tool-builds` and `tools` are **public read** | The browser must fetch the UMD without credentials. All other buckets (`measurements`, `models`, `workflows`, `airflow-workspace`) are private because they hold patient or research data. |
| Plugin **backend** on the shared platform network | nginx (inside `portal-frontend`) needs DNS resolution for the plugin container by service name. If the plugin's `docker-compose.yml` doesn't attach to this network as an external network, `proxy_pass` fails with "host not found". |
| Generated nginx `.conf` in a shared volume (instead of rebuilding the nginx image) | Zero-downtime plugin install. `nginx -s reload` only re-reads configs; portal-frontend never restarts. |
| Docker compose `-p <expose>` | Scopes the plugin's volumes, networks and containers under the expose name, so they can be removed cleanly with `down --rmi all --volumes` and a volume prefix filter. |
| An SDS dataset as the build artifact | The same format every platform dataset uses, so an approved build becomes a tool dataset like any other. |
| A database registry (not just "read Docker / MinIO") | Plugin metadata (title, description, annotation mappings) doesn't live in Docker or MinIO, and listing plugins shouldn't need directory walks. |
| `PLUGIN_ROUTE_PREFIX` injected at **build** time to the frontend, at **deploy** time to the backend | The frontend must bake it into JS (Vite env). The backend reads it at runtime only if it needs it (e.g. to build self-referential URLs). |

---

## 7. What plugin authors must provide

See [gui-tool-authoring.md](gui-tool-authoring.md): the SDS package, the frontend and backend contract, and
registration.

---

## 8. Delete flow

Deleting a tool or workflow in the portal:

1. `PluginDeployer.delete()` runs `docker compose -p <expose> down --rmi all --volumes` in the plugin's backend
   folder.
2. Removes `/nginx-plugins-conf/<expose>.conf`.
3. `nginx -s reload`, so the route goes away.
4. Removes any Docker volumes whose name starts with `<expose>`.
5. Deletes each build's bundle from `tool-builds`. If the item was approved, the builder asks the platform API
   to delete its dataset (and, for a workflow, its tools), which removes it from SEEK and from `tools/`.
6. Deletes the registry rows: the `Plugin` (or workflow) row and its builds and deployments.

After this the tool is gone: no containers, no files, no route, no registry rows.

---

## 9. Files map: what lives where

### Builder (`services/builder/app/`)

| Path | Responsibility |
|---|---|
| `engine/build_tool.py` | `PluginBuilder`: fetch source → patch vite → npm install → build → SDS dataset → `tool-builds` upload |
| `engine/build_workflow.py` | Builds a gui workflow's single tool with `PluginBuilder` |
| `engine/deploy_tool.py` | `PluginDeployer`: compose up → write nginx conf → reload nginx; also compose down and delete |
| `models/db_model.py` | `Plugin`, `PluginBuild`, `PluginDeployment`, `PluginAnnotation` and the workflow tables |
| `database/` | DB init, and schema changes as numbered SQL files in `migrations/` |
| `client/minio.py` | MinIO client factory per bucket |

### Portal frontend (`services/portal/frontend/`)

| Path | Responsibility |
|---|---|
| `src/views/tool-plugin/tool-plugin-view.vue` | `/tool-view`: starts the backend, loads a gui assay's launch context, mounts the tool |
| `src/components/RemoteComponentApp.vue` | `<script>`-loads a plugin's UMD bundle, mounts `window[<expose>]` and provides the launch context |
| `src/bootstrap/tool_api.ts`, `workflow_api.ts` | The portal's API clients for the builder's endpoints |
| `nginx.conf.template` | portal-frontend's only nginx config. HTTP only; TLS terminates at the platform gateway. Proxies `/tools/` and `/tool-builds/` to MinIO and includes `plugins/*.conf` |
| `Dockerfile` | Copies the template to `/etc/nginx/templates/`, where the stock nginx entrypoint renders it with `envsubst`; EXPOSE 80 |

### Infra

| Where | Role in the plugin system |
|---|---|
| `services/builder/docker-compose.yml` | Runs the builder; mounts `/var/run/docker.sock` and the `nginx_plugin_configs` volume; holds the variables plugin compose files can interpolate |
| `services/portal/docker-compose.yml` | `portal-frontend`: mounts `nginx_plugin_configs` at `/etc/nginx/conf.d/plugins`; `container_name: ${PROJECT_NAME}-portal-frontend` so the builder can `docker exec` it |
| `services/minio/init-minio.sh` | Creates the buckets; sets `tools` public and `tool-builds` to anonymous download |
| Root `docker-compose.yml` volumes: `nginx_plugin_configs`, `portal_datasets`, `plugin_database` (SQLite fallback and migration source) | Shared state that must survive container restarts |

---

## 10. Common misunderstandings

**"Why can't you just put the plugin routes directly in the main `nginx.conf`?"**
Because plugins are installed at runtime by end users. Which plugins exist isn't known when the image is
built. The `include /etc/nginx/conf.d/plugins/*.conf;` line adds routes without rebuilding nginx.

**"Why does the `builder` have `/var/run/docker.sock` mounted? Isn't that a security risk?"**
Yes, it's a significant privilege: root on the host. It's there because the deployer runs `docker compose up`
and `docker exec portal-frontend nginx -s reload`, and builds run the plugin's own `npm` scripts next to it.
That's why the builder runs as its own service, apart from the platform API, with a minimal environment (no
API credentials) and the only socket mount (see
[2026-10-21-builder-as-its-own-service.md](decisions/2026-10-21-builder-as-its-own-service.md)). Builds aren't
sandboxed yet; in a hardened deployment they would run against an isolated Docker daemon or a privileged
helper service.

**"Can plugins run outside the platform network?"**
No. If they don't join it, nginx can't resolve their hostname for `proxy_pass`. The generated conf would
load (nginx defers DNS) but every request would 502. Always attach plugin backends to the external platform
network.

**"Why are `tools` and `tool-builds` public when other buckets aren't?"**
Because the browser fetches the UMD bundle directly. Giving the browser MinIO credentials would be worse
than a public-read bucket: the bundle holds no secrets, only compiled frontend code. Patient data stays in
private buckets: the browser reads an assay's input files through the API's file proxy (the launch context's
`url`), and plugin backends read them with server-side credentials.

**"What happens if two plugins have the same frontend `expose` name?"**
The builder makes the expose name unique (`unique_name()` appends a short hash). The same repository
installed twice gets two expose names and two nginx location blocks, so `window[<expose>]` can't collide.

**"Do I need to edit the portal's main nginx template when I add a plugin?"**
No, never. If you find yourself editing `nginx.conf.template`, or the platform gateway's config, to add a
plugin, stop: the system is broken elsewhere. All plugin routes come from the generated `plugins/*.conf`
files.

**"Does HTTP or HTTPS mode affect plugins?"**
No. TLS terminates at the platform gateway, and portal-frontend's one HTTP-only template includes
`plugins/*.conf` either way. The browser uses whatever scheme the portal page was loaded with.

---

## 11. Quick sanity checks when plugins misbehave

| Symptom | First thing to check |
|---|---|
| The tool opens blank | Browser devtools → Network: is the UMD bundle fetched (200 from `/tool-builds/` or `/tools/`)? Is `window[<expose>]` defined after it loads? |
| The bundle loads but API calls 404 | `docker compose exec portal-frontend cat /etc/nginx/conf.d/plugins/<expose>.conf`: does the file exist? Is `include plugins/*.conf` still in the rendered `default.conf`? |
| API calls 502 | The plugin container isn't on the platform network, or `internal_host` doesn't match its service name. `docker network inspect digitaltwins-platform` (the network is named after `PROJECT_NAME`). |
| The build fails | `PluginBuild.build_logs` in the registry (`portal` schema), or the builder logs. Usually the vite config patch, `npm install`, or a malformed `config.portal.json`. |
| The deploy fails | `PluginDeployment.status` and `error`, shown in `/tool-view`. Usually the plugin's compose file is missing the external network declaration. |
| A deleted tool's card is still visible | The registry row wasn't deleted. Check the `Plugin` table in the registry (`portal` schema). |
