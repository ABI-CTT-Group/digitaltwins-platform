FROM jupyterhub/jupyterhub:5.4.6

# Install Hub dependencies (notebook stack is in Dockerfile.singleuser)
RUN pip install --no-cache-dir \
    "packaging>=21.0" \
    "oauthenticator>=17.0" \
    dockerspawner
