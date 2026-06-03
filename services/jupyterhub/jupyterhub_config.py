import os

c = get_config()  # noqa

# ---------------------------------------------------------------------------
# Authenticator
# ---------------------------------------------------------------------------
# DummyAuthenticator for local development – replace with KeycloakAuthenticator
# or another provider for production.
c.JupyterHub.authenticator_class = 'dummy'
c.DummyAuthenticator.password = os.environ.get('JUPYTERHUB_DUMMY_PASSWORD', 'password')

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = 8000  # internal container port; mapped to 8016 on the host

# Hub bind address (used by single-user servers to reach the hub)
c.JupyterHub.hub_ip = '0.0.0.0'

# ---------------------------------------------------------------------------
# Admin users
# ---------------------------------------------------------------------------
c.Authenticator.admin_users = {'admin'}

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
