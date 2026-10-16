# Make the JupyterHub service token a per-deployment secret and revoke the public default

- **Date:** 2026-10-16
- **Status:** Accepted

## Context

digitaltwins-api calls JupyterHub as the `digitaltwins-api` service. It uses that service to:
- start users' servers;
- stage notebook assays into users' workspaces;
- download and upload results from those workspaces.

The service has the hub's admin role.

**The token is public.** The hub config and the API both read `JUPYTERHUB_API_TOKEN` with the fallback `digitaltwins-api-secret-token`. No env file or compose file sets the variable, so every deployment uses that value, and it is in a public repository.

**It works from outside.** The gateway forwards all of `/jupyter/`, including the hub API. A read-only check confirmed that the public value is accepted through the gateway with admin scopes.

**Rotating it doesn't revoke it.** JupyterHub adds tokens listed in config to its database but never deletes ones that are no longer listed. A hub that has run with the default keeps it valid after a new value is configured.

**How secrets reach containers.** On remote deployments, the operator writes `data/secrets.env` by hand, and it is the only copy. `util/gen-env.sh` renders `.env` from `.env.template` and fails on any variable the template uses that is unset. The day-to-day upgrade (`git pull`, `sync-runtime.sh`, `compose up`) doesn't re-render `.env`.

## Alternatives Considered

### Revoking the old token

#### Option A: automatic at every hub start (chosen)
`jupyterhub_config.py` deletes the service's `from config` tokens from `jupyterhub.sqlite`, and the hub then re-adds only the configured one.
- Pros:
  - No operator step, on remote and air-gapped hosts alike.
  - Running it on every start is harmless.
  - A later rotation revokes the previous token too.
- Cons:
  - It depends on JupyterHub's database schema (`api_tokens`, `services`), which is pinned at 5.4.6 and covered by a test against the real ORM.
  - It handles only the default SQLite `db_url`.

#### Option B: a documented manual command
- Cons: every operator has to remember it, and a missed step leaves an admin token live.

#### Option C: recreate the hub's database volume
- Cons: heavy-handed and manual. It discards hub state, though user files survive in their own volumes.

### A deployment that upgrades without the secret

#### Option A: hard fail (chosen)
`gen-env.sh` refuses to render, and compose `${JUPYTERHUB_API_TOKEN:?...}` refuses to start. This matches the precedent set by `PORTAL_DB_PASSWORD`.
- Pros: a deployment can never run on a default.
- Cons:
  - Upgrades stop until the operator adds the secret.
  - If the new compose files are on the host and the secret isn't, a reboot fails to start the stack.

#### Option B: `gen-env.sh` generates the secret if it is missing
- Cons:
  - `gen-env.sh` would start writing to the operator's only copy of `secrets.env`.
  - The day-to-day upgrade path doesn't run `gen-env.sh` anyway.

#### Option C: soft fail
The stack starts and only the notebook features fail.
- Cons:
  - A deployment can silently run with those features broken.
  - The hub would register the service with an empty token.

## Decision

Option A in both sections.

- `JUPYTERHUB_API_TOKEN` is a required secret:
  - it is declared in `secrets.env.template` and `.env.template`;
  - compose passes it to `jupyterhub` and `digitaltwins-api` with `:?`;
  - neither service has a default any more.
- `jupyterhub_config.py` revokes the service's previously configured tokens at every start.
- The service keeps `'admin': True` for now. Narrowing it to the scopes it uses is a separate change.

## Consequences

- **Breaking for deployment data files.** Every existing deployment must add the secret before, or together with, the upgrade, in one sitting:
  1. `echo "JUPYTERHUB_API_TOKEN=$(openssl rand -hex 32)" >> data/secrets.env`
  2. Update the code (`git pull` and `util/sync-runtime.sh`, or a new bundle).
  3. `./util/gen-env.sh -e data/env -s data/secrets.env`
  4. `docker compose up -d --build`
  5. Check that the old public value now gets 403 from `/jupyter/hub/api/users`.

  If step 1 or 3 is skipped, gen-env or compose stops with "JUPYTERHUB_API_TOKEN is required", and the containers already running keep running.
- **The old token stops working at the next hub start.** That start, like any hub restart, stops users' running notebook servers. JupyterHub's `cleanup_servers` defaults to on, and our config leaves it on. Files persist in the per-user volumes, but open kernels and unsaved notebook state are lost, so schedule the upgrade when nobody is working. A server starts again at the user's next JupyterHub visit or notebook-assay launch.
- **Rotating the token later** takes only steps 1 (with a new value), 3 and 4.
- **The demo bundle's secrets generator must include the key**, or the next bundle fails at gen-env.

## Amendments during implementation

- **A hub restart stops users' servers.** The plan said users' running servers were unaffected, which is wrong. Recreating or restarting the hub stops them, because `cleanup_servers` is on by default. This was already the case for every hub restart and isn't caused by the token change, but the rollout restarts the hub. The Consequences now say so. Keeping servers running across hub restarts (`c.JupyterHub.cleanup_servers = False`) is a possible follow-up.
- **A test had depended on the public fallback.** `tests/test_upload_workspace_dataset_api.py::test_upload_workspace_datasets_jupyter` passed only because of the fallback; it now sets the variable as compose does. It still fails on HEAD's separate assertion ("uploaded 0 datasets"), which is an earlier test bug.
