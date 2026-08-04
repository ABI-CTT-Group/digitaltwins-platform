# Installing a remote Airflow compute node

A compute node is a **single Airflow Celery worker** on its own VM that joins the
portal's Airflow cluster over the VLAN and runs tasks tagged for its queue (e.g.
`gpu`). It runs **no platform of its own** — the scheduler, apiserver, Postgres,
Redis, MinIO and Keycloak all live on the portal.

> ### ⚠️ The compute VM MUST be clean
> A fresh VM with **only** Docker installed. Do **not** run the platform on it and
> do **not** reuse a box that already runs one — you'll end up with a second
> Airflow cluster fighting the first, and tasks landing on the wrong worker.
> Before you start, `docker ps` on the node should show **nothing** (or only
> containers you put there).

Everything is driven from the portal (`MAIN_VM_IP`), and the shared secrets come
straight from the portal's `.env`, so nothing drifts.

## Connection contract

The worker reaches the portal two ways:

| Portal service | How the worker reaches it | Why |
|---|---|---|
| **Redis** (broker) | direct VLAN port `MAIN_VM_IP:8005` | raw TCP — can't go through the http gateway |
| **Postgres** (metadata + result backend) | direct VLAN port `MAIN_VM_IP:8003` | raw TCP |
| **MinIO** (S3 — task logs/data) | direct VLAN port `MAIN_VM_IP:8011` | S3 API (the gateway `/minio` route is the GUI, not the API) |
| **DigitalTWINS API** | direct VLAN port `MAIN_VM_IP:8010` | — |
| **Airflow execution API** | direct VLAN port `MAIN_VM_IP:8002` | machine-to-machine API — keep it **internal**, never the public gateway |
| **Keycloak** (token issuer) | **gateway** `https://<domain>/auth` | canonical token issuer; internal `keycloak` host is unreachable off-box |

So the node needs the portal's **direct ports 8003/8005/8002/8011/8010** opened to
it (in ufw **and** the cloud security group — see below), and it must reach the
portal's **gateway on 443** by domain name (for Keycloak only).

> **Do not expose the execution API on the public gateway.** It's an internal
> worker↔apiserver API; route it over the VLAN direct port and open `8002` in the
> cloud security group **restricted to the node's private IP** — never `0.0.0.0/0`.

---

## A. Portal side (run once, on the portal)

Values used below: portal VLAN IP `10.2.0.195`, compute node VLAN IP `10.2.0.14`.

1. **Redis published + password-protected** (so a remote worker can use the broker).
   Ensure `REDIS_PASSWORD` is set in `secrets.env`/`.env`, then bring the stack up
   with the remote-compute override (or set it in `COMPOSE_FILE`):
   ```bash
   cd ~/digitaltwins-platform
   docker compose -f docker-compose.yml -f services/airflow/remote-compute.override.yml up -d
   docker compose ps redis    # expect 0.0.0.0:8005->6379
   ```
   > **Pure-remote vs hybrid — stopping the portal's local worker.** By default
   > the portal keeps its own `airflow-worker` on the `default` queue (hybrid:
   > local `default` + remote `gpu`). If you want *all* tasks to run on the remote
   > node instead, stop the local worker — and do it so it survives `up -d`, which
   > otherwise restarts a merely-stopped service:
   > ```bash
   > docker compose -f docker-compose.yml -f services/airflow/remote-compute.override.yml \
   >   up -d --scale airflow-worker=0
   > ```
   > (`docker compose ... stop airflow-worker` stops it now, but the next `up -d`
   > brings it back.) This matters: the preprocessor passes an absolute API URL
   > through XCom, so a *hybrid* split only works if every worker resolves the same
   > endpoints — pure-remote (a single worker) sidesteps that. Confirm one node:
   > ```bash
   > docker compose -f docker-compose.yml -f services/airflow/remote-compute.override.yml \
   >   exec airflow-scheduler celery \
   >   --app airflow.providers.celery.executors.celery_executor.app inspect active_queues
   > ```
2. **Open the firewall** to the node's VLAN IP (raw-TCP ports only; the gateway's
   443 is already public):
   ```bash
   util/ufw_for_remote_compute.sh 10.2.0.14      # opens 8003 8005 8002 8011 8010
   ```
   On OpenStack/NeCTAR, also open these to `10.2.0.14` in the **security group**
   (a separate firewall layer below ufw) — `8002` in particular tends to be
   blocked there. Restrict to the node's private IP, never `0.0.0.0/0`.
3. **Generate the node's `.env`** from the running platform (carries the shared
   Fernet/DB/Redis/MinIO/Keycloak secrets, the ports, and the domain):
   ```bash
   util/generate-compute-env.sh 10.2.0.195 ~/digitaltwins-platform/.env > /tmp/compute.env
   ```
4. **Export the worker image**:
   ```bash
   docker save digitaltwins-platform-airflow-worker:latest | gzip > ~/airflow-worker.tar.gz
   ```

