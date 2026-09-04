# Issue draft — ABI-CTT-Group/ldh-deployment

**Title:** SEEK interactive OIDC login 504s on real deployments — `host-gateway` hairpin only works on a localhost dev box

**Body:**

The SEEK↔Keycloak OIDC integration (`4ed7ff5`) added, in `docker-compose.yml`:

```yaml
extra_hosts:
  - "${PLATFORM_DOMAIN:-localhost}:host-gateway"
```

on the SEEK services. This makes interactive browser login work on a single-host
`http://localhost` dev box, but **504s on any real deployment**.

### What happens

Browser login → `/seek/auth/oidc/callback?...code=...` returns 504. SEEK logs:

```
(oidc) Authentication failure! execution expired: HTTPClient::ReceiveTimeoutError
```

### Why

`keycloak_oidc.rb` correctly sets `discovery: false` and pins token/userinfo/JWKS to the
internal `http://keycloak:8080` (reachable). But a residual back-channel call in the login
flow still reaches the **public** hostname (appears to be ID-token key validation against
the public issuer). The `extra_hosts: host-gateway` entry pins that hostname to
`172.17.0.1` (the `docker0` default bridge), which is **unroutable** when the platform runs
on a custom bridge (`digitaltwins-platform`, `172.18.x`) — and the published-port hairpin
via the host is additionally blocked by `ufw default deny` on hardened hosts. So the call
times out → 504.

The API JWT path (`keycloak_jwt_auth`) is unaffected because it only ever calls
`keycloak:8080` internally.

### Verified

From inside the SEEK container, hitting `…/.well-known/openid-configuration`:

- `172.17.0.1` (host-gateway / docker0): timeout
- `172.18.0.1` (host on the platform bridge): timeout (ufw)
- gateway **container** IP (`172.18.0.13`): HTTP 200, ~33 ms, cert trusted

### Suggested fix

Resolve the public hostname to the **gateway container** on the shared network instead of
relying on `host-gateway`:

1. Drop the `extra_hosts: "${PLATFORM_DOMAIN}:host-gateway"` lines from the SEEK services.
2. In the platform's gateway service, add a network alias for `${PLATFORM_DOMAIN}` on the
   shared `digitaltwins-platform` network (an `/etc/hosts` entry would shadow this, hence
   step 1 is required).

Alternatively, remove the residual public-host call so no hairpin is needed (e.g. ensure
ID-token validation uses the already-configured internal JWKS URL).

### Environment

- Real deployment: HTTPS + custom domain, custom bridge network, `ufw default deny`.
- Regression class: dev-only assumption — the feature was verified on `http://localhost`.
