# Release Notes

## 2026-05-07 — Workflow `/workflows/...` MinIO direct-link removed

Replaced the legacy direct-MinIO URL for workflow build artifacts with a backend-mediated streaming proxy. The old URL (`http(s)://<host>:<MINIO_PORT>/workflows/<expose>/primary/...`) depended on MinIO's port 9000 being published to the host — a dependency that was already removed for the public `tools` bucket but left in place for `workflows`. With this change the deployment no longer needs to publish 9000 / 9001, and the `workflows` bucket stays fully private.

**No action required for portal operators.** Pulling the new portal image and restarting `portal-backend` is sufficient — the change lives entirely in `workflow_router.py`.

**Breaking changes for external consumers of `/api/workflow/metadata`:**

- The `path` field shape has changed from `<protocol>://<host>:<minio_port>/workflows/<expose>/primary` to `<protocol>://<host>/api/workflow/<expose>/primary` (no MinIO port; default 80/443 through portal-frontend nginx → portal-backend).
- Object reads now hit `GET /api/workflow/<expose>/primary/<path>`, which streams the object from the private MinIO bucket through FastAPI. Anyone hardcoding the old `host:port/workflows/...` shape must update their fetch URL.
- Errors: `404` for missing object, `503` for MinIO transport failures, `200` with `Content-Type` derived from the object's stored MIME type (or `mimetypes.guess_type(path)`, falling back to `application/octet-stream`).
- `Cache-Control: public, max-age=300` on responses (5-minute browser cache; conservative because expose names can be reused across rebuilds).

**Internal Vue frontend is unaffected** — `frontend/src/bootstrap/workflow_api.ts` does not consume the metadata endpoint, and the local-source CWL viewer (`/api/workflow/{id}/cwl`) reads from the staging directory, not MinIO.

See [`../plan/02-PLAN-workflow-router-minio-proxy.md`](../plan/02-PLAN-workflow-router-minio-proxy.md) for the full design and rationale.

## 2026-05-07 — Plugin state isolation

Fixed cross-plugin data leakage caused by all plugins sharing the portal's single Pinia instance. Each plugin mount now gets its own Vue app + Pinia, torn down on exit; same source registered under two `expose` names — or two different plugins with same-named stores — no longer pollute each other.

**No action required for portal operators.** Pulling the new portal image and restarting `portal-frontend` / `portal-backend` is sufficient — the fix lives entirely on the host side.

**Breaking changes for plugin authors:**

- **`persist: true` on plugin stores no longer persists.** `pinia-plugin-persistedstate` is intentionally not registered on the per-mount Pinia. If your plugin needs durable state, write to `localStorage` directly using `import.meta.env.VITE_PLUGIN_ROUTE_PREFIX` as the key namespace (e.g. ``localStorage.setItem(`${import.meta.env.VITE_PLUGIN_ROUTE_PREFIX}:draft`, ...)``).
- **Plugin state is per-mount.** Opening, closing, and reopening a plugin always starts from a blank store — same as closing and reopening a SPA tab. Treat plugin state as session-scoped to the open tab.
- **Module-level global side effects are now repeated on every mount.** UMD bundles are re-executed each time the plugin opens, so `document.addEventListener(...)` / `window.X = ...` / global subscriptions written at module top-level will be re-registered each open and never torn down. Move them into `onMounted` and pair with `onBeforeUnmount` cleanup.
- **`vite.config.{js,ts}` must externalize the four host-shared libraries.** `rollupOptions.external` must include `'vue'`, `'pinia'`, `'vuetify'`, `'vue-toastification'`, with matching `output.globals` (`Vue`, `Pinia`, `Vuetify`, `VueToastification`). The builder now refuses to build a plugin that does not satisfy this — without it the per-app Pinia isolation silently breaks.
- **`defineStore` IDs are auto-namespaced at build time.** The builder injects a `portal-plugin-store-namespace` Vite plugin that rewrites every literal `defineStore('foo', ...)` to `defineStore('<expose>__foo', ...)` during transform. Use plain string literals — non-literal IDs (`defineStore(useFooId, ...)` / template-literal IDs) bypass the rewrite and rely solely on the per-app Pinia for isolation.

**No rebuild required to pick up the main fix** — the Pinia isolation lives entirely on the portal side.

**Recommended rebuild** to pick up the secondary safeguard (`<expose>__` store-id prefix). Plugin authors can trigger a rebuild from the portal's plugin list page; the bundle URL's `?v=<build_ts>` cache-buster will advance automatically and clients pick up the new bundle on next mount with no `Ctrl+Shift+R` needed. Already-deployed plugins keep working without a rebuild.

See [`../plan/01-PLAN-plugin-state-isolation.md`](../plan/01-PLAN-plugin-state-isolation.md) for the full design and rationale.
