import os

c = get_config()  # noqa

# ---------------------------------------------------------------------------
# Authenticator — Keycloak OIDC via oauthenticator 17.x GenericOAuthenticator
# ---------------------------------------------------------------------------
# Browser-facing Keycloak URL — used for the authorize redirect the user's browser follows
_keycloak_public = os.environ.get('KEYCLOAK_PUBLIC_URL', 'http://localhost:8009')
# Container-to-host URL — used for server-side token exchange and userinfo calls.
# host.docker.internal resolves to the Docker host's IP (mapped via extra_hosts in docker-compose).
# KC_HOSTNAME=localhost:8009 is set in Keycloak so issued tokens always carry iss=localhost:8009;
# host.docker.internal:8009 reaches that same Keycloak instance, so validation passes.
_keycloak_internal = os.environ.get('KEYCLOAK_INTERNAL_URL', 'http://host.docker.internal:8009')
_realm = os.environ.get('KEYCLOAK_REALM', 'digitaltwins')
_base_public = f'{_keycloak_public}/realms/{_realm}/protocol/openid-connect'
_base_internal = f'{_keycloak_internal}/realms/{_realm}/protocol/openid-connect'

c.JupyterHub.authenticator_class = 'oauthenticator.generic.GenericOAuthenticator'

c.GenericOAuthenticator.authorize_url = f'{_base_public}/auth'
c.GenericOAuthenticator.token_url = f'{_base_internal}/token'
c.GenericOAuthenticator.userdata_url = f'{_base_internal}/userinfo'

c.GenericOAuthenticator.client_id = os.environ.get('JUPYTERHUB_CLIENT_ID', 'jupyterhub')
c.GenericOAuthenticator.client_secret = os.environ.get('JUPYTERHUB_CLIENT_SECRET', 'jupyterhub-secret')

# Redirection on Logout to clear the Keycloak SSO session
c.GenericOAuthenticator.logout_redirect_url = f'{_base_public}/logout?client_id={c.GenericOAuthenticator.client_id}&post_logout_redirect_uri=http://localhost:8016/hub/login'


# Scopes requested from Keycloak
c.GenericOAuthenticator.scope = ['openid', 'profile', 'email']

# Derive the JupyterHub username from the 'preferred_username' claim
c.GenericOAuthenticator.username_claim = 'preferred_username'

# ---------------------------------------------------------------------------
# Group-based access control (oauthenticator 17.x API)
# Keycloak includes group names in the 'groups' claim via the groups protocol
# mapper configured on the jupyterhub client.
# ---------------------------------------------------------------------------
_allowed_groups = set(
    os.environ.get('JUPYTERHUB_ALLOWED_GROUPS', 'admin,researcher').split(',')
)
_admin_groups = set(
    os.environ.get('JUPYTERHUB_ADMIN_GROUPS', 'admin').split(',')
)

# manage_groups must be True to allow auth_state_groups_key to work
c.GenericOAuthenticator.manage_groups = True
# auth_state_groups_key: path into the auth_state dict where groups live.
# With userdata_url set, auth_state['oauth_user'] holds the userinfo response.
c.GenericOAuthenticator.auth_state_groups_key = 'oauth_user.groups'

c.GenericOAuthenticator.allowed_groups = _allowed_groups
c.GenericOAuthenticator.admin_groups = _admin_groups

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = 8000  # internal container port

# Hub bind address (used by single-user servers to reach the hub)
c.JupyterHub.hub_ip = '0.0.0.0'

# ---------------------------------------------------------------------------
# Admin users (fallback static list; group-based admin via admin_groups is preferred)
# ---------------------------------------------------------------------------
c.Authenticator.admin_users = set(
    os.environ.get('JUPYTERHUB_ADMIN_USERS', 'admin').split(',')
)

# ---------------------------------------------------------------------------
# Spawner – SimpleLocalProcessSpawner runs notebook servers in the same container
# ---------------------------------------------------------------------------
c.JupyterHub.spawner_class = 'jupyterhub.spawner.SimpleLocalProcessSpawner'

# Use jupyterhub-singleuser (the canonical single-user server command)
c.Spawner.cmd = ['jupyterhub-singleuser']

# Required when JupyterHub runs as root (as it does inside Docker)
c.Spawner.args = ['--allow-root']

# Notebook directory — use /tmp so it always exists and is writable by root
c.Spawner.notebook_dir = '/tmp'

# Give the single-user server a bit more time to start
c.Spawner.http_timeout = 60
c.Spawner.start_timeout = 60

# Allow admin to access other users' servers
c.JupyterHub.admin_access = True
