# Walkthrough: Keycloak Troubleshooting and Fixes

Here is a summary of the operational changes made to your local environment to resolve the Keycloak and API errors. No source code or configuration files were modified; the fixes were applied directly to the state of the running Docker containers.

## 1. Resolved Keycloak Database Authentication Failure
**Issue:** The `digitaltwins-platform-keycloak-1` and `hapi-fhir` containers were continuously crashing because their respective Postgres databases and roles did not exist. This occurred because the Postgres database container was already populated with existing data, which prevented its initialization scripts (`03_keycloak.sql` and `04_hapi.sql`) from automatically executing on startup. 

**Fix:**
- Manually executed `03_keycloak.sql` inside the `digitaltwins-platform-database-1` container to create the `keycloak` database and role.
- Manually executed `04_hapi.sql` to create the `hapi` database.
- Restarted the dependent containers (`keycloak`, `hapi-fhir`, and `orthanc-auth-service`). This restored connectivity between the digitaltwins API and Keycloak.

## 2. Disabled "HTTPS Required" for Local Development
**Issue:** When navigating to `http://localhost/auth/`, the Keycloak admin console returned a "We are sorry... HTTPS required" error. This is a built-in security policy for Keycloak's `master` realm that blocks non-HTTPS traffic, which is problematic for a local `http://localhost` environment.

**Fix:**
- Used the Keycloak Admin CLI (`kcadm.sh`) within the `digitaltwins-platform-keycloak-1` container to authenticate.
- Ran a command to update the `master` realm configuration, changing the `sslRequired` property to `NONE`.
- This change allows you to access the Keycloak admin console over standard HTTP.

> [!NOTE]
> Because these fixes modified the runtime state of your Docker volumes (specifically the Postgres data and Keycloak's internal configuration), the issues will remain fixed across normal container restarts. However, if you ever delete and recreate your Docker volumes, you may need to ensure the initialization scripts execute correctly on the fresh volume.
