# Fix MinIO Keycloak SSO for Remote Deployments

The issue you're experiencing is caused by a networking challenge between MinIO and Keycloak combined with a hardcoded `localhost` workaround in the NGINX configuration.

## Why this happens:
MinIO requires both the frontend (`authorization_endpoint`) and backend (`token_endpoint`) URLs from Keycloak's OIDC discovery document. 
When MinIO container tries to fetch the real Keycloak discovery document (`https://dev-digitaltwins.../.well-known/openid-configuration`), it often fails to resolve or route to its own external domain from within the Docker network (hairpin NAT issue), causing it to fail initialization and hide the Keycloak button.

Currently, the `.env` generation script provides a workaround for `localhost` by pointing MinIO to `http://gateway/minio-discovery.json`. However, this discovery document is a hardcoded string inside `services/nginx/snippets/platform-routes.conf` that always returns `http://localhost/...`. If a remote deployment uses this workaround, the browser gets redirected to `localhost` and fails.

## Proposed Changes

We will fix this by dynamically generating the `minio-discovery.json` file for every deployment, ensuring it contains the correct public domain for the frontend endpoints while keeping internal Docker IPs for the backend endpoints.

### `services/nginx/snippets/platform-routes.conf`
Modify the `location = /minio-discovery.json` block to serve a physical file instead of returning a hardcoded `localhost` JSON string.
#### [MODIFY] [platform-routes.conf](file:///home/clin864/Projects/digitaltwins-platform/services/nginx/snippets/platform-routes.conf)

### `util/gen-env.sh`
Update the environment generation script to always point MinIO to `http://gateway/minio-discovery.json`, and dynamically generate the `services/nginx/snippets/minio-discovery.json` file with the correct `${PLATFORM_PROTOCOL}` and `${PLATFORM_DOMAIN}`.
#### [MODIFY] [gen-env.sh](file:///home/clin864/Projects/digitaltwins-platform/util/gen-env.sh)

### `.gitignore`
Ignore the newly generated `minio-discovery.json` file so it doesn't get committed to version control.
#### [MODIFY] [.gitignore](file:///home/clin864/Projects/digitaltwins-platform/.gitignore)

## Verification Plan

### Automated Tests
- NGINX configuration syntax check: `docker run --rm -v ./services/nginx/snippets:/etc/nginx/snippets:ro nginx:1.30.3-alpine nginx -t -c /etc/nginx/nginx.conf` (Note: since we are only touching snippets, we'll just review the syntax).

### Manual Verification
1. Run `util/gen-env.sh` and verify that `services/nginx/snippets/minio-discovery.json` is generated correctly.
2. Verify the generated JSON contains the correct `dev-digitaltwins...` URLs for `issuer` and `authorization_endpoint`, while keeping `http://keycloak:8080` for backend endpoints.
3. Deploy on the remote VM, verify the Keycloak login button appears and redirects correctly.
