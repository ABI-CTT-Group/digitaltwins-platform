# Installing an Airflow remote compute node (from the running platform)

A **compute node** is a stripped-down projection of the platform: a *single*
service — an Airflow **Celery worker** — running on a separate VM, wired back to
the portal's broker / metadata DB / API / MinIO. It runs no control plane of its
own (no scheduler, apiserver, Postgres, or Redis). It serves one or more named
**queues**, so specific workflows can be routed to it (e.g. a GPU box that serves
the `gpu` queue).

Assumptions:
- The compute node and the portal are on the **same VLAN** (private network), and
  the portal is already up and running.
- Config is **derived from the running platform**, not built from scratch — the
  worker reuses the platform's image and its shared secrets (`FERNET_KEY`,
  `REDIS_PASSWORD`, Postgres/MinIO creds) via `generate-compute-env.sh`, so they
  can't drift.

> **STATUS — this is a design/runbook draft on the `remote-compute` branch.**
> It is deliberately kept out of the `env-config-generation` → `main` PR (#266).

## How task routing works (recap)

Airflow Celery routes work by **queue name**:
- A worker serves queues via its start command: `celery worker -q <queues>`.
- A task declares its queue: `SomeOperator(..., queue="gpu")`.
- A task lands on the node whose worker serves that queue; unqueued tasks stay on
  the portal's default worker.

So there are three touch-points that must line up:
1. **Portal** local worker `command:` → serves `default`.
2. **Compute node** worker `command:` → serves `gpu` (via `WORKER_QUEUES`).
3. **DAG** task `queue="gpu"` → sends that workflow to the GPU node.

## Pieces this runbook depends on (to build on this branch first)

These don't exist on the branch yet — they're the remaining feature work:

- **`services/airflow/compute-worker/docker-compose.yml`** — the single-service
  worker compose. Port from `main_buildout:buildout/dev/compute/docker-compose.yml`;
  set `command: celery worker -q ${WORKER_QUEUES:-default}` and add a GPU device
  reservation.
- **`util/generate-compute-env.sh`** — port from `main_buildout:buildout/util/`.
  Sources the platform `.env` and emits the worker `.env` (carrying the shared
  secrets + `MAIN_VM_IP`).
- **generalise `util/ufw_for_remote_compute.sh`** — take the compute node's VLAN
  IP + the port list as arguments instead of the hardcoded values.
- **portal Redis hardening** — a `REDIS_PASSWORD` and publishing Redis on the
  VLAN interface (small change to `services/airflow/docker-compose.yml` / `.env`).
- **`digitaltwins-worker.service`** — port the systemd unit from
  `main_buildout:buildout/dev/compute/`.

---

## A. Portal side (once)

1. **Harden + expose Redis on the VLAN.** Add `REDIS_PASSWORD` to `secrets.env`,
   change the broker URL to `redis://:${REDIS_PASSWORD}@redis:6379/0`, and publish
   `6379` on the VLAN interface. Re-render and apply **without** a wipe:
   ```bash
   util/gen-env.sh -e /mnt/install_src/data/env -s /mnt/install_src/data/secrets.env
   docker compose up -d          # recreates only redis + the airflow services
   ```
2. **Open the firewall to the node** (generalised `ufw_for_remote_compute.sh`):
   allow the compute node's VLAN IP to the Redis, Postgres (`8003`), Airflow API,
   and MinIO (`8011`) ports.
3. **Export the worker image:**
   ```bash
   docker save digitaltwins-platform-airflow-worker:latest | gzip > ~/airflow-worker.tar.gz
   ```

## B. Compute VM prep

1. **Docker + Compose** — see *Installing on a connected machine* in
   [`README.md`](README.md).
2. **GPU (if applicable):** install the NVIDIA driver + `nvidia-container-toolkit`,
   then verify: `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu24.04 nvidia-smi`.
3. `mkdir ~/digitaltwins-compute`.

## C. Bring the platform's environment across

1. **Worker image:** `scp ~/airflow-worker.tar.gz` to the node, then
   `docker load -i airflow-worker.tar.gz`.
2. **Compose:** copy `services/airflow/compute-worker/docker-compose.yml` into
   `~/digitaltwins-compute/`.
3. **`.env` derived from the platform** — on the portal, render it from the live
   `.env`, then copy it over and set the node's queue:
   ```bash
   # on the portal:
   util/generate-compute-env.sh <portal_vlan_ip> > /tmp/compute.env
   # copy /tmp/compute.env -> compute:~/digitaltwins-compute/.env, then on the node:
   echo 'WORKER_QUEUES=gpu' >> ~/digitaltwins-compute/.env
   ```
   This carries the matching `FERNET_KEY`, `REDIS_PASSWORD`, and Postgres/MinIO
   credentials — the reason the node "reuses the existing environment."
4. **DAGs / config / plugins / data:**
   ```bash
   rsync -a <portal>:digitaltwins-platform/services/airflow/{dags,config,plugins,data} \
     ~/digitaltwins-compute/
   ```

## D. Run it

1. `cd ~/digitaltwins-compute && docker compose up -d` (the worker is the whole
   compose).
2. Install the systemd unit so it survives reboot:
   ```bash
   sudo cp digitaltwins-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now digitaltwins-worker
   ```

## E. Verify

1. On the portal, confirm the worker **registered** — Flower on `:5555`, the
   Airflow UI, or a Celery ping. A missing worker usually means the broker isn't
   reachable (VLAN firewall / Redis password mismatch).
2. Trigger a task with `queue="gpu"` and confirm it runs **on the compute node**
   (check the node's task logs / that the task succeeds while the portal worker is
   idle).

---

## Notes

- **The node is a projection of the platform.** Same image, same secrets, same
  DAGs — only `MAIN_VM_IP` (→ portal VLAN IP) and `WORKER_QUEUES` (→ `gpu`)
  distinguish it. Adding a second node later is the same procedure with a
  different queue.
- **Fernet key must match** across portal and node (connections/variables in the
  metadata DB are Fernet-encrypted). `generate-compute-env.sh` carries it, so this
  holds automatically — provided the platform's key is wired (it is, as of the
  `AIRFLOW__CORE__FERNET_KEY` fix on `env-config-generation`).
- **DAG code must be present on both sides.** The worker executes the DAG's task
  code, so the `dags/`+`plugins/` trees are synced to the node (step C4). Keep them
  in sync with the portal's the same way (`sync-dags.sh` targets the runtime dags
  dir on each host).
- **GPU access model — the one open design fork.** If a task runs in-process in
  the worker, the *worker image* needs CUDA; if it spins up its own task container
  (e.g. DockerOperator), the GPU flags go on that container instead. Which one
  applies depends on how the first GPU workflow is written.
