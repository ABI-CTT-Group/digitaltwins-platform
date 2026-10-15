# Plan: make the JupyterHub service token a per-deployment secret and revoke the public one

## Context

Two components share the `digitaltwins-api` JupyterHub service token: `services/jupyterhub/jupyterhub_config.py` registers it, and the API sends it.

**The problem.** Three places read `JUPYTERHUB_API_TOKEN` with the fallback `digitaltwins-api-secret-token`:
- `jupyterhub_config.py`
- `services/api/app/routers/assays.py` (`_download_jupyter_folder`)
- `services/api/src/digitaltwins/jupyterhub/hub.py`

No env file or compose file sets the variable, so every deployment runs on that fallback.

**Why it matters.** The repository is public, and nginx forwards all of `/jupyter/` to the hub, including `/jupyter/hub/api/`. A read-only check on a local stack showed:
- With no token, the hub API returns 403.
- With the public value, it returns 200, acting as service `digitaltwins-api` with the scopes `admin:users`, `admin:servers`, `access:servers`, `tokens` and `admin-ui`.

So anyone who can reach a deployment's `/jupyter/` can read or change every user's workspace and run code in users' containers. Notebook-assay staging now copies measurement data into those workspaces, so more sensitive data is exposed than before.

**Why setting a new value isn't enough.** JupyterHub (`_add_tokens` in 5.4.6) adds tokens from config but never deletes ones that are no longer configured. A hub that has run with the default keeps it valid until it is removed from `jupyterhub.sqlite`.

**Outcome.**
- Every deployment uses its own secret token.
- On the next hub start, the public token is revoked without any operator step.
- A deployment that upgrades without adding the secret fails loudly instead of running on a default.
- Notebook launch, workspace download and workspace upload keep working.

### Decisions (interview 2026-10-16)

| Topic | Decision |
|---|---|
| Revoking the old token | Automatic at every hub start. `jupyterhub_config.py` deletes the `digitaltwins-api` service's `from config` tokens from `jupyterhub.sqlite`, and the hub then re-adds only the configured one. |
| Missing secret on upgrade | Hard fail, like `PORTAL_DB_PASSWORD`: `gen-env.sh` refuses to render and compose `:?` refuses to start. |
| Narrowing the service's scopes | A separate change. Keep `'admin': True` here so behaviour is unchanged. |
| Host port 8016 | Left as is. The new token protects that route the same way. Noted as a follow-up. |

## Changes

### 1. Declare the secret
- **`secrets.env.template`.** Add `JUPYTERHUB_API_TOKEN=` to the "Referenced by .env.template" block, with a comment:
  - the token is shared by JupyterHub and digitaltwins-api, and both must get the same value;
  - generate it with `openssl rand -hex 32`;
  - changing it revokes the previous one at the next hub start.
- **`.env.template`.** In the JupyterHub block, beside `JUPYTERHUB_CLIENT_SECRET`, add `JUPYTERHUB_API_TOKEN=${JUPYTERHUB_API_TOKEN}`. `util/gen-env.sh` derives its required-variable list from the template, so this line alone makes it refuse to render without the value.

### 2. Pass it to both containers, required
- **`services/jupyterhub/docker-compose.yml`.** Under `environment:`, add `- JUPYTERHUB_API_TOKEN=${JUPYTERHUB_API_TOKEN:?JUPYTERHUB_API_TOKEN is required}`, the same form as `JUPYTERHUB_CLIENT_SECRET`.
- **`services/api/docker-compose.yml`.** Under the JupyterHub block, add `JUPYTERHUB_API_TOKEN: ${JUPYTERHUB_API_TOKEN:?JUPYTERHUB_API_TOKEN is required}`.

### 3. JupyterHub: no default, and revoke stale config tokens
In `services/jupyterhub/jupyterhub_config.py`:
- Use `'api_token': os.environ['JUPYTERHUB_API_TOKEN']`. This follows the file's own rule that settings from `.env` are indexed, with no second default.
- Before `c.JupyterHub.services`, add a short block that runs only when `jupyterhub.sqlite` already exists in the working directory (`/srv/jupyterhub`, the default `db_url`):
  - It deletes `api_tokens` rows with `note = 'from config'` whose `service_id` is the `digitaltwins-api` service.
  - It uses Python's `sqlite3`; the image has no `sqlite3` CLI.
  - The hub reads its config before opening its database, so on start `_add_tokens` re-adds the current token.
  - Effect: the public token, and any previously rotated one, stops working on the next start. Running it on every start is harmless.
  - User tokens, OAuth tokens and other services' tokens are untouched.
  - A fresh install has no database file, so the block is skipped; it never creates one.
  - A comment notes that this applies to the default SQLite `db_url` only.

### 4. digitaltwins-api: no default
- **`src/digitaltwins/jupyterhub/hub.py`.**
  - Remove `DEFAULT_TOKEN`.
  - The token becomes `token or os.environ["JUPYTERHUB_API_TOKEN"]`. Compose guarantees the value; when run outside compose, a missing value fails loudly instead of using the public token.
- **`app/routers/assays.py`.** `_download_jupyter_folder` reads `os.environ["JUPYTERHUB_API_TOKEN"]` the same way. It stays a separate requests call, so the change is surgical.

