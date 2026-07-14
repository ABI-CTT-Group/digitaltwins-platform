# Platform Edge Gateway

The platform's front door. Owns host ports 80/443 and TLS, routes the platform
services, and hands everything else to the portal.

**The config is a set of bind-mounted plain files. Changing a route needs no image
rebuild and no container restart.** That is the whole point of this directory.

---

## Change a route, an upstream, a timeout, a body size

Edit `snippets/platform-routes.conf`, then:

```bash
docker exec digitaltwins-platform-gateway nginx -t        # check syntax — don't skip
docker exec digitaltwins-platform-gateway nginx -s reload # live in milliseconds
```

A failed `nginx -t` is safe: `reload` refuses a broken config and the running nginx
keeps serving the old one.

## Change TLS, the certificate, or the domain

Edit `conf/ssl/default.conf` — cert paths and `server_name` are written as plain
literals precisely so you can edit them. Then reload as above.

Certificates go in **`certs/`** (this directory). That is the default `SSL_CERT_DIR`
in the root `.env`; point it elsewhere for a real deployment, e.g.
`/etc/letsencrypt/live/<domain>`. The gateway is the only service that reads them —
the portal no longer terminates TLS at all.

```
services/nginx/certs/
├── server.crt      # ← name them this, or edit the two ssl_certificate lines
└── server.key
```

`*.crt` / `*.key` / `*.pem` are gitignored here. **Never commit a private key.**

## Switch between HTTP and HTTPS

Set `NGINX_MODE` in the root `.env` to `http` or `ssl`, then:

```bash
docker compose up -d gateway    # seconds, no image build
```

**Also check `SSL` in the root `.env`.** The two are different questions:

| Variable | Question it answers | Owner |
|---|---|---|
| `SSL` | What scheme do browsers reach us on? (portal-backend puts it in generated URLs) | the app |
| `NGINX_MODE` | Does this gateway terminate TLS itself? | the edge |

Normally they agree (`SSL=true` → `NGINX_MODE=ssl`). They diverge when TLS is
terminated by a load balancer **in front of** this gateway: then it is `SSL=true`
with `NGINX_MODE=http` — public HTTPS, plain HTTP arriving here.

---

## Layout

```
services/nginx/
├── conf/
│   ├── http/default.conf     # server shell: listen 80, no TLS
│   └── ssl/default.conf      # server shell: 80→301 + 443 ssl   ← edit certs/domain here
├── snippets/
│   ├── http-level.conf       # resolver + map (http{} context — NOT locations)
│   ├── platform-routes.conf  # ← the file you will edit most
│   └── portal-fallback.conf  # location / → portal-frontend. Read before touching.
└── certs/                    # TLS certs (gitignored). Default SSL_CERT_DIR.
```

`conf/http` and `conf/ssl` are **only server shells**. Both `include` the *same*
snippets, so a route is written once and is automatically correct in both modes.

That structure exists to kill a specific bug: in the old portal config, `/seek` and
`/airflow` were defined **only in the SSL template** and were silently missing from
the HTTP one. One copy, two shells, no drift.

---

## Two things that will bite you

**1. Every `proxy_pass` goes through a `set $var`. Keep it that way.**

nginx resolves a literal `proxy_pass http://seek:3000` at *config parse time*. If
`seek` isn't running, nginx **refuses to start** — and that takes the entire edge
down, portal included. One optional service being off would make the whole platform
unreachable.

Routing through a variable (with the `resolver` in `http-level.conf`) defers the
lookup to request time: a missing upstream becomes a 502 on that one route, and
nothing else notices.

The catch: with a variable, nginx no longer strips the location prefix for you. A
trailing slash on `proxy_pass` does **not** rewrite the path — it sends a literal
`/` for every request. Where you need the strip, use `rewrite ... break` (see
`/minio-console/` for the pattern).

**2. `snippets/portal-fallback.conf` is not boilerplate.**

Its `proxy_buffering off`, `client_max_body_size 0`, and `Upgrade`/`Connection`
headers are load-bearing. Drop any of them and three things break *silently* — no
error, no log line:

- SSE build logs stop streaming and arrive in one delayed burst at the end
- Uploads over 1 MB fail with 413 at the edge
- Plugin WebSockets fail to handshake

The edge is a transparent pipe **on purpose**. The real upload ceiling lives in
portal-frontend (`MAX_UPLOAD_MB` / `MAX_PART_SIZE_MB`) — the layer that knows what
the limit means and can return a coherent error.

---

## What is not yours

`/`, `/api/`, `/tools/`, `/plugin/*` belong to the **portal** (nginx inside the
`portal-frontend` container). `portal-fallback.conf` forwards them there.

- **Never hand-write a `/plugin/...` route.** portal-backend generates those into a
  shared volume and reloads portal-frontend's nginx. Writing one here means something
  else is broken.
- **Never edit `services/portal/DigitalTWINS-Portal/` to change portal routing.** It
  is a git submodule; editing it dirties the working tree and the next
  `git submodule update` conflicts. Portal changes are made in the portal repo,
  pushed, and picked up by bumping the submodule SHA.

---

## Known gaps: none of the four platform routes work yet

**This is not a regression.** These four locations were inherited verbatim from the
portal's old SSL template, where they were equally dead — and they were missing
outright from the HTTP template, so nobody ever hit them in local dev.

The reason is the same in all four cases: **every one of these apps is configured to
live at the root path**, and every one is reached today through its own published host
port. Proxying is fine — a `404`, or a redirect to `/hub/...`, means the request *did*
reach the app. The app just doesn't know it's mounted under a prefix.

| Route | Today | To make it work | Direct access meanwhile |
|---|---|---|---|
| `/seek/` | 404 | `RAILS_RELATIVE_URL_ROOT: "/seek"` in `services/seek/ldh-deployment/docker-compose.yml` (on both `seek` and `workers`) | `:8001` |
| `/airflow/` | 502 / broken UI | `AIRFLOW__API__BASE_URL=http://<host>/airflow` (Airflow 3; `AIRFLOW__WEBSERVER__BASE_URL` on 2.x) | `:8002` |
| `/jupyter/` | 302 to `/hub/...` | `c.JupyterHub.base_url = '/jupyter/'` in `services/jupyterhub/jupyterhub_config.py` | `:8016` |
| `/auth/` | 404 | Change `KC_HOSTNAME`, `PORTAL_KEYCLOAK_BASE_URL`, **and** this route together — see below | `:8009` |

`/jupyter/`'s upstream was also simply wrong: the old route pointed at
`jupyterlab:8888`, a service that is commented out of the root compose `include` and
has never run here. It now points at `jupyterhub:8000`.

⚠️ **Keycloak is the dangerous one.** `KC_HOSTNAME` pins the issuer baked into every
token (`iss=http://localhost:8009`), and the portal SPA validates against
`PORTAL_KEYCLOAK_BASE_URL`. Move one without the other and every login fails.

Note how cheap each of these fixes now is: one line here, `nginx -s reload`, plus one
setting on the app. Before this gateway existed, touching the route side of that meant
rebuilding the portal's frontend image.
