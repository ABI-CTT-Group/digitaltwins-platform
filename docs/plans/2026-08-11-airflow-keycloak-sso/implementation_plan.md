# Airflow → Keycloak SSO Integration

Enable Airflow to authenticate via the Keycloak `digitaltwins` realm (OIDC / OAuth2),
using the `airflow` Keycloak client already defined in the realm template.
The Keycloak `admin` user will log into Airflow and be granted **Admin** role via
realm-role mapping (`airflow_admin`).

---

## Summary of Current State

| Item | Status |
|---|---|
| `AIRFLOW__CORE__AUTH_MANAGER` (docker-compose) | ✅ Already set to `FabAuthManager` |
| `auth_manager` in **both** `airflow.cfg` files | ❌ Still set to `SimpleAuthManager` (overrides compose env) |
| `webserver_config.py` | ❌ Does not exist — needed for OAuth2 provider config |
| Keycloak `airflow` client in realm template | ✅ Defined with redirect URI + secret placeholder |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` in `secrets.env` | ✅ Already set — **no change needed** |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` in `secrets.env.template` | ✅ Already has empty placeholder — **no change needed** |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` in `.env` / `.env.template` | ❌ Missing — needs adding |
| Realm-level roles `airflow_admin` / `airflow_viewer` etc. | ✅ Defined in realm template |
| Realm roles mapper (pushes roles into token) | ✅ Present in `airflow` client's `protocolMappers` |
| `Authlib`, `Flask-AppBuilder`, `apache-airflow-providers-fab` | ✅ Already installed in container |
| Ansible playbook (`airgap_build_step3.yml`) | ✅ No changes needed — it deploys the committed `airflow.cfg` as-is |
| `docs/deployment.md` Section 4 | ❌ Needs a new step documenting SSO setup |

> [!IMPORTANT]
> **Two `airflow.cfg` files exist** — both must be updated:
> - `services/airflow/config/airflow.cfg` — the source-controlled copy (committed to git)
> - `config/airflow.cfg` — the root-level copy actually mounted by the running stack
>   (`AIRFLOW_PROJ_DIR` defaults to `.` so docker-compose volume-mounts `./config/`)
>
> The diff between them shows only `fernet_key`, `secret_key`, and CORS settings differ.
> The `auth_manager` line is **identical and wrong** in both. We must update **both files**.
>
> Because `AIRFLOW_CONFIG=/opt/airflow/config/airflow.cfg` is set in docker-compose,
> the cfg file takes precedence over env vars for any value already set in the file.
> Line 57 (`auth_manager = SimpleAuthManager`) overrides the compose env var — this is
> why Keycloak login doesn't work today.

---

## Open Questions / Design Decisions Already Resolved

- **Auth backend**: FabAuthManager + OAuth2 via `webserver_config.py` ✅
- **Environments**: Local dev primary; prod notes included as diff section ✅
- **Realm check**: Plan includes a live Keycloak verification step before configuring Airflow ✅
- **Fallback local admin**: Keep FAB local admin as recovery fallback ✅
- **Role mapping**: Keycloak realm roles (`airflow_admin`) → Airflow `Admin` ✅
- **Secret**: Reuse existing `AIRFLOW_KEYCLOAK_CLIENT_SECRET` ✅

---

## Proposed Changes

### Step 1 — Verify Keycloak is healthy and the `airflow` client exists

Before touching Airflow config, confirm:
1. Keycloak container is up and reachable.
2. The `digitaltwins` realm exists and the `airflow` client is registered with the correct redirect URI.
3. The Keycloak `admin` user exists and has the `airflow_admin` realm role assigned.

**Action:** Run a diagnostic curl against `http://localhost/auth/realms/digitaltwins/.well-known/openid-configuration` and check the Keycloak admin API.

---

### Step 2 — Fix `airflow.cfg`: switch from SimpleAuthManager to FabAuthManager

#### [MODIFY] [airflow.cfg](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/config/airflow.cfg)

Change line 57:
```diff
-auth_manager = airflow.api_fastapi.auth.managers.simple.simple_auth_manager.SimpleAuthManager
+auth_manager = airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
```

This unblocks FAB from loading. The compose env var was already correct but was being
ignored because `airflow.cfg` hard-codes the old value.

---

### Step 3 — Create `webserver_config.py` for OAuth2 / Keycloak