### 5. Docs and upgrade notes
- **`docs/production.md` §3.** Add `JUPYTERHUB_API_TOKEN` to the JupyterHub checklist line. Leave the existing crypt-key line alone; it's unrelated.
- **`util/INSTALL-BUNDLE.md`.** Next to the "`REDIS_PASSWORD` is **required** now" note, add the same kind of note for `JUPYTERHUB_API_TOKEN`.
- **ADR.** Write `docs/decisions/2026-10-16-jupyterhub-service-token-secret.md`, with the operator upgrade steps under Consequences, following the `PORTAL_DB_PASSWORD` precedent.
- **Commit message.** Mark the change as BREAKING for deployment data files, with the same upgrade steps (also precedent).
- **Demo bundle (local, untracked).** Add `JUPYTERHUB_API_TOKEN` to `docs/artifacts/2026-10-06-105400-demo-airgap-deployment/scripts/gen-new-secrets.sh`, so the next demo bundle ships the key. This is optional and isn't committed, since that folder is untracked.

## Remote deployment rollout (operator steps)

Do these in one sitting. Once the new compose files are on the host, the boot unit's `docker compose up -d` fails until `.env` has the value, so a reboot in between would leave the platform down.

1. Add the secret to the host's only secrets copy:
   ```bash
   echo "JUPYTERHUB_API_TOKEN=$(openssl rand -hex 32)" >> data/secrets.env
   ```
2. Update the code: `git pull` plus `util/sync-runtime.sh`, or a new bundle with `airgap_build_step3.yml`. Step3 reruns `gen-env.sh` itself.
3. Re-render `.env`: `./util/gen-env.sh -e data/env -s data/secrets.env`. `sync-runtime.sh` never does this.
4. `docker compose up -d --build`. This recreates `jupyterhub` and `digitaltwins-api`, and the hub revokes the old token on start.
5. Check: the public value now gets 403 from `https://<domain>/jupyter/hub/api/users`. Use `-H "Authorization: token <old value>"` and print only the status code.

If step 1 or 3 is skipped, `gen-env.sh` or `docker compose` stops with "JUPYTERHUB_API_TOKEN is required" and the containers that are already running keep running. Step 4 restarts the hub, which stops users' running notebook servers. This happens on any hub restart (`cleanup_servers` is on by default). Files are kept, but unsaved kernel state is lost, so do it when nobody is working.

## Tests (red first)

- **New `services/jupyterhub/tests/test_service_token.py`.** Run it in the hub image, which has the real JupyterHub 5.4.6 `orm`.
  - Build a real hub database in a temporary directory with `jupyterhub.orm`. It holds:
    - service `digitaltwins-api` with a `from config` token and a token with another note;
    - another service with a `from config` token;
    - a user token.
  - Execute `jupyterhub_config.py` with a `get_config` stub, the required environment variables and the temporary directory as the working directory. Then check:
    - only `digitaltwins-api`'s `from config` token is gone, and every other token remains;
    - `c.JupyterHub.services[0]['api_token']` equals the environment value;
    - with no database file, nothing is created and no error is raised;
    - without `JUPYTERHUB_API_TOKEN`, a `KeyError` is raised.
- **`services/api/tests/test_notebook_staging.py`.**
  - With no `token` argument and the variable unset, `JupyterHub()` raises `KeyError`.
  - With the variable set, its value is the one sent in the `Authorization` header.
  - The existing tests already pass `token="tok"`.
- **`gen-env.sh`.** Run it in a scratch git worktree, because it also writes `services/nginx/snippets/minio-discovery.json`:
  - with a secrets file that lacks the key, it exits 1 and names `JUPYTERHUB_API_TOKEN`;
  - with the key, the rendered `.env` contains it.
- **`docker compose config`** for `jupyterhub` and `digitaltwins-api` (renders only, starts nothing): it fails without the variable and succeeds with it.
- **Regression suites.** The full API suite should show only the 10 failures and 1 error already present on HEAD, plus the new tests passing. The portal backend and frontend suites aren't touched.

## Verification on the local stack

1. Add a generated `JUPYTERHUB_API_TOKEN` to the local `secrets.env`, rerun `util/gen-env.sh`, and check that the only change in `.env` is the new line.
2. Run `docker compose up -d jupyterhub digitaltwins-api`, which recreates both.
3. Through the gateway (`/jupyter/hub/api/users`), check the status codes only:
   - the old public value gets 403;
   - the new value gets 200;
   - the old value on host port 8016 also gets 403.
4. The hub database holds exactly one `digitaltwins-api` token. After a second hub restart, it still holds one and the new value still works.
5. Current behaviour still works, through the portal and API as a signed-in user:
   - launching a notebook assay stages or skips files and opens the workspace;
   - downloading the assay's workspace returns a zip of `outputs/datasets`;
   - Verify opens the workspace;
   - a user's server stopped by the hub restart is started again by the next notebook launch. Correction: the plan first said it kept running; a hub restart stops it.
   Workspace upload (Submit) shares the download's Jupyter call, so it's covered by the same token path. It isn't run live, because it creates platform datasets.

## Out of scope (follow-ups)
- **Narrow the service's scopes:** replace `'admin': True` with a `load_roles` role granting only `admin:users`, `admin:servers` and `access:servers`.
- **Host port 8016:** the hub's published port, which bypasses nginx.
- **Non-SQLite hubs:** revocation for a hub moved off the default SQLite `db_url`.

## Process
- **Artifacts.** Sync the plan, task list and walkthrough to this folder. Keep the walkthrough free of local paths and live ids, and run gitleaks before committing.
- **Containers.** Rebuild and restart `jupyterhub` and `digitaltwins-api`, and say so in the hand-off.
- **Commit and ADR.** Commit on the same branch with the ADR. The commit message carries the BREAKING upgrade note.
