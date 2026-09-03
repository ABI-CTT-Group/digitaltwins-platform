# SEEK interactive Keycloak login 504s on a real deployment (`host-gateway` hairpin)

**Symptom.** Browsing to `/seek` and logging in via Keycloak returns **504** at
`/seek/auth/oidc/callback?...&code=...`. SEEK log shows:

```
(oidc) Authentication failure! execution expired: HTTPClient::ReceiveTimeoutError
```

`/seek/auth/oidc/callback` is **correct** — it is SEEK's *own* OIDC callback (not
Keycloak). Keycloak authenticates you in the browser, redirects back here with the
`code`, and SEEK then makes a **server-side (back-channel)** call to exchange/validate
it. The 504 is the gateway timing out while that server-side call hangs.

## Root cause

Not an app-config regression. SEEK's OIDC config
(`ldh-deployment/config/initializers/keycloak_oidc.rb`) is correct: `discovery = false`
and the token/userinfo/JWKS endpoints are pinned to the **internal** `http://keycloak:8080`
(reachable from the SEEK container in ~12 ms).

The break is a **network hairpin** that only works in a dev setup. SEEK's compose adds:

```yaml
extra_hosts:
  - "${PLATFORM_DOMAIN:-localhost}:host-gateway"
```

which writes `172.17.0.1  <PLATFORM_DOMAIN>` into the container's `/etc/hosts`.
`host-gateway` is Docker's **default `docker0` bridge** (`172.17.0.1`) — but the platform
runs on the custom named bridge **`digitaltwins-platform` (172.18.x)**. A *residual*
call in the interactive-login flow still reaches the **public** hostname (most likely
ID-token signature validation fetching Keycloak's signing keys from the public issuer),
resolves it to `172.17.0.1`, which is **unroutable from the `172.18.x` network** → timeout
→ 504.

Reachability from inside the SEEK container to
`…/auth/realms/digitaltwins/.well-known/openid-configuration`:

| target | result |
| --- | --- |
| `172.17.0.1` (`host-gateway` / docker0) — what it uses today | timeout |
| `172.18.0.1` (host on the platform bridge, published-port hairpin) | timeout (blocked by `ufw default deny`) |
| **`172.18.0.13` (the gateway *container*)** | **HTTP 200 in ~33 ms, cert trusted** |

### Why the platform still seemed fine

The **API JWT path** (`keycloak_jwt_auth`) only ever talks to `keycloak:8080` internally,
so it works. Only the **interactive browser login** has a residual public-host call — and
it is the first thing to trip the hairpin on a real deployment.

### Origin

The hairpin was introduced with the SEEK↔Keycloak OIDC integration
(`ldh-deployment` commit `4ed7ff5`, 2026-08-19), which was verified only on a
`http://localhost` single-host dev box (see
`docs/features/2026-08-20-per-user-seek-auth/walkthrough.md`). A `host-gateway` hairpin
works there — no ufw, and `container → host-gateway → published port` succeeds. It does
not survive the three things a real portal adds at once: HTTPS + a custom domain, a custom
bridge network, and `ufw default deny`.

## Fix

Make the public hostname resolve — *inside the platform network* — to the **gateway
container** (which serves `/auth` → Keycloak with a trusted cert). **Both** edits are
required, because an `/etc/hosts` entry always shadows Docker DNS:

1. Add a network alias for the public hostname to the `gateway` service on the
   `digitaltwins-platform` network (`services/nginx/docker-compose.yml`):

   ```yaml
   services:
     gateway:
       networks:
         digitaltwins-platform:
           aliases:
             - ${PLATFORM_DOMAIN}
   ```

2. **Remove** the `extra_hosts: "${PLATFORM_DOMAIN}:host-gateway"` lines from SEEK's two
   services (`ldh-deployment/docker-compose.yml`).

Then recreate `gateway` and the SEEK services (SEEK takes a few minutes to boot and 502s
transiently while it does).

**This belongs upstream in the `ldh-deployment` submodule** — the hairpin is part of the
OIDC integration there, so fixing it upstream fixes every real deployment, not just this
runtime. (Alternatively, eliminate the residual public-host call at the app layer so no
hairpin is needed at all.)
