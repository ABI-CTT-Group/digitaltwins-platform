# MinIO SSO Fix for Remote Deployments

The MinIO Keycloak Single Sign-On issue on remote VMs has been resolved. The fix addresses the `localhost` hardcoding and Docker hairpin NAT issue.

## What was changed

1. **Dynamic OIDC Discovery Document**
   - Modified `util/gen-env.sh` to dynamically generate a `minio-discovery.json` file in the NGINX snippets directory.
   - The generated JSON now correctly resolves `issuer` and `authorization_endpoint` using your deployment's `PLATFORM_DOMAIN` and `PLATFORM_PROTOCOL` (e.g. `https://dev-digitaltwins.../auth/...`).
   - The internal endpoints (`token_endpoint`, `jwks_uri`, etc.) remain pointing to the internal docker network (`http://keycloak:8080/auth/...`).
   - Updated `.env.template` to populate `MINIO_BROWSER_REDIRECT_URL=${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/minio`. Previously this was empty, which caused MinIO to fallback to `http://localhost/minio` for its OAuth2 redirect URI, resulting in the browser redirecting back to `localhost` and failing with an `invalid_grant` error.

2. **NGINX Configuration Update**
   - Updated `services/nginx/snippets/platform-routes.conf` to serve the `/minio-discovery.json` route from the dynamically generated physical file instead of returning a hardcoded `http://localhost` string.
   - Updated `services/nginx/conf/ssl/default.conf` to serve `/minio-discovery.json` on port 80 without redirecting to HTTPS. This allows MinIO's internal HTTP requests to bypass the global HTTPS redirect and avoid TLS certificate mismatch errors on remote deployments.

3. **Version Control**
   - Added the generated `services/nginx/snippets/minio-discovery.json` file to `.gitignore`.

## What you need to do on your remote VM

Since these changes modify the deployment scripts and NGINX configs, you must pull these updates on your remote VM and re-run the generator script.

1. **Pull the latest code** on your remote VM.
2. **Re-run the environment generator script**:
   ```bash
   ./util/gen-env.sh
   ```
   *Make sure you pass your `-e` and `-s` flags if you don't have `env` and `secrets.env` populated with your remote config in the default location.*
3. **Reload NGINX** and **Restart MinIO**:
   ```bash
   docker compose restart minio
   docker exec digitaltwins-platform-gateway nginx -s reload
   ```

MinIO will now boot up, fetch the dynamically generated discovery document using the gateway, and successfully validate the Keycloak endpoints. The Keycloak login button will now appear and redirect to your actual public domain instead of `localhost`.
