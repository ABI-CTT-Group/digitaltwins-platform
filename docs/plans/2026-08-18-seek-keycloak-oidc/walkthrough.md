# SEEK Keycloak OIDC Integration Fix

## Problem

Clicking "Sign in with Keycloak" on the SEEK login page (`/seek/login`) resulted in:
```
OpenID Connect authentication failure
SSL_connect SYSCALL returned=5 errno=0 peeraddr=(null) state=SSLv3/TLS write client hello
```

## Root Cause

Two issues combined:

1. **SWD gem forces HTTPS**: The `swd` gem (Simple Web Discovery), used by the `openid_connect` Ruby gem, hardcodes `URI::HTTPS` as the URL builder. Even when the issuer URL is `http://...`, all OIDC discovery calls are made over HTTPS. When Keycloak is running on plain HTTP behind a reverse proxy, this causes an SSL handshake failure.

2. **Server-side calls routed through localhost**: The original `keycloak_oidc.rb` used `KEYCLOAK_PUBLIC_URL` (`http://localhost/auth`) for all OIDC endpoints. Server-side calls (token exchange, userinfo, JWKS) from inside the SEEK container to `localhost` fail because `localhost` inside the container doesn't reliably reach the host gateway.

## Fix

### [keycloak_oidc.rb](file:///home/clin864/Projects/digitaltwins-platform/services/seek/ldh-deployment/keycloak_oidc.rb)
- Added `SWD.url_builder = URI::HTTP` to force the SWD gem to use plain HTTP for discovery endpoints
- Split OIDC endpoints into **public** (browser-facing) and **internal** (container-to-container), following the exact same pattern used by Airflow and JupyterHub:
  - `scheme`/`host`/`port` → from `KEYCLOAK_INTERNAL_URL` (`http://keycloak:8080/auth`)
  - `authorization_endpoint` → full public URL (`http://localhost/auth/realms/digitaltwins/protocol/openid-connect/auth`)
  - `token_endpoint`, `userinfo_endpoint`, `jwks_uri` → relative paths resolved against the internal URL

### [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/seek/ldh-deployment/docker-compose.yml)
- Added `KEYCLOAK_INTERNAL_URL` environment variable to the `seek` service

## Verification

- Restarted the SEEK container
- Tested the full OIDC login flow in the browser:
  1. Navigated to `/seek/login` → clicked "Keycloak" tab → clicked "Sign in with Keycloak"
  2. Successfully redirected to Keycloak → authenticated → redirected back to SEEK
  3. SEEK registration page shown (first-time OIDC user) → completed registration
  4. Logged in successfully as "DigitalTwins Admin"
- SEEK container logs show no errors — clean OIDC callback with 302 redirect

![SEEK Keycloak login recording](seek_keycloak_login_v2_1787049437291.webp)
