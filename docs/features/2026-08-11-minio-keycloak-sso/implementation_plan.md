# Integrate MinIO with Keycloak Single Sign-On (SSO)

This plan outlines the steps required to configure MinIO to use Keycloak for authentication via OpenID Connect (OIDC).

## Background

MinIO has native support for OpenID Connect. Unlike Airflow's FAB integration (which allowed us to decouple the public authorization URL from the internal token exchange URL), MinIO strictly relies on a single **Discovery Document URL** (`MINIO_IDENTITY_OPENID_CONFIG_URL`). MinIO extracts both the `authorization_endpoint` and `token_endpoint` directly from this document.

## Solution to the `localhost` Docker Networking Limitation

Because MinIO strictly uses the endpoints from Keycloak's discovery document, Keycloak normally tells MinIO to use `http://localhost/auth/...` for the token exchange. Inside the MinIO Docker container, `localhost` resolves to the MinIO container itself, leading to a `Connection refused` error. 

To solve this completely natively on `localhost` without requiring any fake domains or `/etc/hosts` modifications, we will:
1. **Host a custom OIDC Discovery Document** directly in our NGINX gateway (`/minio-discovery.json`). This custom document will trick MinIO: it will preserve `http://localhost` for the browser's `authorization_endpoint`, but substitute `http://keycloak:8080` for the backend `token_endpoint`.
2. **Dynamically switch the config URL** in `gen-env.sh`. When deploying locally (`localhost`), MinIO will use the NGINX custom document. When deployed remotely, it will use the standard Keycloak discovery document.

## Proposed Changes

### 1. Keycloak Realm Configuration
We will add a new OIDC client for MinIO in `services/keycloak/digitaltwins-realm.json.template`.
- **Client ID:** `minio`
- **Client Protocol:** `openid-connect`
- **Access Type:** `confidential`
- **Valid Redirect URIs:** `${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/minio/oauth_callback`
- **Mappers:** We will map the `minio_admin` realm role (which we will create) to the `policy` claim with the value `consoleAdmin`. This tells MinIO that anyone with this Keycloak role gets administrator access in MinIO.

### 2. NGINX Custom Discovery Document
We will add a new route in `services/nginx/snippets/platform-routes.conf` that intercepts `/minio-discovery.json` and serves a static JSON object where the `token_endpoint` points to Keycloak's internal Docker IP, but the `authorization_endpoint` points to `localhost`.

### 3. MinIO Service Configuration (`docker-compose.yml`)
We will update `services/minio/docker-compose.yml` to inject the MinIO OIDC environment variables:

```yaml
      - MINIO_IDENTITY_OPENID_DISPLAY_NAME="Keycloak"
      - MINIO_IDENTITY_OPENID_CONFIG_URL="${MINIO_OIDC_CONFIG_URL}"
      - MINIO_IDENTITY_OPENID_CLIENT_ID="minio"
      - MINIO_IDENTITY_OPENID_CLIENT_SECRET="${MINIO_KEYCLOAK_CLIENT_SECRET}"
      - MINIO_IDENTITY_OPENID_SCOPES="openid,profile,email"
      - MINIO_IDENTITY_OPENID_CLAIM_NAME="policy"
      - MINIO_IDENTITY_OPENID_REDIRECT_URI="${MINIO_BROWSER_REDIRECT_URL}/oauth_callback"
```

### 4. Environment Variables (`gen-env.sh`)
We will update `util/gen-env.sh` to dynamically populate `MINIO_OIDC_CONFIG_URL`. If the platform domain is `localhost`, it will point to our custom NGINX document. Otherwise, it points directly to Keycloak. We will also add `MINIO_KEYCLOAK_CLIENT_SECRET` to `.env.template`.

## Verification Plan

1. Regenerate `.env` and the Keycloak realm file using `util/gen-env.sh` and `util/gen-realm.sh`.
2. Restart Keycloak and MinIO.
3. Access MinIO via the browser. We should see a "Login with Keycloak" button.
4. (Local test may fail without a host alias due to the `localhost` limitation).
