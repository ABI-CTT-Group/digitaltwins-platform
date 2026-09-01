# Build a full system — portal (platform + observability) + remote compute

**This is the canonical, ordered runbook.** Follow it top to bottom for a clean
build of a portal (the DigitalTWINS platform *plus* the Grafana/Loki/Mimir
observability stack) and one or more remote compute nodes whose logs and metrics
report back into the portal's observability. Where a step has deep detail, this
doc links to it — but the **order lives here**, and where older docs disagree,
**this doc wins**.

> Worked example IPs (replace with yours): portal VLAN `10.2.0.195`, compute node
> VLAN `10.2.0.14`. Everything runs **locally on each box** (`ansible-playbook -c
> local`), as your **normal login user** (not `sudo ansible-playbook`) — `become`
> escalates per task.

---

## The three roles

| Role | Internet? | What it is |
|---|---|---|
| **Build box** | **Yes** | A machine *you* control (staging/laptop-VM) where the airgap bundle is manufactured. **Never the hospital.** |
| **Portal** | No (airgap) | Runs the platform (docker-compose) + observability (k3s). Installs only from the bundle. |
| **Compute node(s)** | No (airgap) | A clean VM running one Airflow Celery worker + Alloy. Reaches the portal over the VLAN. |

The bundle lives on a **persistent volume** mounted at `/mnt/install_src` that
**survives a VM rebuild** (see [`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md)).

---

## Order at a glance

```
A. BUILD BOX (connected)   build the bundle  ── incl. the obs image bundle
        │  ship the /mnt/install_src volume to each target
        ▼
B. PORTAL   platform           (airgap_build_step3.yml)         install_src=/mnt/install_src
C. PORTAL   observability      (install_observability_airgap.yaml)  install_src=/mnt/install_src/airgap   ← different!
D. PORTAL   open compute-obs ingress  (enable_compute_observability_ingress.yaml)
        │  portal must be fully UP before touching a compute node
        ▼
E. COMPUTE  platform worker    (seed bundle → docker → worker → DAGs)
F. COMPUTE  observability      (install_compute_observability_airgap.yaml)
        ▼
G. VERIFY end to end
```

Two things trip everyone; note them now:
- **`install_src_dir` is different for the two portal playbooks** — platform uses
  `/mnt/install_src`, observability uses `/mnt/install_src/airgap`. Not a typo.
- **The portal must be fully up before the compute node** — the node's `.env`,
  broker, and DAGs all come from a running portal.

---

## A. Build box (connected) — manufacture the bundle

Do this once per release, on a box **with internet**. Full detail:
[`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md).

1. **Code + config into the bundle**
   ```
   # clean_src tracks the release branch; refresh it + submodules
   ( cd /mnt/install_src/clean_src/digitaltwins-platform && git pull \
       && git submodule update --init --recursive )
   # fill in data/env + data/secrets.env (see Phase B.3 for the required keys)
   ```
2. **Internet-only bits** (binaries, apt debs, pip wheels, charts):
   ```
   AIRGAP_DIR=/mnt/install_src/airgap util/fetch_airgap.sh
   util/build-apt-debs.sh          # regenerate the local apt repo (full dep closure)
   ```
3. **Platform images** (docker-compose stack) — build/pull the stack, then freeze:
   ```
   # bring the platform up from source once (connected), verify, then:
   util/freeze_images.sh           # -> /mnt/install_src/digitaltwins-images-all.tar.gz
   docker save digitaltwins-platform-airflow-worker:latest | gzip > /mnt/install_src/airflow-worker.tar.gz
   ```
4. **Observability images** (k3s stack) — **deterministic, chart-driven**, needs
   k3s running on the build box (containerd as the pull engine; no charts deployed):
   ```
   AIRGAP_DIR=/mnt/install_src/airgap util/build_image_bundle.sh
   #  -> airgap/images/k3s-images.tar.gz  (ONE valid multi-image archive)
   #  -> airgap/images/image-list.txt     (the manifest the install verifies against)
   ```
   > This replaces the old capture-from-a-running-stack step. It derives the image
   > set from the Helm charts themselves, so it can't miss a subchart (MinIO) or a
   > hook Job (the make-bucket job) — the exact gap that made airgap installs hang.
5. **Capture k3s app images too** (if you brought the obs stack up connected and
   prefer capturing what actually ran): `AIRGAP_DIR=/mnt/install_src/airgap
   util/fetch_airgap_images.sh` — either script produces the same
   `images/{k3s-images.tar.gz,image-list.txt}` pair. Prefer `build_image_bundle.sh`
   for reproducibility.

**Ship** the `/mnt/install_src` volume (or its contents on media) to each target.

---

## B. Portal — the platform

Detail: [`README.md`](README.md) §0–6.

1. **Mount the bundle** (fstab is on the wiped root disk, so mount once by hand):
   ```
   sudo mkdir -p /mnt/install_src && sudo mount /dev/vdb /mnt/install_src
   sudo /mnt/install_src/clean_src/digitaltwins-platform/util/mount_src.sh
   ```
2. **OS deps + Ansible + Docker** (airgap path — README §2–3):
   ```
   CS=/mnt/install_src/clean_src/digitaltwins-platform
   sudo "$CS/util/install-apt-debs.sh"                       # unzip, pip, … (also masks the esm-cache hang)
   tar xzf /mnt/install_src/ansible-packages.tar.gz -C ~ \
     && pip3 install --no-index --find-links ~/ansible-packages/ ansible --break-system-packages
   #   ... log out / back in (PATH) ...
   ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step2.yml" \
     -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src"
   #   ... log out / back in (docker group) ...
   ```
3. **Configure** `data/env` + `data/secrets.env`. Required for a remote-compute +
   observability build:
   - platform: `PLATFORM_PROTOCOL/PLATFORM_DOMAIN`, `REDIS_PASSWORD` (**required**),
     `REMOTE_COMPUTE=true`, `AIRFLOW_VAR_COMPUTE_QUEUE` (leave `default` for now — see G),
   - observability: `GRAFANA_ADMIN_PASSWORD`, `GRAFANA_OAUTH_SECRET`,
     `MIMIR_MINIO_ROOT_USER`, `MIMIR_MINIO_SECRET_KEY`.
   > `GRAFANA_OAUTH_SECRET` must be **identical** on the Keycloak side (rendered by
   > `gen-realm.sh`, imported **first-boot only**) and the Grafana side (shell env at
   > obs-playbook time). Source `secrets.env` for both so they can't drift.
4. **Deploy the platform** — `install_src` is **`/mnt/install_src`** here:
   ```
   ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step3.yml" \
     -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src"
   ```
   Do **not** `export COMPOSE_FILE` in your shell — it overrides `.env` and silently
   drops the remote-compute override.
5. **DAGs** (not in the bundle): sync from your DAG source, then **un-pause**:
   ```
   util/sync-dags.sh <dag-source-box> <this-box>     # wait ~1 min for the dag-processor
   ```
6. **Verify** the platform (README §6): the stack is up, and the Airflow API token
   works (fresh Keycloak+Airflow creates the local `admin1` automatically):
   ```
   docker compose exec -T digitaltwins-api python -c "import os,requests;r=requests.post(os.environ['AIRFLOW_ENDPOINT']+'/auth/token',json={'username':os.environ['AIRFLOW_USERNAME'],'password':os.environ['AIRFLOW_PASSWORD']},timeout=30);print('HTTP',r.status_code)"
   ```
   Expect `HTTP 200`.

---

## C. Portal — observability

Detail: [`README.md`](README.md) → *Observability*. `install_src` is
**`/mnt/install_src/airgap`** here (binaries + the image bundle live under `airgap/`).

```
CS=/mnt/install_src/clean_src/digitaltwins-platform
set -a; . /mnt/install_src/data/secrets.env; . /mnt/install_src/data/env; set +a
ansible-playbook -i 'localhost,' -c local \
  -e "ansible_user=$(whoami)" \
  -e "install_src_dir=/mnt/install_src/airgap" \
  "$CS/util/install_observability_airgap.yaml"
```

The playbook now **imports the image bundle and verifies it before deploying
anything**: if any image is missing from containerd it fails *immediately* with the
list (rebuild the bundle with `build_image_bundle.sh` — Phase A.4), instead of a
30-minute Helm `ImagePullBackOff` timeout. When it finishes, `https://<domain>/grafana`
works.

---

## D. Portal — open the ingress for compute-node observability

So a compute node's Alloy can reach Loki `:3100` / Mimir `:9005` over the VLAN:

```
ansible-playbook -i 'localhost,' -c local -e "ansible_user=$(whoami)" \
  -e "compute_node_ip=10.2.0.14" \
  util/enable_compute_observability_ingress.yaml
```

**Also open `3100` and `9005` to `10.2.0.14` in the cloud security group** — Ansible
can't touch that layer. (The playbook opens ufw and ensures the port-forwards bind
`0.0.0.0`.)

