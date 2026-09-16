# SEEK Keycloak OIDC Integration Walkthrough

We have successfully integrated Keycloak Single Sign-On with SEEK via OpenID Connect (OIDC).

## Changes Made

1. **Environment Configuration**:
   - Added `SEEK_KEYCLOAK_CLIENT_SECRET` to `.env.template` and `.env`.
   - Verified that the `SEEK_KEYCLOAK_CLIENT_SECRET` exists in `secrets.env.template` and `secrets.env`.
2. **Keycloak Realm**:
   - Updated the `seek` client in `services/keycloak/digitaltwins-realm.json.template` to use the dynamic platform variables (`${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/seek/auth/keycloak/callback`) for its `redirectUris`.
3. **SEEK Configuration**:
   - Created `services/seek/ldh-deployment/omniauth_providers.yml` to instruct SEEK to use Keycloak as its OIDC provider.
   - Updated `services/seek/ldh-deployment/docker-compose.yml` to pass the necessary environment variables (`KEYCLOAK_PUBLIC_URL`, `SEEK_KEYCLOAK_CLIENT_SECRET`, `PLATFORM_PROTOCOL`, `PLATFORM_DOMAIN`) and mount the `omniauth_providers.yml` file.

## Validation Plan

To verify that these changes are functioning as expected, perform the following steps:

1. **Restart the affected services** from the root platform directory:
   ```bash
   cd /home/clin864/Projects/digitaltwins-platform
   docker compose down seek keycloak
   docker compose up -d seek keycloak
   ```
2. **Navigate to the SEEK login page**:
   - Go to `https://<your-platform-domain>/seek/login`
3. **Verify the OIDC Button**:
   - You should see a "Log in with Keycloak" (or similar external provider) button on the login screen.
4. **Test the Integration**:
   - Click the Keycloak login button.
   - You should be redirected to the Keycloak authentication page.
   - Log in using a Keycloak account.
   - You should be successfully redirected back to SEEK and authenticated as that user.

> [!NOTE]
> If a user doesn't exist in SEEK but exists in Keycloak, SEEK's OIDC implementation will typically prompt them to complete their profile or automatically provision their account based on Keycloak's `email` and `profile` scopes.

> [!TIP]
> You can view the SEEK logs for any authentication errors by running: `docker compose logs -f seek`.