## B. Compute VM (a CLEAN VM)

1. **Install Docker** (+ NVIDIA container toolkit if this is a GPU node) — see the
   "Installing on a connected machine" section of [`README.md`](README.md).
2. **Working dir**:
   ```bash
   mkdir -p ~/digitaltwins-compute/{dags,config,plugins,data,logs} && cd ~/digitaltwins-compute
   ```
3. **Resolve the portal's domain to the portal over the VLAN** (the worker hits the
   gateway by name for the execution API + Keycloak):
   ```bash
   echo '10.2.0.195  <PLATFORM_DOMAIN>' | sudo tee -a /etc/hosts    # your real domain
   ```

## C. Copy from the portal → node

From the portal:
```bash
CS=/mnt/install_src/clean_src/digitaltwins-platform
scp ~/airflow-worker.tar.gz /tmp/compute.env 10.2.0.14:~/
scp $CS/services/airflow/compute-worker/docker-compose.yml \
    $CS/services/airflow/compute-worker/digitaltwins-worker.service 10.2.0.14:~/digitaltwins-compute/
util/sync-compute-dags.sh 10.2.0.14      # dags + plugins + config (see §F)
# data/ is workflow scratch, not code — copy it only if a DAG needs seed data:
rsync -a ~/digitaltwins-platform/services/airflow/data/ 10.2.0.14:~/digitaltwins-compute/data/
```

## D. Configure + run (on the node)

```bash
cd ~/digitaltwins-compute
mv ~/compute.env .env
sed -i 's/^WORKER_QUEUES=.*/WORKER_QUEUES=gpu/' .env      # the queue THIS node serves
docker load -i ~/airflow-worker.tar.gz

# GPU nodes: uncomment the `gpus: all` / deploy.resources block in docker-compose.yml
docker compose up -d
sudo cp digitaltwins-worker.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now digitaltwins-worker
```

## E. Verify

1. **The node is registered on the right queue** — on the **portal**:
   ```bash
   docker compose exec airflow-scheduler \
     celery --app airflow.providers.celery.executors.celery_executor.app inspect active_queues
   ```
   You should see this node's `celery@<hostname>` listed against **`gpu`** (the
   portal's own worker is a separate entry on `default`).
2. **Run a task through it.** Pick (or make) a DAG task tagged `queue="gpu"`,
   **un-pause the DAG** (they're paused by default), and trigger it. Watch it land
   on the node:
   ```bash
   cd ~/digitaltwins-compute && docker compose logs -f airflow-worker
   ```

## F. Keeping DAGs in sync (ongoing)

A remote worker only runs the code in **its own** `dags/` folder — it does NOT
read the portal's. So every time the DAGs change on the portal (they're managed
outside the repo and edited often), push them to the node. From the **portal**:

```bash
util/sync-compute-dags.sh 10.2.0.14           # dags + plugins + config -> the node
util/sync-compute-dags.sh 10.2.0.14 --delete  # same, but also prune DAGs deleted on the portal
```

- No worker restart needed — the worker re-parses each DAG file per task run.
- **New DAGs boot PAUSED** — un-pause them (portal UI) or they sit `queued`.
- A child `workflow_{seek_id}` DAG that the preprocessor triggers must exist AND
  be synced here too, or its tasks 404 / never land. Keep the portal and node
  DAG folders identical (that's what `--delete` is for).

---

## Gotchas (learned the hard way)

- **Clean VM only.** If the node already runs a platform, its own `airflow-worker`
  competes for tasks and everything gets tangled. `docker ps` on the node should
  show only what you put there.
- **DAGs are paused by default** (`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION`).
  A paused DAG leaves tasks sitting in `queued` forever — un-pause it.
- **Only `queue="gpu"` tasks reach this node.** Untagged tasks go to `default`,
  which the portal's local worker serves. To offload work here, tag the task (or
  set the DAG's default queue).
- **Execution API is internal — never public.** Reach it over the VLAN on
  `MAIN_VM_IP:8002`, not the gateway. If the direct port is unreachable, the
  blocker is usually the **cloud security group** (a layer below ufw) — open 8002
  there **restricted to this node's private IP**, don't route it over the public
  gateway (it's a machine-to-machine API and shouldn't face the internet).
- **`WORKER_QUEUES` defaults to `default`** in the generated `.env` — the `sed` in
  step D sets it to `gpu`. If you edit `.env` after the worker is up, you must
  `docker compose up -d --force-recreate` (Compose bakes the queue into the
  command at create time).
- **Shared `FERNET_KEY`** must match the portal (it does — `generate-compute-env`
  carries it). Connections/Variables in the metadata DB are Fernet-encrypted.
- **Open item — worker↔apiserver JWT:** if a task reaches the node but errors
  authenticating to the execution API, the platform may need an explicit shared
  `AIRFLOW__API_AUTH__JWT_SECRET` on both sides. Verify at first run.
