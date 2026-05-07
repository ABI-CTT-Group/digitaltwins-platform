# Release Notes

## 2026-05-07 — Builder dev-mount fallback removed; `source_type` strictly enforced

Removed the long-deprecated dev-mount source path from the plugin and workflow build pipelines. Step 1 of `build_tool.py` and `build_workflow.py` now accepts exactly two `source_type` values — `github` and `local` — with an explicit `ValueError` for anything else. The dev-mount fallback (matching `./plugins/<name>` / `/plugins/<name>` / `./workflow/<name>` / `/workflow/<name>` and resolving against unmounted host paths) was already unreachable in production (no volume bound in `docker-compose.yml`, frontend regex blocked non-git URLs) and is now physically gone, along with its dead-code companions: the `is_git_url` helper, all permanently-true `if cloned_dir:` gates, the unreachable `else:` branches, the misleading "only for cloned repos / only for remote repos" comments, and the `is_local` field in the builder return dict.

**No action required for portal operators.** Pre-existing DB records were audited (`SELECT ... WHERE repository_url NOT LIKE 'http%' AND NOT LIKE 'local://%'` returned 0 rows in both `plugins` and `workflows` tables). Pulling the new portal image and restarting `portal-backend` is sufficient.

**Internal renames:**

- The local variable `cloned_dir` in both builders is now `tmp_source_dir` — both `github` and `local` branches assign it (previous semantics implied "this came from a clone," which was misleading for local-upload paths).

**Breaking changes for direct API callers / external integrators:**

- `POST /api/tools/create` and `POST /api/workflow/create` with a `source_type` value other than `"github"` or `"local"` now fail-fast with `ValueError` (previously fell through to a dead dev-mount branch that would `RuntimeError` on the missing `/plugins/...` path). This only affects callers that bypass the Pydantic `Literal["github", "local"]` validator — e.g., callers writing directly to the DB or to unvalidated internal call sites.
- The build response dict no longer includes an `is_local` key. The internal `build_record` writer ([`builder_utils.py`](../backend/app/utils/builder_utils.py)) and the `/api/.../metadata` endpoints never read this key (they recompute from `latest_build.s3_path is None`); no in-tree consumer is affected. External consumers reading the build response directly should switch to `s3_path is None` if they need an equivalent signal.
- The `is_git_url` helper in [`backend/app/utils/builder_utils.py`](../backend/app/utils/builder_utils.py) has been removed.

**No frontend impact** — `clinical-dashboard/frontend/` had zero references to `is_local` or `is_git_url`, and the production registration form's `githubRepoRegex` already rejected non-git URLs.

See [`../plan/03-PLAN-deprecate-dev-mount.md`](../plan/03-PLAN-deprecate-dev-mount.md) for the full context.

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
