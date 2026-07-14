import os

c = get_config()  # noqa

# Settings that come from .env are read with os.environ[...], so the `${X:-...}` in
# docker-compose.yml holds their only default. A second default here would drift from it
# — DOCKER_NETWORK_NAME's did, for as long as both existed. Indexing also fails loudly:
# .get() with no default returns None and quietly builds a URL out of the string "None".
# Everything else keeps its default here.

# ---------------------------------------------------------------------------
# Authenticator — Keycloak OIDC via oauthenticator 17.x GenericOAuthenticator
# ---------------------------------------------------------------------------
# Browser-facing Keycloak URL — where the user's browser is redirected to authorize.
# Keycloak now lives behind the edge gateway at <public-url>/auth, so this is a normal
# same-origin URL on 443 and works under HTTPS. It must match Keycloak's KC_HOSTNAME,
# because that is the `iss` baked into every token.
_keycloak_public = os.environ['KEYCLOAK_PUBLIC_URL']
# Container-to-container URL — server-side token exchange and userinfo. Straight to the
# keycloak service on the shared network; never leaves it, so it stays plain HTTP.
# (This used to be host.docker.internal:8009, a workaround from when Keycloak had no
# stable public address and the only way to reach the same instance was via the host.)
_keycloak_internal = os.environ['KEYCLOAK_INTERNAL_URL']
_realm = os.environ['KEYCLOAK_REALM']
_base_public = f'{_keycloak_public}/realms/{_realm}/protocol/openid-connect'
_base_internal = f'{_keycloak_internal}/realms/{_realm}/protocol/openid-connect'

c.JupyterHub.authenticator_class = 'oauthenticator.generic.GenericOAuthenticator'

c.GenericOAuthenticator.authorize_url = f'{_base_public}/auth'
c.GenericOAuthenticator.token_url = f'{_base_internal}/token'
c.GenericOAuthenticator.userdata_url = f'{_base_internal}/userinfo'

# Declared in .env, but docker-compose.yml does not forward it — so the default here is
# what actually runs, and the .env value is ignored.
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
# Declared in .env, but docker-compose.yml does not forward it — so the default here is
# what actually runs, and the .env value is ignored.
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
# Declared in .env, but docker-compose.yml does not forward it — so the default here is
# what actually runs, and the .env value is ignored.
c.Authenticator.admin_users = set(
    os.environ.get('JUPYTERHUB_ADMIN_USERS', 'admin').split(',')
)

# ---------------------------------------------------------------------------
# Spawner — DockerSpawner: one isolated container per user
# ---------------------------------------------------------------------------
c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'

# Docker image for single-user servers (built from Dockerfile.singleuser)
c.DockerSpawner.image = os.environ.get('DOCKER_NOTEBOOK_IMAGE', 'digitaltwins-platform-jupyter-singleuser:latest')

# Networking — spawned containers join the same Docker network as the Hub. Compose passes
# ${PROJECT_NAME}, which is the network's real Docker name (the root compose sets
# networks.digitaltwins-platform.name: ${PROJECT_NAME}). The default this line used to
# carry, 'digitaltwins-platform_digitaltwins', named a network that does not exist.
_network_name = os.environ['DOCKER_NETWORK_NAME']
c.DockerSpawner.network_name = _network_name
c.DockerSpawner.use_internal_ip = True

# Hub URL for user containers (port 8081 = hub API; distinct from proxy port 8000)
c.JupyterHub.hub_connect_url = 'http://digitaltwins-platform-jupyterhub:8081'

# User notebook directory (inside each user container)
_notebook_dir = os.environ.get('DOCKER_NOTEBOOK_DIR', '/home/jovyan/work')
c.DockerSpawner.notebook_dir = _notebook_dir

# Per-user persistent storage via Docker named volumes
# Automatically creates "digitaltwins-platform_jupyterhub_user_{username}" for each user
c.DockerSpawner.volumes = {
    'digitaltwins-platform_jupyterhub_user_{username}': _notebook_dir
}

# Remove user containers when they stop (data persists in named volumes)
c.DockerSpawner.remove = True

# Resource limits — sized for ML training / image segmentation workloads
c.DockerSpawner.mem_limit = os.environ.get('DOCKER_MEM_LIMIT', '8G')
c.DockerSpawner.cpu_limit = float(os.environ.get('DOCKER_CPU_LIMIT', '4'))

# Timeouts — allow time for image pulls and container startup
c.DockerSpawner.start_timeout = 120
c.DockerSpawner.http_timeout = 60

# Allow admin to access other users' servers (via JupyterHub admin panel)
c.JupyterHub.admin_access = True
