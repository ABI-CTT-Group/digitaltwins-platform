# Airgap buildout — DigitalTWINS platform

Everything needed to bring the platform up on an **airgapped Ubuntu 24.04**
machine with no Internet access. You can run it on `http`/`localhost` or behind
`https` on a (real or `/etc/hosts`-faked) domain.

This directory (`util/`) replaces the old `buildout/dev` + `buildout/util` tree.
Config is now **template-driven**: you fill in two small input files
(`data/env` + `data/secrets.env`) and the playbook renders `.env` and the
Keycloak realm for you via `gen-env.sh` / `gen-realm.sh`. You no longer hand-edit
a `data/.env` or place a `data/digitaltwins-realm.json`.

## Contents

- [Getting the code into `clean_src`](#getting-the-code-into-clean_src)
- [Installing on a connected machine](#installing-on-a-connected-machine)
  - [Docker (replaces `airgap_build_step2.yml`)](#docker-replaces-airgap_build_step2yml)
  - [Ansible (only if you run the step-3 playbook)](#ansible-only-if-you-run-the-step-3-playbook)
- [Installing on a Mac or other arm64 host](#installing-on-a-mac-or-other-arm64-host)
  - [macOS (Apple Silicon)](#macos-apple-silicon)
  - [arm64 Linux (e.g. Graviton)](#arm64-linux-eg-graviton)
- [0. Mount the install source](#0-mount-the-install-source)
- [1. (Optional) Airgap the VM](#1-optional-airgap-the-vm)
- [2. Install Ansible from the local packages](#2-install-ansible-from-the-local-packages)
- [3. Install Docker (playbook)](#3-install-docker-playbook)
- [4. Configure the deployment](#4-configure-the-deployment)
- [5. Deploy the platform (playbook)](#5-deploy-the-platform-playbook)
- [6. Verify](#6-verify)
- [7. Gateway proxy routes (reference)](#7-gateway-proxy-routes-reference)
- [SEEK `/seek` asset precompile](#seek-seek-asset-precompile)
- [Rebuilding the frozen image archive (connected host)](#rebuilding-the-frozen-image-archive-connected-host)
- [Transferring data from one system to another](#transferring-data-from-one-system-to-another)
  - [Scripts](#scripts)
  - [What's covered](#whats-covered)
  - [Migrating Airflow runs & logs](#migrating-airflow-runs--logs-optional--not-done-by-default)
  - [Procedure](#procedure)
  - [Caveats](#caveats)
  - [How it works & gotchas](#how-it-works--gotchas-for-maintainers)
- [Working with the submodules (portal / api / seek)](#working-with-the-submodules-portal--api--seek)
- [Files in `/mnt/install_src` (reference)](#files-in-mntinstall_src-reference)
- [Observability (separate, optional)](#observability-separate-optional)
- [Notes / gotchas](#notes--gotchas)

The install source is assumed mounted at `/mnt/install_src`, laid out as:

```
/mnt/install_src/
├── clean_src/digitaltwins-platform/     # this repo checkout (submodules included)
├── data/
│   ├── env                              # non-secret host config (you fill in)
│   ├── secrets.env                      # all passwords/keys (you fill in)
│   ├── public_keys/*.pub                # operator SSH keys
│   ├── <domain>.fullchain.pem / .privkey.pem   # per-domain certs
│   └── fullchain.pem -> … / privkey.pem -> …    # symlink to the chosen domain
├── digitaltwins-images-all.tar.gz       # frozen docker images
├── docker-29.4.0.tgz                    # docker static binaries
├── docker-compose-linux-x86_64-v5.1.2   # compose plugin binary
├── airgap/apt-debs/*.deb                # pip/venv debs (to install ansible)
└── ansible-packages.tar.gz              # ansible wheels (to install ansible)
```

### Getting the code into `clean_src`

Populate `clean_src/digitaltwins-platform/` with a **recursive** clone. The repos
are public, so this needs no auth over HTTPS (the box's only GitHub block is
SSH); `--recursive` pulls the three submodules (portal / api / seek) at their
pinned commits:

```bash
cd /mnt/install_src/clean_src
git clone --recursive -b remote-compute \
  https://github.com/ABI-CTT-Group/digitaltwins-platform.git
```

> **Branch note:** this currently tracks the `remote-compute` branch — it covers
> both single-box ("worker in docker") and remote-compute deploys, the systemd
> boot units, and `COMPOSE_FILE`/queue config rendered into `.env`. Slated to
> merge into `main`; once it does, drop `-b remote-compute` and clone `main`.
>
> After any `git pull` in `clean_src`, re-run `git submodule update --init
> --recursive` — a pull moves the submodule pointers but does **not** check out
> their new commits.

---

## Installing on a connected machine

The steps below assume an **airgapped** host, so Docker and Ansible come from the
bundled tarball/wheels on `/mnt/install_src`. On a machine **with Internet
access** you don't need that bundle — install them from their normal repos
instead. This **replaces step 2** (and you can skip the airgap-only steps 0 and
1); the frozen image archive is also unnecessary — run **step 5 with
`-e load_frozen_images=false`** so it builds/pulls images from source.

### Docker (replaces `airgap_build_step2.yml`)

Install Docker Engine + the Compose plugin from Docker's official apt repo. One
install gives you `docker`, `docker compose`, containerd, and an enabled systemd
service — everything the step-2 playbook set up by hand from the static tarball:

```bash
# Docker's official apt repo (Ubuntu)
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# put your user in the docker group, then log out / back in
sudo usermod -aG docker "$USER"
```

(Quick alternative: `curl -fsSL https://get.docker.com | sudo sh`, then the same
`usermod`.) The `docker-compose-plugin` package provides the `docker compose`
subcommand (v2) the compose files use — not the old standalone `docker-compose`.

### Ansible (only if you run the step-3 playbook)

Ansible just executes the playbooks; install it from apt instead of the bundled
wheels:

```bash
sudo apt install -y ansible
```

Unlike the airgap `pip … --break-system-packages` install (which lands in
`~/.local/bin` and needs a re-login for PATH), the apt package puts
`ansible-playbook` on your PATH immediately. If you'd rather deploy **without**
Ansible, follow [`../docs/deployment.md`](../docs/deployment.md) instead (manual
`gen-env.sh` → `docker compose build` → `up`).

Then continue at **step 4** (configure the deployment) and run **step 5** with
`-e load_frozen_images=false`.

---

## Installing on a Mac or other arm64 host

A developer/test setup on **Apple Silicon** or an **arm64 Linux** box (e.g. AWS
Graviton). This is *not* a production target — the real boxes are amd64 — but
it's useful for validating the stack off the amd64 servers.

Two things are always true on arm64:

- **Always build/pull from source — never load the frozen archive.** The bundled
  `digitaltwins-images-all.tar.gz` is amd64, so run **step 5 with
  `-e load_frozen_images=false`** (or follow [`../docs/deployment.md`](../docs/deployment.md)).
- **The amd64-only images run under emulation.** Most images are multi-arch and
  run native arm64, but `ldh` (SEEK), `fairdom/seek-solr`, and
  `orthanc-auth-service` publish **amd64 only**. The compose files already pin
  them with `platform: linux/amd64`, so they run — but *emulated*, which is
  CPU-heavy and slow. Give the machine plenty of headroom (≈8 CPU / 16 GB). The
  portal backend itself builds **natively** on arm64 (the Docker apt repo in its
  Dockerfile uses `$(dpkg --print-architecture)`).

Emulation needs a translation layer — the one setup difference between the two
hosts:

### macOS (Apple Silicon)

Use a Docker engine with **Rosetta** enabled for amd64 emulation (much faster
than QEMU) — either **Colima** (CLI, no GUI) or **Docker Desktop**.

**Colima.** Install the Docker CLI, the Compose plugin, and Colima via Homebrew:

```bash
brew install colima docker docker-compose
```

Then start the VM with Rosetta (`--vz-rosetta` turns on Rosetta 2 inside the VM;
`vz` is the default VM type):

```bash
colima start --cpu 8 --memory 16 --vz-rosetta
```

Homebrew installs the Compose plugin, but the Docker CLI only finds it if it's in
your CLI-plugins dir — otherwise `docker compose …` errors with "is not a docker
command". Link it once:

```bash
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
```

(Check with `docker compose version`.)

**Docker Desktop.** Alternatively, enable *Settings → General → "Use Rosetta for
x86/amd64 emulation"* and give it ≥ 8 CPU / 16 GB under *Settings → Resources*.
Docker Desktop wires up the `docker compose` plugin itself, so the symlink step
above isn't needed.

### arm64 Linux (e.g. Graviton)

Install Docker the normal connected way (see **Installing on a connected
machine** above). Linux has no Rosetta, so register QEMU/binfmt once so the
kernel can run amd64 binaries:

```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

Without this the amd64-only images fail with `exec format error` even though
their `platform:` pins are correct. It resets on reboot — re-run it, or install
the `qemu-user-static` package to persist it.

Then continue at **step 4** (configure) and run **step 5** with
`-e load_frozen_images=false`.

---

## 0. Mount the install source

The `/dev/vdb` volume persists across VM rebuilds, but `/etc/fstab` on the root
disk does not — so after a fresh rebuild you must mount it manually **once**
(the mount helper lives on the volume, so it can't mount itself the first time):

```bash
sudo mkdir -p /mnt/install_src
sudo mount /dev/vdb /mnt/install_src
```

Then, to add the fstab entry (and re-mount idempotently on later runs):

```bash
sudo /mnt/install_src/clean_src/digitaltwins-platform/util/mount_src.sh
```

> Override the device/mount/owner with `SRC_DEV=`, `MOUNT_POINT=`, `OWNER=` if
> you're using a USB drive instead of `/dev/vdb`.

## 1. (Optional) Airgap the VM

To simulate/enforce the airgap with UFW (allows only 22/80/443 in, denies
egress):

```bash
sudo /mnt/install_src/clean_src/digitaltwins-platform/util/airgap.sh
```

`util/unairgap.sh` restores outgoing access if you need to pull something later.

## 2. Install Ansible from the local packages

No Internet, so install pip and Ansible from the bundle on disk:

```bash
# pip + venv (+ certbot, unzip, …) from the bundled debs — installed THROUGH apt
# against the local repo so deps resolve and CONFIGURE cleanly (no half-configured
# 'iU' packages). Do NOT `dpkg -i *.deb` — that can't resolve deps and is what
# left certbot stuck without python3-josepy/python3-acme.
CS=/mnt/install_src/clean_src/digitaltwins-platform
sudo "$CS/util/install-apt-debs.sh"

# ansible from the bundled wheels (as your normal user)
cd ~
tar xzf /mnt/install_src/ansible-packages.tar.gz
pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages
```

> The deb set is a real local apt repo (a `Packages` index + the full dependency
> closure). If it's ever incomplete or you add a package, rebuild it on a
> **connected** noble host with `util/build-apt-debs.sh` (see the bundle table).

**Log out and back in** so `~/.local/bin` (where `ansible-playbook` lands) is on
your `PATH`.

## 3. Install Docker (playbook)

```bash
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/util/airgap_build_step2.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src"
```

**Log out and back in** so your shell picks up membership of the `docker` group.

## 4. Configure the deployment

Fill in the two input files under `/mnt/install_src/data/` (copy the repo's
`env.template` / `secrets.env.template` if they don't exist yet):

- **`data/env`** — non-secret host config. In particular the four lines at the
  bottom select `http`/`localhost` vs `https`/domain:
  ```bash
  export PLATFORM_PROTOCOL=https
  export PLATFORM_DOMAIN=abi1.drai.auckland.ac.nz
  export KC_HOSTNAME_STRICT=true
  export KC_HOSTNAME_STRICT_HTTPS=true
  ```
  It also carries the compute knobs:
  ```bash
  REMOTE_COMPUTE=false              # true → also merge remote-compute.override.yml (publish Redis on the VLAN for a remote worker)
  AIRFLOW_VAR_COMPUTE_QUEUE=default # 'remote' routes workflow DAGs to a remote compute node
  ```
- **`data/secrets.env`** — every password/key (this is where "set up all your
  passwords" now happens). Generate strong values with `openssl rand -hex 32`.

**TLS cert (https only).** Symlink one of the bundled domain certs to the generic
names the playbook reads — it must match `PLATFORM_DOMAIN`:

```bash
cd /mnt/install_src/data
ln -sf abi1.drai.auckland.ac.nz.fullchain.pem fullchain.pem
ln -sf abi1.drai.auckland.ac.nz.privkey.pem  privkey.pem
```

(Or drop in your own `fullchain.pem` / `privkey.pem`.) If you're testing a domain
whose DNS doesn't point here, add it to `/etc/hosts` (e.g. `0.0.0.0 abi1.drai.auckland.ac.nz`).

**Source both files** so the playbook tasks can read them. Use `set -a` so the
bare `KEY=value` lines in `secrets.env` are **exported** — a plain `source`
leaves them as shell variables the `ansible-playbook` process can't see:

```bash
set -a
source /mnt/install_src/data/secrets.env
source /mnt/install_src/data/env
set +a
```

## 5. Deploy the platform (playbook)

```bash
# use this if airgapped
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/util/airgap_build_step3.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src"

# Use this if rebuilding in a connected environment
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/util/airgap_build_step3.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src" \
  -e load_frozen_images=false
```

This step (all automatic):
- rsyncs `clean_src` → `~/digitaltwins-platform` (you do **not** copy code yourself),
- renders `.env` (`gen-env.sh`) and the Keycloak realm (`gen-realm.sh`),
- installs the gateway TLS cert to `services/nginx/certs/server.{crt,key}`,
- loads the frozen docker images (**airgap default**) — or, on a connected host,
  add `-e load_frozen_images=false` to **build/pull from source instead** (use
  this to produce a fresh archive, then re-freeze — see below),
- initialises Airflow,
- bootstraps SEEK (admin user, features, API token → written back to
  `secrets.env`, then `.env` re-rendered),
- precompiles SEEK's assets for the `/seek` path (see note below),
- brings the whole stack up (`docker compose up -d`),
- installs + enables the `digitaltwins-platform.service` systemd unit, so a reboot
  reconverges the stack automatically (mirrors the compute node's worker unit).

`COMPOSE_FILE` is rendered into `.env` (by `gen-env.sh`, from `REMOTE_COMPUTE`),
so `docker compose` run from `~/digitaltwins-platform` picks up the right file set
automatically — no `~/.bashrc` entry and no re-login needed. **Do not export
`COMPOSE_FILE` in your shell:** a shell value overrides the one in `.env` and will
silently pin you to base-only (the remote-compute override then never applies). If
an old deploy left an `export COMPOSE_FILE=…` line in `~/.bashrc`, delete it.

## 6. Verify

Open a browser to `https://${PLATFORM_DOMAIN}<path>` (use `http://localhost` for
the localhost/http build). Every route below is served by the edge **gateway**
(`services/nginx`); see the routing table in the next section.

Quick smoke test: `/` (portal), `/seek`, `/jupyter`, `/auth`, `/airflow`.

**Pre-canned realm users** (from the realm template — change/remove for
production): `admin` (password = your `KEYCLOAK_REALM_ADMIN_PASSWORD`), and the
plaintext test users `clinician`/`clinician`, `researcher`/`researcher`,
`test1`/`test1`, `test2`/`test2`.

## 7. Gateway proxy routes (reference)

The edge gateway (`services/nginx`) owns all of `80`/`443` and proxies these
paths. Every `proxy_pass` goes through a `set $var` + the docker `resolver`
(`http-level.conf`), so a service that is down 502s **only its own route**
instead of stopping nginx from starting. Routes are defined in
`services/nginx/snippets/platform-routes.conf`; the `/` fallback in
`portal-fallback.conf`.

| Path | Upstream (service:port) | Keycloak auth | Prefix handling |
|---|---|:---:|---|
| `/`                 | `portal-frontend`         | **Yes** — OIDC login (frontend `VITE_KEYCLOAK_*`; backend validates the `api` client). Also carries `/api/`, `/tools/`, `/plugin/<expose>/`. | passthrough |
| `/seek/`            | `seek:3000`               | **No** — local admin login (`SEEK_ADMIN_PASSWORD`). `omniauth_enabled` is on but no provider is wired; the realm ships a `seek` client for future SSO. | passthrough (`RAILS_RELATIVE_URL_ROOT=/seek`) |
| `/airflow/`         | `airflow-apiserver:8080`  | **Yes** — OIDC (`airflow` client in `digitaltwins` realm). | passthrough (`AIRFLOW__API__BASE_URL`) |
| `/jupyter/`         | `jupyterhub:8000`         | **Yes** — OIDC (GenericOAuthenticator → Keycloak). | passthrough (`c.JupyterHub.base_url=/jupyter/`) |
| `/auth/`            | `keycloak:8080`           | *is Keycloak* | passthrough (`KC_HTTP_RELATIVE_PATH=/auth`) |
| `/fhir/`            | `hapi-fhir:8080`          | **No** — open REST API. | passthrough (native `/fhir`) |
| `/minio/`           | `minio:9001`              | **No** — root creds (`minioadmin`). | rewrite (strips `/minio/`) |
| `/pgadmin/`         | `pgadmin:80`              | **No** — own login (`PGADMIN_DEFAULT_*`). | rewrite (strips `/pgadmin/`) |
| `/orthanc-1/`       | `orthanc-1:8042`          | **Yes** — `ENABLE_KEYCLOAK=true` (orthanc auth plugin). | rewrite (strips `/orthanc-1/`) |
| `/orthanc-2/`       | `orthanc-2:8042`          | **Yes** — `ENABLE_KEYCLOAK=true`. | rewrite (strips `/orthanc-2/`) |
| `/digitaltwins-api/`| `digitaltwins-api:8000`   | **Yes** — validates Keycloak tokens (resource server, `api` client). | rewrite (strips `/digitaltwins-api/`) |

- **passthrough** routes forward the URI unchanged; the app is *told* it lives
  under the prefix by the setting shown. A 404/redirect-to-`/` there is an app
  config problem, not nginx.
- **rewrite** routes strip the prefix because the app serves at root (needed
  only because the `set $var` form disables nginx's automatic prefix strip).
- Edit a route and reload with no rebuild/restart:
  `docker exec ${PROJECT_NAME}-gateway nginx -t && docker exec ${PROJECT_NAME}-gateway nginx -s reload`.

---

## SEEK `/seek` asset precompile

The frozen LDH image bakes its assets **without** `RAILS_RELATIVE_URL_ROOT`, so
under `/seek` they 404 until recompiled with the root set (it's in SEEK's compose
env). **Step 5 does this automatically** after the final `up`, then restarts
`seek workers portal-frontend`. It writes to the container's writable layer (not
a volume), so redo it whenever you:

- first deploy on a new VM (done by the playbook),
- pull a new LDH image version,
- change `RAILS_RELATIVE_URL_ROOT`.

Manual form, if ever needed:

```bash
docker compose exec seek bundle exec rake assets:precompile
docker compose exec seek bundle exec rake tmp:clear
docker compose restart seek workers portal-frontend
```

## Rebuilding the frozen image archive (connected host)

When the archive is stale (or missing), build fresh on an Internet-connected box
and re-freeze:

```bash
# 1. Deploy, building from source instead of loading the stale archive:
set -a; source /mnt/install_src/data/secrets.env; source /mnt/install_src/data/env; set +a
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/util/airgap_build_step3.yml \
  -e "ansible_user=$USER" -e "install_src_dir=/mnt/install_src" \
  -e load_frozen_images=false

# 2. Verify the app (see section 6), then re-freeze the running system's images:
util/freeze_images.sh          # writes /mnt/install_src/digitaltwins-images-all.tar.gz
```

`freeze_images.sh` saves the union of the compose config's declared images and
every container's actual image (so exited one-shots like `minio-init` and the
`singleuser` build are included). Copy the resulting `.tar.gz` to the airgapped
machine's install source; subsequent runs with the default
`load_frozen_images=true` will load it.

## Transferring data from one system to another

Copies the live data from one instance (e.g. a staging box) into another (e.g.
the portal). Uses **logical dumps + object mirrors**, not raw volume copies, so
it survives the two layouts differing — which they do:

- **Keycloak** may be embedded **H2** on one box and **Postgres** on the other.
  A DB copy is impossible across engines, so Keycloak is **not** handled here —
  migrate realms/users via a Keycloak realm export/import instead.
- **HAPI FHIR** may have its **own Postgres** on one box and live in the
  **shared Postgres** on the other. A logical `pg_dump` restores fine across
  that (and across major versions, e.g. 13 → 16).

### Scripts

| Script | Runs on | What it does |
|---|---|---|
| `util/stage-dump.sh [OUT]` | **source** | READ-ONLY dump → `OUT` (default `/tmp/dtwins-migrate`). Nothing on the source is stopped or modified. |
| `util/portal-restore.sh [IN]` | **target** | **Destructive** restore from `IN`. Prompts for confirmation. |
| `util/sync-dags.sh <SRC> <DST> [--mirror]` | **control machine** | Copies Airflow DAGs SRC→DST over ssh. Separate from the above (DAGs are managed outside the repo). |

Both dump/restore read credentials from the containers' own env, so the two
boxes need not share passwords. Container/volume names default to the
`digitaltwins-platform` project; override with the `PROJECT` / `*_C` / `*_VOLS`
env vars if yours differ.

### What's covered

`digitaltwins` DB · HAPI FHIR DB · SEEK (MySQL + filestore) · MinIO buckets ·
portal **plugin registry** (`plugin_registry.db`) · gateway **plugin route
configs** (`nginx_plugin_configs`) · **JupyterHub per-user volumes**
(`jupyterhub_user_*`) · Orthanc DICOM volumes.

> **Plugin images are still not covered** — a plugin (e.g. `surfaceannotator`)
> also needs its docker **image** present on the target. `docker save` it from
> the source and `docker load` on the target separately (the data tooling moves
> data, not images).

**Not** covered: Keycloak (see above), Airflow **run history + task logs** (not by
default — see [Migrating Airflow runs & logs](#migrating-airflow-runs--logs-optional--not-done-by-default) below), and Airflow DAGs (use `sync-dags.sh`).

### Migrating Airflow runs & logs (optional — not done by default)

The default procedure deliberately leaves Airflow's **run history** and **task
logs** behind — you migrate the DAG *definitions* with `sync-dags.sh` and
**re-trigger** on the fresh target. If you specifically need the history/logs too,
here's what each takes. They are **separate problems**, and the Fernet key only
touches one of them.

**Logs — easy, no key involved.** Airflow task logs are stored **unencrypted** in
the MinIO `airflow-logs` bucket. `stage-dump.sh` skips it on purpose:

```bash
[ "$b" = "airflow-logs" ] && { echo "  skip $b"; continue; }
```

Delete that line (or gate it behind an opt-in flag) and the bucket mirrors like
any other — `portal-restore.sh` needs no change, it restores whatever bucket dirs
are present. Note this bucket can be large.

**Runs — harder; this is where the Fernet key matters.** Run history lives in the
**`airflow` Postgres database**, which the tooling does **not** dump (it dumps only
`digitaltwins` + `hapi`). `airflow` shares the same `postgres:16` container, so
it's a second logical dump/restore against `${PROJECT}-database-1`:

```bash
# SOURCE (read-only):
docker exec ${PROJECT}-database-1 sh -c \
  'pg_dump -U "$POSTGRES_USER" --clean --if-exists airflow' > /tmp/airflow.sql
# TARGET (destructive — replaces the target's airflow metadata):
docker exec -i ${PROJECT}-database-1 sh -c 'psql -U "$POSTGRES_USER" airflow' < /tmp/airflow.sql
# then restart the airflow services
```

Three prerequisites for that to be *usable*:

1. **Same Airflow version** on both sides (metadata schema / alembic). Both boxes
   are `apache/airflow:3.0.6` today — but re-check before any version bump.
2. **Same `AIRFLOW__CORE__FERNET_KEY`.** The run history itself (`dag_run`,
   `task_instance`, XComs) is stored **plaintext** and migrates regardless. What
   Fernet encrypts is **Connections** (passwords/extras) and **Variables** — so the
   target needs the *same key the source's DB was encrypted with*, or those rows
   won't decrypt and migrated DAGs can't authenticate to anything.
3. Expect to prune scheduler/executor/worker state that's meaningless on the new
   box.

**The Fernet catch on this platform.** Until recently both boxes ran with an
**empty** Fernet key (a bug — the compose hardcoded `''` instead of reading
`AIRFLOW__CORE__FERNET_KEY` from `secrets.env`; now fixed). A fresh target given a
*new* real key will **not** decrypt connections/variables that an old source
encrypted under the empty key. So a runs-migration and the key-fix pull against
each other: if you must preserve encrypted connections from an old instance, set
the target's `AIRFLOW__CORE__FERNET_KEY` to *that instance's* key, and re-enter any
connections/variables that were created under the empty key.

**Recommendation.** For most migrations: bring the **logs** if you want them
(cheap), and **re-run the DAGs** on the fresh target rather than transplant the
`airflow` DB — that sidesteps the version and Fernet knots entirely. Reach for the
DB transplant only when the historical run *records* themselves are the deliverable.

### Procedure

```bash
# 1. On the SOURCE (read-only; writes to /tmp):
ssh <source>
util/stage-dump.sh                      # -> /tmp/dtwins-migrate on the source

# 2. Move the dump to the TARGET (relay through your workstation if the boxes
#    can't reach each other):
rsync -az -e ssh <source>:/tmp/dtwins-migrate/ ./dtwins-migrate/
rsync -az -e ssh ./dtwins-migrate/ <target>:/tmp/dtwins-migrate/

# 3. On the TARGET (destructive; asks for confirmation):
ssh <target>
cd ~/digitaltwins-platform
util/portal-restore.sh                  # <- /tmp/dtwins-migrate on the target

# 4. Re-mint the SEEK API token (restore replaced SEEK's users, so the
#    buildout's token is stale). On the target:
SECRETS_FILE=/mnt/install_src/data/secrets.env util/generate-token.sh admin
util/gen-env.sh -e /mnt/install_src/data/env -s /mnt/install_src/data/secrets.env
docker compose up -d digitaltwins-api

# 5. DAGs — separate, run from a machine that can ssh to both:
util/sync-dags.sh <source> <target>
```

### Caveats

- **Overwrite:** `portal-restore.sh` replaces the target's `digitaltwins`,
  `hapi`, `seek`, MinIO, plugin registry and Orthanc data. Intended for a fresh
  target; don't run it over data you want to keep.
- **Orthanc** restore briefly **stops** the target's `orthanc-1/2` containers to
  swap their volumes.
- **Plugin images:** the plugin *registry* comes across, but a registered
  plugin only runs if its image/source is also present on the target. If a
  migrated plugin fails to start, its build context/image still needs providing.
- **SEEK API token** must be re-minted (step 4) or the portal's API can't talk
  to SEEK after the restore.

### How it works & gotchas (for maintainers)

Read this before changing `stage-dump.sh` / `portal-restore.sh` — most of it is
non-obvious and was learned the hard way.

**Design principles**

- **Logical dumps + object mirrors, never raw volume copies.** The source and
  target layouts genuinely differ — Keycloak may be embedded **H2** on one box
  and **Postgres** on the other; HAPI may have its **own Postgres** on one and
  live in the **shared Postgres** on the other. A `pg_dump`/`mysqldump`/`mc
  mirror` survives that (and crosses major versions, e.g. pg 13→16); a volume
  copy would not. (This is also why Keycloak is *not* migrated here — do a realm
  export/import instead.)
- **Credentials are read from each container's own env** (`docker exec … printenv`
  / `sh -c '… "$VAR"'`), so the two boxes need **not** share passwords and the
  scripts need no `.env`.
- **Everything is keyed off the compose project name.** Container and volume
  names default to the `digitaltwins-platform` project (`${PROJECT}-<svc>-1`,
  `${PROJECT}_<vol>`). If a box uses a different project name, override via the
  `PROJECT` / `*_C` / `*_VOLS` / `*_VOL` env vars — otherwise steps silently find
  nothing. **Restore assumes the target project name matches** what the dump
  captured (volumes are recreated under their original names); that's fine while
  both boxes are `digitaltwins-platform`, but revisit it if that ever changes.

**Per-step gotchas**

- **MinIO enumeration must happen host-side.** The `minio/mc` image is minimal —
  no `awk`/`ls`/`sed`. Enumerate buckets on the host side of the pipe and run
  `mc` per bucket inside the container. `mc` reaches MinIO by its **network alias**
  (`http://minio:9000`) on the compose network, so MinIO must be **running**.
- **SEEK MySQL needs `unset MYSQL_HOST`.** The SEEK db container carries
  `MYSQL_HOST=db` (via `env_file`), so a bare `mysql`/`mysqldump` connects over
  **TCP** as `root@<network>` and is denied. Unsetting it forces the local socket.
- **Root-owned output.** The `mc` / `alpine` / `docker cp` helpers run as **root**,
  so parts of `OUT` end up root-owned. `stage-dump.sh` `chown`s the whole tree
  back to the invoking user at the end — **keep that step**, or a later non-root
  `tar`/`rsync` will *silently skip* the root-owned files (that was the original
  "partial dump" bug).
- **Orthanc / plugin-config / jupyter volumes are tarred via a throwaway `alpine`**
  (`-v vol:/v:ro … tar`). Restore **stops** the Orthanc containers to swap their
  volumes; the plugin-config restore reloads the gateway; jupyter user volumes are
  recreated by their exact name so the hub mounts them on the user's next login.

**Deliberately fail-loud vs skip**

- MinIO mirror failures **abort** the dump (`set -e`, no `|| true`) — a partial
  object set must never pass silently.
- A **missing volume/container** is a **skip with a message** (Orthanc, plugin
  configs, HAPI-on-shared-pg). That's intentional for legitimately-absent things,
  but it's also how a wrong `PROJECT`/name yields a quiet partial — so when a box
  differs, set the overrides rather than trusting the skips.

**Not covered (by design)** — Keycloak (realm export/import), Airflow metadata
(runtime state), Airflow DAGs (`sync-dags.sh`), the JupyterHub hub DB
(`jupyterhub_data` — user *data* travels in the per-user volumes; the hub
re-creates its user record on next Keycloak login), and **docker images** (plugin
images must be `docker save`/`load`ed separately).

## Working with the submodules (portal / api / seek)

`services/portal/DigitalTWINS-Portal`, `services/api/digitaltwins-api`, and
`services/seek/ldh-deployment` are **git submodules**: this platform repo does
**not** contain their code — it stores a *bookmark* (an exact commit hash) saying
"use this submodule at this commit". Each submodule is its own repo with its own
`main` and PRs. So changing submodule code is always **two repos, two commits**:

```bash
# 1. Change the code IN THE SUBMODULE'S OWN REPO (branch -> commit -> push -> PR)
cd services/portal/DigitalTWINS-Portal
git checkout -b feat/my-change
# ...edit...
git commit -am "..."
git push -u origin feat/my-change
gh pr create --base main               # open the PR in the submodule's repo

# 2. Point the PLATFORM's bookmark at that commit (pin) and commit it here
cd -                                   # back to the platform repo root
git add services/portal/DigitalTWINS-Portal
git commit -m "chore(portal): pin submodule to <commit>"
```

**Re-pin after the submodule PR merges.** Pinning to a feature-branch commit is
fine short-term, but once the submodule PR lands on its `main` (especially with a
squash-merge, which makes a *new* hash), bump the pointer again:

```bash
cd services/portal/DigitalTWINS-Portal && git fetch origin && git checkout origin/main
cd - && git add services/portal/DigitalTWINS-Portal && git commit -m "chore(portal): re-pin to main"
```

> The pin only works if the commit is **pushed** to the submodule's remote — a
> local-only commit would be an unfetchable bookmark for anyone else.

## Files in `/mnt/install_src` (reference)

See [`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md) for how to (re)build and refresh each
of these, what survives a VM rebuild, and how to dump data onto the volume first.

| File | Purpose |
|---|---|
| `clean_src/` | this repo + its 3 submodules (the deployment source). |
| `data/env`, `data/secrets.env` | your host config + secrets → rendered into `.env`. Never commit these. |
| `data/<domain>.fullchain.pem`/`.privkey.pem` | per-domain TLS cert/key; symlink the chosen one to `fullchain.pem`/`privkey.pem`. |
| `data/public_keys/*.pub` | operator SSH keys, authorised by step 5. |
| `digitaltwins-images-all.tar.gz` | all docker images. Recreate with **`util/freeze_images.sh`** on a connected host once the stack is built and up. **Re-freeze if `PLATFORM_DOMAIN` changes** — the frontend bakes the Keycloak URL at build time. |
| `airflow-worker.tar.gz` | just the airflow-worker image, for remote compute nodes. |
| `docker-29.4.0.tgz` | docker static binaries (`wget https://download.docker.com/linux/static/stable/x86_64/docker-29.4.0.tgz`). |
| `docker-compose-linux-x86_64-v5.1.2` | compose plugin (`wget https://github.com/docker/compose/releases/download/v5.1.2/docker-compose-linux-x86_64`). |
| `airgap/apt-debs/` | local apt repo: pip/venv/certbot/unzip debs **+ their full dependency closure** + a `Packages` index + `INSTALL.list`. (Re)build on a **connected noble host** with `util/build-apt-debs.sh`; install on the airgapped target with `util/install-apt-debs.sh`. Don't hand-run `apt-get download <names>` — it skips deps and reintroduces the `iU` breakage. |
| `ansible-packages.tar.gz` | ansible wheels (`pip3 download ansible -d ./ansible-packages/ && tar czf ansible-packages.tar.gz ansible-packages/`). |

## Observability (separate, optional)

Unchanged from the original bundle — installs Grafana/Loki/Mimir integrated with
Keycloak. Set the two vars, then run the observability playbook:

```bash
export GRAFANA_ADMIN_PASSWORD=yourpassword
export GRAFANA_OAUTH_SECRET=yoursecret

ansible-playbook -i 'localhost,' -c local \
  -e "ansible_user=$(whoami)" \
  -e "install_src_dir=/mnt/install_src/airgap" \
  /mnt/install_src/install_observability_airgap.yaml
```

Then `https://${PLATFORM_DOMAIN}/grafana` should work.

---

### Notes / gotchas

- **Run on the box, `-c local`.** Step 5's code sync is a box-local rsync
  (`/mnt/install_src` → `~`), so it must run where the source lives. Running the
  playbooks from a laptop against the VM over SSH would look for the source on the
  laptop.
- **Steps 0 and 1 are shell scripts; steps 2 and 3 are Ansible playbooks.** (A
  `airgap_build_step1.yml` UFW playbook can be added if you want parity.)
- **Stale service worker after a rebuild.** A browser that used a previous deploy
  on the same domain can cache a PWA service worker and loop on
  `expired_code` at login. Fix: clear site data / use incognito.
- **A fresh box has no workflow DAGs.** The `workflow_*` DAGs are managed outside
  the repo (not in the bundle), so a new install comes up with an empty
  `services/airflow/dags/`. Sync them (`util/sync-dags.sh <src> <this-box>`), give
  the dag-processor ~a minute to scan, then **un-pause** them (new DAGs boot
  paused). Until a DAG exists and is un-paused, launching its assay silently
  no-ops — the API returns 200 but no run ever appears in Airflow.
- **`REDIS_PASSWORD` is required.** The base compose now always password-protects
  Redis, so `secrets.env` must set `REDIS_PASSWORD` (an unset/empty value fails
  fast at `up`). Broker URL and Redis both read it, so they always match — the
  remote-compute override only adds the VLAN port publish on top.
