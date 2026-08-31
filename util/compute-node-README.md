# Installing a remote Airflow compute node

A compute node is a **single Airflow Celery worker** on its own VM that joins the
portal's Airflow cluster over the VLAN and runs tasks tagged for its queue (e.g.
`remote`). It runs **no platform of its own** — the scheduler, apiserver, Postgres,
Redis, MinIO and Keycloak all live on the portal.

> ### ⚠️ The compute VM MUST be clean
> A fresh VM with **only** Docker installed. Do **not** run the platform on it and
> do **not** reuse a box that already runs one — you'll end up with a second
> Airflow cluster fighting the first, and tasks landing on the wrong worker.
> Before you start, `docker ps` on the node should show **nothing** (or only
> containers you put there).

Everything is driven from the portal (`MAIN_VM_IP`), and the shared secrets come
straight from the portal's `.env`, so nothing drifts.

Both the portal and this node **boot their stack the same way** — a systemd unit
running `docker compose up -d` (`digitaltwins-platform.service` on the portal,
`digitaltwins-worker.service` here), with the compose file set taken from
`COMPOSE_FILE` in each host's `.env`. The unit reconverges the stack to the files
on every boot; the containers' `restart:` policies handle mid-run crashes.

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

1. **Publish Redis on the VLAN** so the remote worker can reach the broker. (Redis
   is *always* password-protected in the base compose now — `REMOTE_COMPUTE=true`
   only adds the VLAN port publish.) Set `REDIS_PASSWORD` in `secrets.env`, and
   `REMOTE_COMPUTE=true` **plus** `AIRFLOW_VAR_COMPUTE_QUEUE=remote` (routes DAGs to
   the node — see §E/gotchas) in the env inputs, re-render `.env`, and bring the
   stack up — `COMPOSE_FILE` in `.env` then pulls in the remote-compute override
   automatically, no `-f` flags:
   ```bash
   cd ~/digitaltwins-platform
   util/gen-env.sh -e <env> -s <secrets.env>   # renders COMPOSE_FILE=…:remote-compute.override.yml into .env
   docker compose up -d
   docker compose ps redis    # expect 0.0.0.0:8005->6379
   ```
   (On a playbook rebuild this is automatic — step3 sets it from `REMOTE_COMPUTE`
   and installs the `digitaltwins-platform.service` boot unit.)
   > **Pure-remote vs hybrid — stopping the portal's local worker.** By default
   > the portal keeps its own `airflow-worker` on the `default` queue (hybrid:
   > `default` locally + `remote` on the node). If you want *all* tasks to run on the remote
   > node instead, stop the local worker — and do it so it survives `up -d`, which
   > otherwise restarts a merely-stopped service:
   > ```bash
   > docker compose up -d --scale airflow-worker=0
   > ```
   > (`docker compose ... stop airflow-worker` stops it now, but the next `up -d`
   > brings it back.) This matters: the child workflow_* DAG tasks reach the
   > platform's services (DigitalTWINS API, MinIO) at absolute VLAN endpoints set
   > per-worker, so a *hybrid* split only works if every worker resolves the same
   > endpoints — pure-remote (a single worker) sidesteps that. Confirm one node:
   > ```bash
   > docker compose exec airflow-scheduler celery \
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

   > **SSH-hopping to the node to build it.** The node is often only reachable by
   > jumping through the portal (`ssh -J <portal> ubuntu@10.2.0.14`). If the portal's
   > ufw is `default deny (outgoing)` (check `sudo ufw status verbose`), that hop is
   > blocked — allow the outbound SSH on the **portal**:
   > ```bash
   > sudo ufw allow out to 10.2.0.14 port 22 proto tcp
   > ```
   > (If instead the *node's* ufw denies inbound 22, allow it there:
   > `sudo ufw allow from <portal_ip> to any port 22 proto tcp`.) The worker-port
   > script above does **not** open 22 — SSH access is separate.
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

0. **Seed the node's bundle (airgapped nodes).** A remote node has no internet, so
   it installs from its own `/mnt/install_src` — the subset a *node* needs, not the
   portal's 6.3G image bundle. From the **portal**, push it over the VLAN:
   ```bash
   # refresh the code first so the node gets the latest scripts
   ( cd /mnt/install_src/clean_src/digitaltwins-platform && git pull \
       && git submodule update --init --recursive )
   util/compute-build.sh ubuntu@10.2.0.14           # creates /mnt/install_src on the node + copies
   # SSH_OPTS='-J abi_portal' util/compute-build.sh ubuntu@10.2.0.14   # if the node is only reachable via the portal
   ```
   (Want it to survive a node rebuild? Mount a persistent volume at
   `/mnt/install_src` on the node *first* — otherwise it lands on the root disk.)

1. **Install Docker** (+ NVIDIA container toolkit if this is a GPU node).
   - **Airgapped node** (no internet — the usual case): install from the seeded
     bundle. It's the same three steps as the portal's airgap install
     ([`README.md`](README.md) §1–§3) but you **stop before step3** (that's the
     full platform). `compute-build.sh` above prints the exact commands
     (`install-apt-debs.sh` → ansible from wheels → `util/airgap_build_step2.yml`).
   - **Connected node**: install Docker the normal way — the "Installing on a
     connected machine" section of [`README.md`](README.md).
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
sed -i 's/^WORKER_QUEUES=.*/WORKER_QUEUES=remote/' .env   # the queue THIS node serves
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
   You should see this node's `celery@<hostname>` listed against **`remote`** (the
   portal's own worker is a separate entry on `default`).
2. **Run a task through it.** With `AIRFLOW_VAR_COMPUTE_QUEUE=remote` set on the
   portal, a DAG whose tasks read `Variable.get("compute_queue")` route here (or
   hardcode `queue="remote"` on a task). **Un-pause the DAG** (paused by default)
   and trigger it. Watch it land on the node:
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
- A child `workflow_{seek_id}` DAG that the API triggers (one run per sample) must
  exist AND be synced here too, or its tasks 404 / never land. Keep the portal and
  node DAG folders identical (that's what `--delete` is for).

---

## G. Ship telemetry to the observability stack (optional)

Get this node into Grafana alongside the portal — its docker container logs
(incl. the celery worker), its **Airflow task/DAG-run logs**, and host metrics all
flow to the portal's Loki/Mimir over the VLAN. One **Alloy** systemd service on the
node does it; nothing extra runs on the portal beyond opening two ports.

The node ships to the portal's ingest ports — Loki `:3100`, Mimir `:9005` — which
the observability install port-forwards. They're loopback-only until you expose
them, exactly like the other portal↔worker ports.

**1. Portal side (once).** Bind the Loki/Mimir port-forwards to the VLAN. A fresh
observability install already does this; to rebind a **running** install, re-run
the observability playbook — or do it live (faster). ⚠️ The live rebind has a sharp
edge (detached `kubectl` procs survive `restart`, and a `127.0.0.1` listener blocks
the `0.0.0.0` bind) — follow the **stop → kill-by-port → confirm-free → start**
recipe in [`docs/diagnostics.md`](../docs/diagnostics.md) → "Observability
port-forwards won't rebind to `0.0.0.0`", not a naive `sed` + `restart`. Then open
the two ports to **this node only**:

```
util/ufw_for_remote_compute.sh 10.2.0.14 3100 9005
```

On OpenStack/NeCTAR, also open `3100` and `9005` to `10.2.0.14` in the **security
group** (never `0.0.0.0/0`) — the same layer you opened 8002/8003/… in.

**2. Node side.** From a checkout of this repo on the node, point it at the
portal's VLAN IP (Loki is single-tenant and Mimir writes the `anonymous` tenant,
so no token — the `node` label separates this box from the portal):

```
util/install-compute-alloy.sh 10.2.0.195
# 2nd arg overrides the bundle dir if not /mnt/install_src/airgap
```

It pulls the `alloy` binary from the install bundle (airgap-safe), renders
`util/observability/config.alloy.compute` with this host's name + the portal IP,
installs `alloy.service`, and starts it.

**3. Verify (from the portal's Grafana).** Explore →
- Loki: `{node="drai-compute"}` (container logs) and `{job="airflow-task"}` (task
  logs; `dag_id`/`task_id` are labels, `run_id`/`attempt` are structured metadata).
- Mimir: `up{node="drai-compute"}`, plus the node-exporter dashboards.

If nothing arrives: `journalctl -u alloy -f` on the node, and re-check that the
portal bound 3100/9005 to `0.0.0.0` and opened them (ufw **and** security group)
to this node.

> **Task logs work with zero compose changes** — the worker already bind-mounts
> `./logs:/opt/airflow/logs` and keeps a local copy of each task log even with
> REMOTE_LOGGING to MinIO on, so Alloy tails them straight off the host. MinIO
> stays the system-of-record for the Airflow UI; Loki is the searchable/audit copy.

---

## Gotchas (learned the hard way)

- **Clean VM only.** If the node already runs a platform, its own `airflow-worker`
  competes for tasks and everything gets tangled. `docker ps` on the node should
  show only what you put there.
- **DAGs are paused by default** (`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION`).
  A paused DAG leaves tasks sitting in `queued` forever — un-pause it.
- **Routing is by Celery queue, and the platform lever is the `compute_queue`
  Airflow Variable.** Set `AIRFLOW_VAR_COMPUTE_QUEUE=remote` on the portal and DAGs
  that call `Variable.get("compute_queue", "default")` route here; untagged /
  `default` tasks stay on the portal's local worker. **This only works if the DAG
  actually reads that Variable** — a DAG with no `queue` and no
  `Variable.get("compute_queue")` runs on `default` regardless of the env var, so
  its tasks land on the local worker, not here. Per-task `queue="remote"` is the
  hardcoded alternative.
- **Execution API is internal — never public.** Reach it over the VLAN on
  `MAIN_VM_IP:8002`, not the gateway. If the direct port is unreachable, the
  blocker is usually the **cloud security group** (a layer below ufw) — open 8002
  there **restricted to this node's private IP**, don't route it over the public
  gateway (it's a machine-to-machine API and shouldn't face the internet).
- **`WORKER_QUEUES` defaults to `default`** in the generated `.env` — the `sed` in
  step D sets it to `remote`. If you edit `.env` after the worker is up, you must
  `docker compose up -d --force-recreate` (Compose bakes the queue into the
  command at create time).
- **Shared `FERNET_KEY`** must match the portal (it does — `generate-compute-env`
  carries it). Connections/Variables in the metadata DB are Fernet-encrypted.
- **Open item — worker↔apiserver JWT:** if a task reaches the node but errors
  authenticating to the execution API, the platform may need an explicit shared
  `AIRFLOW__API_AUTH__JWT_SECRET` on both sides. Verify at first run.
