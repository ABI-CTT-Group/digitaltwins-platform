# Airflow SSO Integration Complete

The Keycloak authentication integration for Airflow is now fully implemented, tested, and working successfully in the local development environment. 

## What was Changed

1. **Airflow Config (`airflow.cfg`)**: Switched from `SimpleAuthManager` to `FabAuthManager` in both the source-controlled file and the root-level mounted configuration.
2. **FAB Configuration (`webserver_config.py`)**: Created the Flask-AppBuilder OAuth configuration to hook up Airflow to the `digitaltwins` Keycloak realm.
3. **Docker Compose Wiring**: Added the `AIRFLOW_KEYCLOAK_CLIENT_SECRET` to the environment and mounted `webserver_config.py` in `services/airflow/docker-compose.yml`.
4. **Environment Variables**: Added the client secret variable to both `.env` and `.env.template` so it injects correctly from `secrets.env`.
5. **Keycloak Roles**: Created the `airflow` OIDC client and `airflow_admin`, `airflow_op`, `airflow_user`, `airflow_viewer` realm roles in Keycloak, and assigned the admin role to the local Keycloak `admin` user.
6. **Documentation**: Updated `docs/deployment.md` to document the Keycloak Single Sign-On flow for Airflow.

## Debugging Highlights

During implementation, we encountered and resolved two critical issues:

1. **Airflow 3.x `webserver_config.py` Path Changes**: 
   The initial FAB import (`from airflow.www.security import AirflowSecurityManager`) caused a fatal crash because it was removed in Airflow 3.0. It was replaced with the updated Airflow 3.x FAB provider import: `from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride`.

2. **Docker Network vs Host Network OAuth Redirects**: 
   The Keycloak token exchange failed with a `Connection refused` (Error 111) because FAB was trying to exchange the browser's token using the public browser-facing URL (`http://localhost/auth`), which inside the Airflow container resolves to the container itself (port 80). We fixed this by manually decoupling the OAuth endpoints in `webserver_config.py`:
   - `authorize_url`: `http://localhost/auth` (Public facing, for the user's browser)
   - `access_token_url` & `userinfo_endpoint`: `http://keycloak:8080/auth` (Internal Docker network routing, for server-to-server token exchange)

## Verification

The Airflow UI now correctly presents the **"Sign In with keycloak"** OAuth button. Clicking it redirects to Keycloak, authenticates the user, and successfully grants access to the Airflow Dashboard as an admin user.

![Airflow Dashboard](file:///home/clin864/.gemini/antigravity-ide/brain/7a010c53-292f-4110-b03c-172f77fa57ca/airflow_dashboard_1786415783771.png)
