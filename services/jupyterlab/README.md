# JupyterLab (inactive)

A single shared JupyterLab server, replaced by [JupyterHub](../jupyterhub/README.md).

## Purpose

It ran one `jupyter/base-notebook` JupyterLab, signed in with a token, before the platform moved to
JupyterHub's per-user servers.

## Status

Inactive. Its include in the root `docker-compose.yml` is commented out, and its variables
(`JUPYTERLAB_ENABLED`, `JUPYTERLAB_URL`, `JUPYTERLAB_TOKEN`) are commented out in `.env.template`.
Nothing in the platform's code calls it, and the gateway has no route to it.

It is kept only as history. Removing or archiving it is listed in
[docs/future_refactoring.md](../../docs/future_refactoring.md).

## Code map

| Path | What it is |
|---|---|
| `docker-compose.yml` | The `jupyterlab` service, on host port 8008 |
| `workspace/` | An empty folder (`.gitkeep`); the compose file uses a named volume instead |
