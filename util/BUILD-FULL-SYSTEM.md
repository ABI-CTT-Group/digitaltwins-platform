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

## A. Build box (connected) — manufacture the bundle from scratch

> **Prefer one command:** `util/build-bundle.sh` runs everything in A.0.1–A.5 below,
> verifies each step, self-re-execs for the docker group (no logout), and ends on the
> A.5 gate — so you get either `== BUNDLE COMPLETE ==` or a precise STOP naming what's
> wrong. It's idempotent (`--force` to redo, `--gate-only` to just re-check,
> `--from <phase>` to resume). The manual steps below are exactly what it automates —
> read them to understand it or to debug a step it stops on.
> ```
> ./util/build-bundle.sh            # full build + gate  (fill data/env + data/secrets.env when it stops on first run)
> ./util/build-bundle.sh --gate-only   # just verify the bundle is complete
> ```

Do this once per release, on a box **with internet**. This section is complete on
its own: starting from **only `clean_src/` + `data/`**, it regenerates every other
piece of `/mnt/install_src`. Per-piece "what/why" detail:
[`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md) → *Bundle contents & how to (re)build each piece*.

> **The two things `clean_src` can NOT give you** (provide them yourself):
> - **`data/`** — `data/env`, `data/secrets.env`, and the TLS cert are *config*, not
>   code. Fill env/secrets from the `.template` files; obtain the cert (LE DNS-01 /
>   institutional). Keep `data/` across a reset — losing it means re-entering all
>   secrets.
> - **Build-box tooling** — this box needs `docker`, `ansible`, `k3s` + `helm`, and
>   `dpkg-dev`, installed the normal *connected* way ([`README.md`](README.md) →
>   *Installing on a connected machine*). You're building the bundle that bootstraps
>   the airgapped targets, so the build box bootstraps itself from the internet.

### A.0  Reset to a clean starting point
Keep only the two non-regenerable dirs, wipe the rest:
```
cd /mnt/install_src
# (keep clean_src/ and data/; remove the generated artifacts)
rm -rf airgap ansible-packages.tar.gz *.tgz docker-compose-linux-* \
       digitaltwins-images-all.tar.gz airflow-worker.tar.gz alpine.tar letsencrypt.tar
CS=/mnt/install_src/clean_src/digitaltwins-platform
```
> **Also wipe docker volumes if this box has run the platform before.** Volumes
> live on the docker root, NOT under `/mnt/install_src`, so the reset above leaves
> stale SEEK/Postgres/MinIO data behind — which contaminates the build (e.g. A.3
> aborts with "Email has already been taken" from a leftover SEEK admin). For a
> truly clean bundle build:
> ```
> ( cd ~/digitaltwins-platform && docker compose down 2>/dev/null ) || true
> "$CS/util/docker_delete_volumes.sh"     # removes digitaltwins-platform* volumes
> ```
> (Skip this on a fresh VM that never ran the stack — there's nothing to wipe.)

### A.0.1  Bootstrap the build box (fresh VM only)
A brand-new connected VM has none of the tooling Phase A drives. This box is
connected and disposable, so it bootstraps itself from the internet (unlike the
airgapped targets, which get everything from the bundle it builds). Install
whatever's missing:
```
# Docker + compose plugin (official convenience script), then join the docker group:
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"      # then log out / back in

# Ansible (runs the playbooks) + dpkg-dev (build-apt-debs.sh) + pip3 (A.2's
# `pip3 download ansible` — not shipped on a fresh Ubuntu 24.04):
sudo apt-get update && sudo apt-get install -y ansible dpkg-dev python3-pip

# k3s — its containerd is the pull/export engine for build_image_bundle.sh (A.4).
# Pin to the bundle's K3S_VERSION (see util/fetch_airgap.sh) so it matches the
# target's k3s; plain 'sh -' takes latest, which is fine for image pull/export:
curl -sfL https://get.k3s.io | sh -

# helm — client-side chart templating for build_image_bundle.sh (A.4):
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```
> Verify before continuing: `docker ps`, `ansible --version`,
> `sudo k3s ctr version`, `helm version`. All four must work.

### A.1  Code + config

**Get `clean_src`** — clone from scratch, or refresh if you kept it in A.0:
```
BRANCH=observability-mainline     # the current release branch
mkdir -p /mnt/install_src/clean_src
if [ -d "$CS/.git" ]; then
  ( cd "$CS" && git fetch origin && git checkout "$BRANCH" \
      && git pull && git submodule update --init --recursive )
else
  git clone --recurse-submodules -b "$BRANCH" \
    https://github.com/ABI-CTT-Group/digitaltwins-platform.git \
    /mnt/install_src/clean_src/digitaltwins-platform
fi
```
> Public repos — HTTPS needs no auth (the box's only GitHub block is SSH).
> `--recurse-submodules` checks out the three submodules (portal / api / seek) at
> their pinned commits. **After ANY later `git pull` in `clean_src`, re-run
> `git submodule update --init --recursive`** — a pull moves the submodule pointers
> but doesn't check them out.

**Config** — `data/` is not code, so provide it (absolute paths; cwd-independent):
```
mkdir -p /mnt/install_src/data
[ -f /mnt/install_src/data/env ]         || cp "$CS/env.template"         /mnt/install_src/data/env
[ -f /mnt/install_src/data/secrets.env ] || cp "$CS/secrets.env.template" /mnt/install_src/data/secrets.env
#   ... edit both (required keys listed in Phase B.3) ...
# TLS cert -> data/<domain>.fullchain.pem/.privkey.pem (+ symlinks); letsencrypt.tar backup
```

> **Optional — `data/public_keys/*.pub` (operator SSH access):** drop any operator SSH
> **public** keys here and A.3 (step3's *"Authorise operator SSH keys"* task) adds each
> one to the deploy user's `~/.ssh/authorized_keys` on the **portal** — so those
> operators can SSH in after the build. Skipped if the dir is absent (dev/localhost).
> **Portal-only:** the compute node runs step2 + the worker compose, **not** step3, so
> it does **not** process `data/public_keys` — set up SSH access to the node separately
> (e.g. generate a key on the portal and authorise it on the node so `ssh <node>` works,
> which `compute-build.sh` / `sync-compute-dags.sh` need).

### A.2  Offline packages + binaries (internet)
Every line here fetches from the internet, so a silent failure here only surfaces
at airgap-install time on a box that can no longer fetch anything. **Verify each
generated piece before moving on** — the inline `test` lines below stop you at the
step instead of three phases later.
```
AIRGAP_DIR=/mnt/install_src/airgap "$CS/util/fetch_airgap.sh"   # k3s/helm/alloy/k9s, pip wheels, k3s system-image tarball
# fetch_airgap does `pip3 download kubernetes` internally, so it needs pip3 (A.0.1).
# Verify BOTH the binaries AND the kubernetes wheels landed — the wheels are what the
# observability venv installs, and Step C dies with "No matching distribution ...
# kubernetes" if pip-wheels is empty (pip3 was missing when fetch_airgap ran):
test -s /mnt/install_src/airgap/binaries/alloy-linux-amd64.zip \
  || { echo "STOP: fetch_airgap.sh did not populate airgap/binaries — fix before continuing"; }
ls /mnt/install_src/airgap/pip-wheels/kubernetes-* >/dev/null 2>&1 \
  || { echo "STOP: fetch_airgap.sh did not populate airgap/pip-wheels (kubernetes client) — is pip3 installed (A.0.1)? re-run fetch_airgap"; }

"$CS/util/build-apt-debs.sh"                                    # local apt repo (needs dpkg-dev + internet)
# ^ THE one that silently goes missing: build-apt-debs writes the Packages INDEX
#   that install-apt-debs needs. Without it the airgap install dies with "no
#   Packages index in .../apt-debs". Verify it HERE, not on the airgapped target:
test -s /mnt/install_src/airgap/apt-debs/Packages \
  || { echo "STOP: build-apt-debs.sh did not write airgap/apt-debs/Packages — did it error? is dpkg-dev installed (A.0.1)? fix before continuing"; }

# docker static binaries (airgap_build_step2 on the targets installs these):
wget -O /mnt/install_src/docker-29.4.0.tgz \
  https://download.docker.com/linux/static/stable/x86_64/docker-29.4.0.tgz
wget -O /mnt/install_src/docker-compose-linux-x86_64-v5.1.2 \
  https://github.com/docker/compose/releases/download/v5.1.2/docker-compose-linux-x86_64
# ansible wheels (targets install ansible from these):
pip3 download ansible -d /mnt/install_src/ansible-packages/ \
  && tar -C /mnt/install_src -czf /mnt/install_src/ansible-packages.tar.gz ansible-packages/ \
  && rm -rf /mnt/install_src/ansible-packages/
# offline helper image (stage-dump / minio-logs-init):
docker pull alpine && docker save alpine > /mnt/install_src/alpine.tar
```
> The observability Helm **charts are already in `clean_src`**
> (`util/observability/charts/*.tgz`, committed) — nothing to fetch.

### A.3  Platform images (build from source, then freeze)
Bring the docker-compose platform up **from source** on this connected box, verify
it, then freeze the running images. **step3 reads config + secrets from the SHELL
ENVIRONMENT** (`lookup('env', …)` for `PLATFORM_DOMAIN`, the MySQL passwords, the
SEEK admin creds, …), so you MUST `source` `data/env` + `data/secrets.env` first —
and re-set `CS` if you logged out/in for the docker group (a fresh shell has neither):
```
CS=/mnt/install_src/clean_src/digitaltwins-platform
set -a; . /mnt/install_src/data/secrets.env; . /mnt/install_src/data/env; set +a

ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step3.yml" \
  -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src" -e load_frozen_images=false
#   ... verify the app (README §6) ...
"$CS/util/freeze_images.sh"        # -> /mnt/install_src/digitaltwins-images-all.tar.gz
docker save digitaltwins-platform-airflow-worker:latest | gzip \
  > /mnt/install_src/airflow-worker.tar.gz
```
> **Freeze gotcha:** `freeze_images.sh` saves whatever images exist *right now*, so
> always `git submodule update` + `up -d` first (so one-shot/init images exist to
> capture). A tarball older than your last image build is stale — re-freeze.

### A.4  Observability images (deterministic, chart-driven)
Needs `k3s` + `helm` on this box (k3s's containerd is the pull engine — no charts
need to be deployed):
```
AIRGAP_DIR=/mnt/install_src/airgap "$CS/util/build_image_bundle.sh"
#  -> airgap/images/k3s-images.tar.gz   ONE valid multi-image archive
#  -> airgap/images/image-list.txt      manifest the install verifies against
```
> Derives the image set from the charts themselves, so it can't miss a subchart
> (MinIO) or a hook Job (the make-bucket job) — the gap that hung airgap installs.
> (`util/fetch_airgap_images.sh` is the alternative, capturing from a fully-running
> obs stack; prefer `build_image_bundle.sh` for reproducibility.)

### A.5  Confirm the bundle is complete — GREEN LIGHT before you drop the build box
This checks the pieces that actually break an airgap install — the apt repo **index**
(not just the debs), the image bundle, the binaries — not merely that directories
exist. Run it on the build box; only ship / drop when it prints **BUNDLE COMPLETE**:
```
cd /mnt/install_src; ok=1
for f in \
  clean_src data data/env data/secrets.env \
  ansible-packages.tar.gz alpine.tar \
  docker-*.tgz docker-compose-linux-x86_64-* \
  digitaltwins-images-all.tar.gz airflow-worker.tar.gz \
  airgap/apt-debs/Packages airgap/apt-debs/INSTALL.list \
  airgap/binaries/alloy-linux-amd64.zip airgap/binaries/k3s airgap/binaries/k3s-airgap-images-amd64.tar.gz \
  airgap/binaries/helm-linux-amd64.tar.gz airgap/pip-wheels/kubernetes-* \
  airgap/images/k3s-images.tar.gz airgap/images/image-list.txt ; do
  if ls -d $f >/dev/null 2>&1; then echo "OK       $f"; else echo "MISSING  $f"; ok=0; fi
done
[ "$ok" = 1 ] && echo "== BUNDLE COMPLETE ==" || echo "== BUNDLE INCOMPLETE — do NOT drop the build box =="
```
> `airgap/apt-debs/Packages` is the one that bites: `build-apt-debs.sh` writes it,
> and without it `install-apt-debs.sh` on the target fails with "no Packages index".
> A bundle can look present (dirs exist) yet be missing this — hence the explicit check.

**Ship** the `/mnt/install_src` volume (or its contents on media) to each target.

---

## B. Portal — the platform

Detail: [`README.md`](README.md) §0–6.

> **(Optional — do this FIRST) Airgap the VM.** If this box is meant to be airgapped
> and isn't yet, **cut its internet now**, before you install anything from the bundle,
> so the install genuinely proves the offline path (nothing silently pulled from the
> net masking a bundle gap). See [`README.md`](README.md) → *§1 Airgap the VM* for the
> ufw recipe. Skip if it's already airgapped, or if you're deliberately validating
> connected. (Forgetting this is why an install can "work" yet still fail when done
> for real — the whole point of the bundle is that it needs no internet.)

1. **Mount the bundle** (fstab is on the wiped root disk, so mount once by hand):
   ```
   sudo mkdir -p /mnt/install_src && sudo mount /dev/vdb /mnt/install_src
   sudo /mnt/install_src/clean_src/digitaltwins-platform/util/mount_src.sh
   ```
   > **(Optional) operator SSH access to the portal.** Put the operators' SSH **public**
   > keys in `data/public_keys/*.pub` (they ride along on the volume from the build). The
   > platform deploy below (B.4 / step3) authorises each into the deploy user's
   > `~/.ssh/authorized_keys`, so those people can `ssh` the portal after the build (see
   > A.1). If you *also* want them to reach the **compute node**, run `authorise-keys.yaml`
   > there — Phase E step 6.
2. **OS deps + Ansible + Docker** (airgap path — README §2–3):
   ```
   CS=/mnt/install_src/clean_src/digitaltwins-platform
   sudo "$CS/util/install-apt-debs.sh"                       # unzip, pip, … (also masks the esm-cache hang)
   tar xzf /mnt/install_src/ansible-packages.tar.gz -C ~ \
     && pip3 install --no-index --find-links ~/ansible-packages/ ansible --break-system-packages
   export PATH="$HOME/.local/bin:$PATH"     # ansible-playbook lands here — no logout needed
   ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step2.yml" \
     -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src"
   ```
   Docker is now installed. If a later docker step fails with **permission denied**
   (not "command not found"), activate the docker group without a logout:
   ```
   newgrp docker      # starts a subshell WITH the group; then re-set CS + re-run. (Or just log out / back in.)
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
4. **Deploy the platform** — `install_src` is **`/mnt/install_src`** here. step3
   reads config + secrets from the **shell environment** (`PLATFORM_DOMAIN`, MySQL +
   SEEK creds, …), so source `data/env` + `data/secrets.env` first:
   ```
   CS=/mnt/install_src/clean_src/digitaltwins-platform
   set -a; . /mnt/install_src/data/secrets.env; . /mnt/install_src/data/env; set +a
   ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step3.yml" \
     -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src"
   ```
   Do **not** `export COMPOSE_FILE` in your shell — it overrides `.env` and silently
   drops the remote-compute override.
5. **(Optional) Seed with a `stage-dump`.** To bring an existing instance's data
   into this fresh one, restore a `stage-dump.sh` result now — *after* the stack is
   up (so the DBs/MinIO exist to restore into), *before* DAGs. `portal-restore.sh`
   is **destructive** (overwrites the fresh digitaltwins + HAPI DBs, SEEK DB +
   filestore, MinIO buckets, plugin registry, gateway plugin configs, JupyterHub
   volumes, Orthanc DICOM with the dump's). It does **not** touch Keycloak, Airflow
   runs/logs, or DAGs. Run from `~/digitaltwins-platform`, pointing at the dump dir:
   ```
   cd ~/digitaltwins-platform
   util/portal-restore.sh /mnt/install_src/migrate     # your stage-dump dir (default /tmp/dtwins-migrate)
   ```
   Then **re-mint the SEEK API token** — the restore replaced SEEK's users, so the
   token in `secrets.env` is stale (see README → *Transferring data* step 4). Uses
   the bundled `alpine`/`mc` images (already loaded), so it works airgapped.
6. **DAGs** (not in the bundle): sync from your DAG source, then **un-pause**. If
   you seeded in step 5, sync the DAGs that go with that data:
   ```
   util/sync-dags.sh <dag-source-box> <this-box>     # wait ~1 min for the dag-processor
   ```
7. **Verify** the platform (README §6): the stack is up, and the Airflow API token
   works (fresh Keycloak+Airflow creates the local `admin1` automatically). This
   mirrors `_get_api_token()` in `assays.py` — `os.getenv(key, default)`, so it uses
   the same fallbacks the code does and never KeyErrors on an unset var:
   ```
   docker compose exec -T digitaltwins-api python -c "import os,requests; ep=os.getenv('AIRFLOW_ENDPOINT','http://airflow-apiserver:8080/airflow'); u=os.getenv('AIRFLOW_USERNAME','admin'); p=os.getenv('AIRFLOW_PASSWORD','admin'); r=requests.post(ep+'/auth/token',json={'username':u,'password':p},timeout=30); print('HTTP',r.status_code)"
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
2. **On the node — install Docker + Ansible FROM THE BUNDLE** (compute-build seeded
   it in E.1). Must finish before E.3, or `docker compose` isn't there. Same as B.2:
   ```
   CS=/mnt/install_src/clean_src/digitaltwins-platform
   sudo "$CS/util/install-apt-debs.sh"
   tar xzf /mnt/install_src/ansible-packages.tar.gz -C ~ \
     && pip3 install --no-index --find-links ~/ansible-packages/ ansible --break-system-packages
   export PATH="$HOME/.local/bin:$PATH"     # ansible-playbook lands here — no logout needed
   ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step2.yml" \
     -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src"
   #   docker installed. If a later step hits docker "permission denied": newgrp docker (or log out/in).
   ```
3. **Wire up the worker.** First on the **portal** (the node `.env` reads the *running*
   portal's config, and the node needs the VLAN ports opened):
   ```
   # on the PORTAL:
   util/generate-compute-env.sh 10.2.0.195 ~/digitaltwins-platform/.env > /tmp/compute.env
   scp /tmp/compute.env ubuntu@10.2.0.14:~/compute.env
   util/ufw_for_remote_compute.sh 10.2.0.14     # 8002/8003/8005/8010/8011 (+ security group)
   ```
   Then on the **node** — the worker image and compute-worker files are already here
   (image in the bundle from compute-build; files in clean_src). Copy them into place,
   load the image, THEN bring it up:
   ```
   # on the NODE:
   CS=/mnt/install_src/clean_src/digitaltwins-platform
   mkdir -p ~/digitaltwins-compute/{dags,config,plugins,data,logs} && cd ~/digitaltwins-compute
   cp "$CS/services/airflow/compute-worker/docker-compose.yml" \
      "$CS/services/airflow/compute-worker/digitaltwins-worker.service" .
   mv ~/compute.env .env
   sed -i 's/^WORKER_QUEUES=.*/WORKER_QUEUES=remote/' .env
   docker load -i /mnt/install_src/airflow-worker.tar.gz     # image is already in the node's bundle
   docker compose up -d
   sudo cp digitaltwins-worker.service /etc/systemd/system/ \
     && sudo systemctl daemon-reload && sudo systemctl enable --now digitaltwins-worker
   ```
4. **DAGs to the node** (from the portal): `util/sync-compute-dags.sh 10.2.0.14`
5. **Confirm** the node joined the queue — on the portal:
   ```
   docker compose exec airflow-scheduler \
     celery --app airflow.providers.celery.executors.celery_executor.app inspect active_queues
   ```
   Expect `celery@<node> -> remote`.
6. **(Optional) operator SSH access to the node — only if you want those people able to
   SSH the compute node directly.** (Many deployments keep the node ops-only, reached
   via the portal, and skip this.) The node doesn't run step3, so it doesn't authorise
   `data/public_keys` (portal-only — see A.1). `compute-build` copies the pubkeys over,
   so authorise them with the standalone playbook:
   ```
   # on the NODE:
   ansible-playbook -i 'localhost,' -c local -e "ansible_user=$USER" \
     "$CS/util/authorise-keys.yaml"
   ```

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
2. **Watch the node's worker first** — on the **node**, tail the worker so you can see
   the message land on the `remote` queue and execution begin. Start this *before* you
   trigger:
   ```
   # on the NODE:
   cd ~/digitaltwins-compute && docker compose logs -f airflow-worker
   ```
3. **Drive load** — trigger the `cpu_burn_primes` DAG (unpaused on creation) from the
   portal (▶ in the Airflow UI, or `airflow dags trigger cpu_burn_primes`). Within a
   second or two the node's worker log should show it **receive and start** the task —
   lines like:
   ```
   Task ...execute_workload... received
   [...] Executing workload in Celery: ... queue='remote' ... dag_id='cpu_burn_primes' ...
   ... Burning N core(s) ...   /  heartbeats  /  Task ... succeeded in <n>s
   ```
   If the trigger fires but **nothing appears on the node**, the task isn't reaching it:
   re-check `compute_queue` = `remote` AND that `active_queues` lists `celery@<node> ->
   remote` (Phase E.5) — a mismatch leaves the task stuck `queued` on the portal, never
   dispatched. `htop` on the node is the ground-truth "is it actually running" check.
4. **See it in Grafana** (`https://<domain>/grafana` → Explore):
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
