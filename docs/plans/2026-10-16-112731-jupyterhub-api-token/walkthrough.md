# Walkthrough: JupyterHub service token as a per-deployment secret

Decision record: [2026-10-16-jupyterhub-service-token-secret](../../decisions/2026-10-16-jupyterhub-service-token-secret.md).

## What changed

- **Templates.**
  - `secrets.env.template` declares `JUPYTERHUB_API_TOKEN`, with a comment saying the hub and the API share it.
  - `.env.template` renders it, so `util/gen-env.sh` refuses to run without it.
- **Compose.** `services/jupyterhub/docker-compose.yml` and `services/api/docker-compose.yml` pass `JUPYTERHUB_API_TOKEN` with `:?`, so compose refuses to start without it.
- **`services/jupyterhub/jupyterhub_config.py`.**
  - The service token is read with `os.environ[...]`, with no default.
  - Before the hub starts, the `digitaltwins-api` service's `from config` tokens are deleted from `jupyterhub.sqlite`, and the hub then re-adds only the configured one. This revokes the old public default, and any previously rotated token, on every hub that has used it.
- **digitaltwins-api.**
  - `src/digitaltwins/jupyterhub/hub.py` and `app/routers/assays.py` (`_download_jupyter_folder`) no longer have a default.
  - A test that had passed only thanks to the default now sets the variable.
- **Docs.**
  - `docs/production.md`: hardening checklist.
  - `util/INSTALL-BUNDLE.md`: required-secret note.
  - The ADR: operator upgrade steps.
- **Local only, not committed.** The demo bundle's `gen-new-secrets.sh`, in an untracked artifact folder, now generates the key.

## Tests

| Suite | Result |
|---|---|
| New `services/jupyterhub/tests/test_service_token.py` (4), run in the hub image against the real JupyterHub 5.4.6 ORM | pass |
| API: 4 new token tests in `test_notebook_staging.py` and `test_assay_notebook_launch.py` | pass |
| API, full suite | 287 passed. The 10 failures and 1 error also occur on HEAD. |
| `gen-env.sh` without the secret | exits 1 and names `JUPYTERHUB_API_TOKEN` |
| `gen-env.sh` with the secret | renders it into `.env` |
| `docker compose config` for jupyterhub and api | fails with "JUPYTERHUB_API_TOKEN is required" without the value; renders it with the value |

## Rotation on a local stack

- Added a generated token to `secrets.env` and re-rendered `.env`.
  - The only other `.env` change was two settings that were already in the template but missing from that stack's stale `.env`. Their values matched what the running API already used.
- Recreated `jupyterhub` and `digitaltwins-api`.
- Old public token:
  - 403 through the gateway;
  - 403 on host port 8016.
- New token: 200 on both routes.
- Hub database: exactly one `digitaltwins-api` token, and still one after another hub restart.
- Existing behaviour still works under the new token:
  - Launching a notebook assay with the user's server stopped started the server and staged or skipped the workspace (about 4 s).
  - Workspace download returned the zip of `outputs/datasets`.
  - The portal's launch route returned the workspace URL.

**Finding: a hub restart stops users' running notebook servers.** This is JupyterHub's `cleanup_servers` default and isn't caused by this change, but the rollout restarts the hub. Files persist in the per-user volumes. The ADR and plan were corrected.

## Operator upgrade (remote and air-gapped)

Do these in one sitting, when nobody is working in JupyterHub:
1. `echo "JUPYTERHUB_API_TOKEN=$(openssl rand -hex 32)" >> data/secrets.env`
2. Update the code (`git pull` and `util/sync-runtime.sh`, or a new bundle).
3. `./util/gen-env.sh -e data/env -s data/secrets.env`
4. `docker compose up -d --build`
5. Check that the old public value gets 403 from `/jupyter/hub/api/users`.