#### [NEW] [webserver_config.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/config/webserver_config.py)

This file is the standard FAB mechanism for configuring OAuth2 providers. It will be
mounted into the container via the existing volume (`./config:/opt/airflow/config`).
FAB picks it up automatically when `AIRFLOW_CONFIG` points to the same directory.

> [!IMPORTANT]
> Airflow 3.x + FAB provider looks for `webserver_config.py` in `$AIRFLOW_HOME`
> (i.e. `/opt/airflow`), **not** in the config sub-dir. We need to ensure it's placed
> where FAB can find it. Options:
> - Mount it directly to `/opt/airflow/webserver_config.py` via a volume mount, OR
> - Set `AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_CLASS` to point to it — FAB uses the
>   env var `AIRFLOW__WEBSERVER__CONFIG_FILE` if set.
>
> **Chosen approach:** Add a new volume mount for the config file in `docker-compose.yml`
> so it lands at `/opt/airflow/webserver_config.py`.

Key config in `webserver_config.py`:

```python
import os
from airflow.www.security import AirflowSecurityManager
from flask_appbuilder.security.manager import AUTH_OAUTH

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True          # auto-create Airflow user on first SSO login
AUTH_USER_REGISTRATION_ROLE = "Viewer" # default role if no role claim matches

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "airflow",
            "client_secret": os.environ["AIRFLOW_KEYCLOAK_CLIENT_SECRET"],
            "server_metadata_url": (
                f"{os.environ.get('KEYCLOAK_INTERNAL_URL', 'http://keycloak:8080/auth')}"
                f"/realms/{os.environ.get('KEYCLOAK_REALM', 'digitaltwins')}"
                "/.well-known/openid-configuration"
            ),
            "api_base_url": (
                f"{os.environ.get('KEYCLOAK_INTERNAL_URL', 'http://keycloak:8080/auth')}"
                f"/realms/{os.environ.get('KEYCLOAK_REALM', 'digitaltwins')}/protocol/openid-connect/"
            ),
            "client_kwargs": {"scope": "openid email profile"},
        },
    }
]

# Map Keycloak realm roles → Airflow roles
class CustomSecurityManager(AirflowSecurityManager):
    def get_oauth_user_info(self, provider, resp):
        info = super().get_oauth_user_info(provider, resp)
        # Realm roles arrive in the token under "realm_access.roles"
        token = resp.get("access_token", "")
        import jwt as pyjwt
        claims = pyjwt.decode(token, options={"verify_signature": False})
        realm_roles = claims.get("realm_access", {}).get("roles", [])
        role_map = {
            "airflow_admin":  "Admin",
            "airflow_op":     "Op",
            "airflow_user":   "User",
            "airflow_viewer": "Viewer",
        }
        airflow_roles = [role_map[r] for r in realm_roles if r in role_map]
        info["role_keys"] = airflow_roles or [AUTH_USER_REGISTRATION_ROLE]
        return info

SECURITY_MANAGER_CLASS = CustomSecurityManager
```

---

### Step 4 — Thread env vars into docker-compose

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

Two changes needed in the `x-airflow-common` block:

1. **Add `AIRFLOW_KEYCLOAK_CLIENT_SECRET` env var** so `webserver_config.py` can read it.
2. **Add volume mount** for `webserver_config.py` → `/opt/airflow/webserver_config.py`.

```yaml
# In environment section:
AIRFLOW_KEYCLOAK_CLIENT_SECRET: ${AIRFLOW_KEYCLOAK_CLIENT_SECRET:?set AIRFLOW_KEYCLOAK_CLIENT_SECRET in secrets.env}

# In volumes section:
- ${AIRFLOW_PROJ_DIR:-.}/config/webserver_config.py:/opt/airflow/webserver_config.py:ro
```

---

### Step 5 — Expose `AIRFLOW_KEYCLOAK_CLIENT_SECRET` in `.env` and templates

#### [MODIFY] [.env](file:///home/clin864/Projects/digitaltwins-platform/.env)

Add to the Airflow section:
```ini
# Keycloak OAuth2 client secret for Airflow SSO
AIRFLOW_KEYCLOAK_CLIENT_SECRET=<REDACTED>
```

#### [MODIFY] [.env.template](file:///home/clin864/Projects/digitaltwins-platform/.env.template)

