# Dashboard Study View — Performance Optimisations

This document describes five performance fixes applied to the study dashboard navigation
(Programmes → Projects → Investigations → Studies → Assays). Each click previously took
several seconds due to a combination of sequential HTTP calls and missing connection reuse.

## Context and ongoing concerns

After all five fixes, performance is improved but is still considered borderline acceptable
for an application that is, at its core, fetching a small number of rows from a database
and rendering a straightforward UI.

The root cause of the sluggishness is the depth of the call chain. A single user click
traverses:

```
Browser → nginx → portal-backend → DigitalTWINS API → postgres Querier → PostgreSQL
                                                     → SEEK Querier     → SEEK (Rails → MySQL)
```

That is five to six network hops to return what is essentially a handful of rows. Each
layer was built independently without visibility into what the surrounding layers were
doing, which is how sequential-within-sequential call patterns and fresh connections at
every layer went unnoticed.

**The fixes in this document address the worst of the plumbing issues, but do not change
the fundamental architecture.** If performance continues to be a concern, the developers
should consider:

- **Caching at the portal-backend level** — currently caching only exists in the
  DigitalTWINS API's SEEK Querier. Adding a cache at the portal-backend would eliminate
  the DigitalTWINS API hop entirely for warm navigations.
- **Collapsing layers** — the portal-backend → DigitalTWINS API boundary adds a full
  HTTP round-trip for every query. If these services are always co-located, merging them
  or moving to direct library calls would remove that hop.
- **A PostgreSQL connection pool** — `psycopg2.pool.ThreadedConnectionPool` in the
  postgres Querier would avoid opening a fresh connection per query.

This is flagged here because the integrating team considers this level of latency
unacceptable for the use case, and believes the developers should be aware of the
architectural debt before the application is used in a production research context.

---

## Fix 1 — Parallel child fetches in `category-children` (backend)

**File:** `services/portal/DigitalTWINS-Portal/backend/app/router/dashboard.py`

Each time the user drills down a level, the backend fetched each child object from the
DigitalTWINS API one at a time in a `for` loop. For a study with N assays that meant N+1
sequential HTTP requests, each waiting for the previous to complete.

**Fix:** Extracted the per-child fetch into an inner coroutine and replaced the loop with
`asyncio.gather()`, so all child fetches fire in parallel. Latency now scales with the
slowest single fetch rather than the sum of all fetches.

---

## Fix 2 — Parallel assay detail loading (frontend)

**File:** `services/portal/DigitalTWINS-Portal/frontend/src/views/dashboard/study-dashboard/index.vue`

When navigating to the Assays level, the frontend loaded each assay's config details
sequentially — the function was literally named `loadSequentially`. Each
`useDashboardGetAssayConfigDetails` call awaited the previous before starting.

**Fix:** Replaced the sequential loop with `Promise.all()` so all assay detail requests
fire concurrently.

---

## Fix 3 — Shared HTTP connection pool (portal backend)

**Files:**
- `services/portal/DigitalTWINS-Portal/backend/app/client/digitaltwins_api.py`
- `services/portal/DigitalTWINS-Portal/backend/app/main.py`
- `services/portal/DigitalTWINS-Portal/backend/app/router/dashboard.py`

`DigitalTWINSAPIClient` created a new `httpx.AsyncClient()` on every API request and closed
it when the request finished. Every call to the DigitalTWINS API paid the full cost of a
TCP handshake.

**Fix:** A single shared `httpx.AsyncClient` is created at app startup via the FastAPI
lifespan and stored on `app.state`. `DigitalTWINSAPIClient` accepts this shared client,
giving proper connection pooling and keep-alive across the life of the application. The
client is cleanly shut down when the app stops.

> **Note:** Because the portal backend and DigitalTWINS API run on the same Docker network,
> TCP setup between them is near-zero and the impact of this fix is modest. It is still
> correct practice and becomes more significant if the services are ever separated.

---

## Fix 4 — Connection reuse and response caching in the SEEK Querier

**File:** `services/api/digitaltwins-api/src/digitaltwins/seek/querier.py`

This was the primary source of latency. Every call to `get_program()`, `get_project()`,
etc. used `requests.get()` directly rather than a `requests.Session()`, opening a new TCP
connection to SEEK (a Ruby on Rails + MySQL application) for each call. There was also no
caching — every dashboard navigation forced a full round-trip to SEEK regardless of whether
the data had changed.

**Fix:** Replaced all bare `requests.get()` calls with a single `requests.Session()`
created in `__init__`, so TCP connections to SEEK are reused. Added a URL-keyed in-memory
TTL cache (default 60 seconds) so repeated navigation within the same session is served
from memory. The TTL is controlled by the `_CACHE_TTL` constant at the top of the file.

The cache is appropriate here because SEEK hierarchy data (programmes, projects,
investigations, studies) changes infrequently — only when researchers deliberately update
it.

### Cache invalidation

The cache lives in the Python process inside the `digitaltwins-api` container. A browser
hard-refresh does **not** clear it. To force an immediate refresh after making changes in
SEEK, call the cache-busting endpoint:

```bash
curl -X POST https://test.digitaltwins.auckland.ac.nz/api/cache/clear \
  -H "Authorization: Bearer <token>"
```

Response confirms how many entries were cleared:

```json
{"cleared": 12}
```

This endpoint requires a valid bearer token (same credentials as other API calls). It is
also available via the interactive API docs at `/docs` on the DigitalTWINS API.

To adjust the TTL, edit `_CACHE_TTL` in `seek/querier.py` and rebuild the
`digitaltwins-api` container:

```bash
docker compose up -d --build digitaltwins-api
```

---

## Fix 5 — Race condition in PostgreSQL Querier (cursor already closed)

**File:** `services/api/digitaltwins-api/src/digitaltwins/postgres/querier.py`

**Confirmed via:** `digitaltwins-api` container logs — `psycopg2.InterfaceError: cursor already closed`

The `postgres/Querier` singleton stored its active database connection and cursor as
instance variables (`self._conn`, `self._cur`). This was safe when requests were
sequential, but the `Promise.all()` fix (Fix 2) caused multiple concurrent calls to
`get_assay(get_configs=True)` to share the same singleton simultaneously:

1. Request A calls `_connect()` → sets `self._cur`
2. Request B calls `_connect()` → overwrites `self._cur` with a new cursor
3. Request A calls `_disconnect()` → closes B's cursor
4. Request B attempts to use `self._cur` → **cursor already closed**

There was also a secondary latent bug: `_format_results()` read `self._cur.description`
after `_disconnect()` had already closed the cursor — this only worked by accident because
psycopg2 retains the description on a closed cursor.

**Fix:** Removed `self._conn` and `self._cur` as instance state entirely. Connection and
cursor are now local variables within `_query()`, created and cleaned up within a
`try/finally` block on every call. Each concurrent request gets its own independent
connection. `_format_results()` now receives the cursor as a parameter rather than reading
instance state.

> **Note:** This fix opens a new PostgreSQL connection per query. A connection pool
> (`psycopg2.pool.ThreadedConnectionPool`) would be the next improvement if query volume
> warrants it, but is not necessary at current load.

---

## Rebuild reference

| Fix | Service | Rebuild command |
|-----|---------|----------------|
| 1, 2 | `portal-backend`, `portal-frontend` | `docker compose up -d --build portal-backend portal-frontend` |
| 3 | `portal-backend` | `docker compose up -d --build portal-backend` |
| 4, 5 | `digitaltwins-api` | `docker compose up -d --build digitaltwins-api` |

All commands run from `~/twins/digitaltwins-platform`.