---

## E. Compute node — the platform worker

Detail: [`compute-node-README.md`](compute-node-README.md) §A–F. **Portal must be up first.**

1. **Seed the node's bundle** from the portal (only the subset a node needs):
   ```
   # on the PORTAL:
   util/compute-build.sh ubuntu@10.2.0.14
   # SSH_OPTS='-J <portal>' util/compute-build.sh ubuntu@10.2.0.14   # if node is reachable only via the portal
   ```
2. **On the node**: mount the volume (if separate), then OS deps + Ansible + Docker
   — same three commands as Phase B.2, run on the node.
3. **Node `.env`** (from the running portal), image, worker (README/compute §C–D):
   ```
   # on the PORTAL: generate the node env, carrying the shared secrets
   util/generate-compute-env.sh 10.2.0.195 ~/digitaltwins-platform/.env > /tmp/compute.env
   docker save digitaltwins-platform-airflow-worker:latest | gzip > ~/airflow-worker.tar.gz
   # open the worker ports to the node (ufw + security group): 8002/8003/8005/8010/8011
   util/ufw_for_remote_compute.sh 10.2.0.14
   ```
   ```
   # on the NODE:
   mkdir -p ~/digitaltwins-compute/{dags,config,plugins,data,logs} && cd ~/digitaltwins-compute
   #   ...copy compute.env -> .env, set WORKER_QUEUES=remote, docker load the worker image...
   docker compose up -d
   sudo cp digitaltwins-worker.service /etc/systemd/system/ && sudo systemctl enable --now digitaltwins-worker
   ```
