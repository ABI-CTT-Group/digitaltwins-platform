# MinIO — Keycloak Integration and Service Account Hardening

## Current State

All access to MinIO — from Airflow workers, DAG tasks, and the platform API — uses the
MinIO root credentials (`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`). There is no concept
of per-user access control in MinIO; everything runs as admin.

The MinIO console is proxied at `/minio/` and requires the root credentials to log in.

---

## Planned Improvements

### 1. Dedicated Airflow service account (low effort, high value)

Rather than using root credentials, create a dedicated MinIO user for Airflow with a
policy scoped to only the buckets it needs:

- `airflow-workspace` — read/write (task inputs/outputs)
- `airflow-logs` — read/write (remote task logging)

This limits blast radius if the Airflow credentials are ever compromised, and gives
MinIO audit logs a meaningful identity to attribute to.

**What needs changing:**
- Create a MinIO user (via the console or `mc admin user add`)
- Attach a scoped policy to that user
- Update `MINIO_SERVER_ACCESS_KEY` / `MINIO_SERVER_SECRET_KEY` in the platform `.env`
  and the compute worker `.env` to use the new credentials
- Update `AIRFLOW_CONN_MINIO_LOGS` in `services/airflow/docker-compose.yml` and
  `services/airflow/compute-worker/docker-compose.yml`

This does not require Keycloak integration and can be done independently.

---

### 2. MinIO console access via Keycloak (OIDC integration)

MinIO supports OIDC natively. Configuring it allows platform users to log into the
MinIO console with their Keycloak credentials rather than the root password.

**What needs changing:**

1. Create a Keycloak client for MinIO (e.g. `minio`) in the digitaltwins realm with:
   - Client authentication enabled
   - Valid redirect URI: `https://${PLATFORM_DOMAIN}/minio/oauth_callback`

2. Add to `services/minio/docker-compose.yml`:
   ```yaml
   - MINIO_IDENTITY_OPENID_CONFIG_URL=https://${PLATFORM_DOMAIN}/auth/realms/digitaltwins/.well-known/openid-configuration
   - MINIO_IDENTITY_OPENID_CLIENT_ID=minio
   - MINIO_IDENTITY_OPENID_CLIENT_SECRET=${MINIO_KEYCLOAK_CLIENT_SECRET}
   - MINIO_IDENTITY_OPENID_CLAIM_NAME=policy
   - MINIO_IDENTITY_OPENID_REDIRECT_URI_DYNAMIC=on
   ```

3. Map Keycloak roles to MinIO policies via the `policy` claim. For example:
   - Keycloak role `minio-admin` → MinIO `consoleAdmin` policy
   - Keycloak role `minio-readwrite` → MinIO `readwrite` policy

   MinIO reads the `policy` claim from the JWT and applies the named policy to the session.
   The claim name must match `MINIO_IDENTITY_OPENID_CLAIM_NAME`.

**Design decision:** How granular should bucket-level access be? Options:
- Simple: all authenticated users get read/write to `airflow-workspace`; admins get full access
- Granular: per-project buckets with per-group policies (more complex, requires policy
  management as users/groups change)

---

### 3. Per-user task execution in MinIO (complex, requires developer work)

See also: `workflow-user-attribution.md`

Even with Keycloak integration, Airflow task execution still uses the service account
credentials (point 1 above). Tasks don't carry the identity of the user who triggered
the workflow.

Propagating user identity into task execution would require:
- The portal to pass the user's Keycloak token in the DAG run `conf` at trigger time
- DAG code to use that token (or exchange it for MinIO-scoped credentials) when
  reading/writing data
- MinIO's STS `AssumeRoleWithWebIdentity` endpoint to exchange a Keycloak token for
  temporary MinIO credentials

This is the "right" solution for multi-tenant data isolation but is non-trivial. It
touches the portal, the DigitalTWINS API, and the DAG code. Defer until the simpler
steps above are in place and the access control requirements are clearer.

---

## Recommended Order

1. **Dedicated Airflow service account** — no Keycloak dependency, immediate security improvement
2. **MinIO console via Keycloak OIDC** — allows admins to log in without sharing the root password
3. **Per-user task execution** — revisit once user attribution requirements are better defined
