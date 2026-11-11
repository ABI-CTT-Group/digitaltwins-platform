# Apply Consolidated Admin Identity to Local Deployment

We need to propagate the new unified identity (`admin1` with password `<REDACTED_PLATFORM_ADMIN_PASSWORD>`) to the running services (Keycloak, SEEK, and Airflow). 

> [!NOTE]
> Docker **images** do not store passwords or user data; this data is stored in the persistent database **volumes**. Because you just backed up your volumes with `docker_archive_volumes.sh`, you have two options for proceeding.

## User Feedback Addressed: "Why a separate admin account with a different password? Does it meet the new structure?"
Yes, it perfectly matches the new structure! 
In Keycloak, there are actually **two** levels of administration:
1. **The `master` realm bootstrap admin (`admin` / `<REDACTED_KC_BOOTSTRAP_ADMIN_PASSWORD>`)**: This is the "super admin" of the entire Keycloak server. It is configured via `KC_BOOTSTRAP_ADMIN_PASSWORD` in `secrets.env` (which still exists in the template).
2. **The `digitaltwins` realm platform admin (`admin1` / `<REDACTED_PLATFORM_ADMIN_PASSWORD>`)**: This is the admin for your specific platform. The "new structure" unified *this* identity across the Keycloak `digitaltwins` realm, SEEK, and Airflow. 

So it is entirely correct and expected that your `master` bootstrap admin remains a separate account from your platform admin.

## User Review Required

You selected Option 1. Please review the updated plan below (now with secrets redacted for safety) and provide explicit approval to proceed with execution.

### Option 1: In-Place Updates (Selected)
We update the existing running databases to align with the new credentials. No data is lost.
- **Keycloak**: Your `admin1` user in Keycloak already has the correct password and role for the `digitaltwins` realm. (Your `admin` account is the master bootstrap admin).
- **SEEK**: Since `admin1` was created via a Keycloak SSO login, it does not have (or need) a local SEEK password. We will run `./util/promote-seek-admin.sh 1afb2774-0277-494f-a976-34a72683d972` (the pinned Keycloak `sub` ID for the platform admin) to elevate your existing `admin1` Keycloak login to a SEEK server admin.
- **Airflow**: We will run the Airflow CLI command inside the `airflow-scheduler` container to create/update the `admin1` user with the new password and role.
- **Config**: We will run `./util/gen-realm.sh` to update the Keycloak realm JSON on disk so future deployments are correct.

## Verification Plan
1. Check that `util/create-admin-user.sh` completes successfully for SEEK.
2. Check that the Airflow CLI successfully creates/updates the user.
3. Verify `import/digitaltwins-realm.json` contains the updated configuration placeholders.