4. **DAGs to the node** (from the portal): `util/sync-compute-dags.sh 10.2.0.14`
5. **Confirm** the node joined the queue — on the portal:
   ```
   docker compose exec airflow-scheduler \
     celery --app airflow.providers.celery.executors.celery_executor.app inspect active_queues
   ```
   Expect `celery@<node> -> remote`.

---

## F. Compute node — observability (Alloy)

Detail: [`compute-node-README.md`](compute-node-README.md) §G. On the **node**:

```
# quick reachability check first (catches a closed security group in 2s):
curl -sS http://10.2.0.195:3100/ready && echo " loki ok"
curl -sS http://10.2.0.195:9005/ready && echo " mimir ok"

ansible-playbook -i 'localhost,' -c local -e "ansible_user=$(whoami)" \
  -e "obs_host=10.2.0.195" \
  /mnt/install_src/clean_src/digitaltwins-platform/util/install_compute_observability_airgap.yaml
```

Alloy runs as your **login user** (reads the world-readable task logs, in the
docker group) — no dedicated user, no ACL/chmod.

---

## G. Verify end to end

1. **Route work to the node** — only now that it's serving `remote` (else tasks hang
   `queued`). On the portal, set `AIRFLOW_VAR_COMPUTE_QUEUE=remote` in `data/env`,
   re-run `gen-env.sh`, `docker compose up -d` to recreate; or set the Airflow
   Variable directly:
   ```
   docker compose exec -T airflow-scheduler airflow variables set compute_queue remote
   ```
2. **Drive load** — trigger the `cpu_burn_primes` DAG (unpaused on creation). It burns
   CPU on the node for a few minutes.
3. **See it in Grafana** (`https://<domain>/grafana` → Explore):
   - Logs (`dititaltwins-log`): `{node="drai-compute"}` and `{job="airflow-task"}`
   - Metrics (`dititaltwins-metric`): `node_load1{node="drai-compute"}` — climbs during the burn
   - Or straight from the box, no Grafana:
     `curl -sG http://localhost:3100/loki/api/v1/label/node/values`

---

## Where each detailed doc lives (so you stop hunting)

| You want… | Read |
|---|---|
| **The ordered build (this)** | `util/BUILD-FULL-SYSTEM.md` |
| Bundle contents + how to (re)build each piece | `util/INSTALL-BUNDLE.md` |
| Portal platform install, step by step | `util/README.md` §0–6 |
| Portal observability install + day-2 changes | `util/README.md` → Observability |
| Remote compute node (worker + its Alloy) | `util/compute-node-README.md` |
| "It's broken" — fix recipes | `docs/diagnostics.md` |
| Airflow API auth 401 (assay launch → no run) | `docs/airflow-api-auth-regression.md` |

**Precedence:** if the order in any of the above disagrees with this file, follow
**this file**. The others are correct for their piece; this one owns how the pieces
compose.