Add to the Airflow section:
```ini
# Keycloak OAuth2 client secret for Airflow SSO
AIRFLOW_KEYCLOAK_CLIENT_SECRET=${AIRFLOW_KEYCLOAK_CLIENT_SECRET}
```

> [!NOTE]
> **`secrets.env`** ✅ already has `AIRFLOW_KEYCLOAK_CLIENT_SECRET=<REDACTED>` — no change.
> **`secrets.env.template`** ✅ already has the empty placeholder — no change.
> Only `.env` and `.env.template` need updating (they reference it via `${...}` interpolation).

---

### Step 5b — Update `docs/deployment.md` Section 4

#### [MODIFY] [deployment.md](file:///home/clin864/Projects/digitaltwins-platform/docs/deployment.md)

Add a new step 4 in **Section 4. Initialise Workflow Service (Airflow)** that documents:
1. The `auth_manager` change in `airflow.cfg` (switching to FabAuthManager)
2. Mounting / existence of `webserver_config.py`
3. Assigning the `airflow_admin` realm role to the `admin` user in Keycloak
4. Update the default credentials table (remove `admin`/`admin` Airflow row or note Keycloak SSO)

> [!NOTE]
> **Ansible playbook (`util/airgap_build_step3.yml`)** ✅ **requires no changes.** 
> The playbook runs `docker compose up airflow-init` and deploys whatever `airflow.cfg`
> is committed to the repo. Since we're committing the fixed cfg, prod deployments
> automatically get FabAuthManager. There is no airflow.cfg patching step in the playbook
> (it was intentionally removed in a prior refactor).

---

### Step 6 — Verify Keycloak `admin` user has `airflow_admin` realm role

If the realm was imported fresh (or via `gen-realm.sh`), the `admin` user may not have
the `airflow_admin` realm role automatically assigned. The plan includes a verification
step via the Keycloak admin console or API:

```
GET http://localhost/auth/admin/realms/digitaltwins/users?search=admin
→ get user ID
GET http://localhost/auth/admin/realms/digitaltwins/users/{id}/role-mappings/realm
```

If `airflow_admin` is missing, assign it via the admin console:
`Users → admin → Role Mappings → Realm Roles → airflow_admin`.

---

## Production (Remote) Differences

> [!WARNING]
> For remote/prod, additional steps are needed. Do NOT apply these to local dev.

| Config | Local dev | Remote prod |
|---|---|---|
| `KC_HOSTNAME` | `http://localhost/auth` | `https://<domain>/auth` |
| Keycloak redirect URI | `http://localhost/airflow/auth/oauth-authorized/keycloak` | `https://<domain>/airflow/auth/oauth-authorized/keycloak` |
| `server_metadata_url` | uses `KEYCLOAK_INTERNAL_URL` (container-to-container) | same — stays internal |
| `AUTH_USER_REGISTRATION_ROLE` | `Viewer` (safe default) | `Viewer` (same) |
| TLS | none | TLS termination at NGINX |
| Realm re-import | Required if client redirect URIs need updating | Run `util/gen-realm.sh -e env -s secrets.env` then re-import via Keycloak admin |

For prod, `util/gen-realm.sh` renders the realm template with `PLATFORM_DOMAIN` and
`PLATFORM_PROTOCOL=https`, which sets the correct redirect URI automatically.

---

## Verification Plan

### Automated checks
```bash
# 1. Confirm Keycloak OIDC discovery endpoint is reachable
curl -s http://localhost/auth/realms/digitaltwins/.well-known/openid-configuration | python3 -m json.tool

# 2. Confirm airflow containers restart cleanly after config changes
cd services/airflow
docker compose down && docker compose up -d
docker compose ps

# 3. Check airflow-apiserver logs for FAB / OAuth errors
docker logs digitaltwins-platform-airflow-apiserver-1 --tail 50
```

### Manual Verification
1. Navigate to `http://localhost/airflow` — should see a **Sign in with Keycloak** button (or be redirected to Keycloak login).
2. Enter `admin` / `admin` in the Keycloak login page.
3. After redirect, confirm you land in Airflow with **Admin** role (Settings → Users → check role).
4. Confirm DAGs are visible and triggerable.
5. Confirm the fallback local login still works (via `http://localhost:8002` direct port if needed).
