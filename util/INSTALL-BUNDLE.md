# The installation bundle (`/mnt/install_src`)

Everything a fresh VM needs to install the platform lives on a **persistent
volume** mounted at `/mnt/install_src` (device `/dev/vdb`). The volume is
*attached* to the VM, not part of its root disk — so it **survives dropping and
recreating the VM**. That's the whole point: rebuild the VM from scratch, re-mount
the volume, install from the bundle.

This doc is about (re)building and refreshing the **bundle** itself — what's in it,
how to produce each piece, and when to refresh. For the *install* steps that
consume it, see [`README.md`](README.md).

## What survives a VM rebuild — and what doesn't

| Survives (on `/mnt/install_src`) | Lost with the VM root disk |
|---|---|
| `clean_src/` (the code), `data/` (config, secrets, certs) | Docker + all **container volumes** → SEEK MySQL, Postgres, MinIO = **programmes/assays/datasets** |
| frozen image archive, docker/compose/ansible bundles | `/etc/letsencrypt` (LE certs + renewal state) |
| any `stage-dump` you put here before dropping the VM | `~/.bashrc`, SSH host keys, installed packages |

**Implication:** before you drop a VM that holds data you care about, dump it
**onto the volume** (below) so it persists. And keep the TLS cert in `data/` — not
just in `/etc/letsencrypt`, which the rebuild wipes.

## Bundle contents & how to (re)build each piece

```
/mnt/install_src/
├── clean_src/digitaltwins-platform/     # the code (+ 3 submodules)
├── data/
│   ├── env, secrets.env                 # host config + secrets (you fill in)
│   ├── public_keys/*.pub                # operator SSH keys
│   ├── <domain>.fullchain.pem/.privkey.pem   # per-domain TLS cert
│   └── fullchain.pem / privkey.pem      # symlinks → the chosen domain
├── digitaltwins-images-all.tar.gz       # all platform docker images (amd64)
├── airflow-worker.tar.gz                # just the worker image, for remote nodes
├── docker-<ver>.tgz                     # docker static binaries (airgap step2)
├── docker-compose-linux-x86_64-<ver>    # compose plugin binary (airgap step2)
├── airgap/apt-debs/*.deb                # pip/venv debs (to install ansible)
└── ansible-packages.tar.gz              # ansible wheels (to install ansible)
```

| Piece | How to (re)build it | Refresh when |
|---|---|---|
| `clean_src/…` | `git clone --recursive -b remote-compute …` (or `git pull && git submodule update --init --recursive` in place) | any code/submodule change |
| `data/env`, `data/secrets.env` | copy `env.template` / `secrets.env.template`, fill in | config/secret changes |
| `data/*.pem` (+ symlinks) | issue the cert (LE DNS-01 / institutional — a VPN box isn't HTTP-01-reachable), drop in, symlink to `fullchain.pem`/`privkey.pem` | cert renewal (~90 days for LE) |
| `digitaltwins-images-all.tar.gz` | on a **connected** host: build + `up -d` the stack, then `util/freeze_images.sh` | **submodule bump, any image/dep change, or `PLATFORM_DOMAIN` change** (frontend bakes the Keycloak URL at build time) |
| `airflow-worker.tar.gz` | `docker save digitaltwins-platform-airflow-worker:latest \| gzip > airflow-worker.tar.gz` | worker image changes |
| `docker-<ver>.tgz` | `wget https://download.docker.com/linux/static/stable/x86_64/docker-<ver>.tgz` | docker version bump |
| `docker-compose-linux-x86_64-<ver>` | `wget https://github.com/docker/compose/releases/download/<ver>/docker-compose-linux-x86_64` | compose version bump |
| `airgap/apt-debs/*.deb` | `apt-get download python3-pip python3-venv python3.12-venv` | rarely |
| `ansible-packages.tar.gz` | `pip3 download ansible -d ./ansible-packages/ && tar czf ansible-packages.tar.gz ansible-packages/` | rarely |

### Freeze gotcha (the one that bites)
`freeze_images.sh` saves **whatever images exist on the build host right now**, so
always: (1) `git submodule update --init --recursive` in `clean_src`, (2) build
+ `up -d` (so one-shot/init images exist for its `ps`-based capture), *then*
freeze. Verify the API image matches the pinned submodule before trusting it:
```bash
diff <(docker compose exec -T digitaltwins-api cat app/routers/assay.py) \
     services/api/digitaltwins-api/app/routers/assay.py && echo MATCH || echo STALE
```
A tarball whose mtime predates the last API build is stale — re-freeze.

## Preserving data across a VM drop

`stage-dump` writes to a directory you choose — put it **on the volume** so it
outlives the VM:
```bash
util/stage-dump.sh /mnt/install_src/migrate     # BEFORE dropping the VM
# … drop + recreate VM, install from the bundle …
util/portal-restore.sh /mnt/install_src/migrate # AFTER the stack is up
# then re-mint the SEEK API token (restore replaced SEEK's users) — see README
```
Covers `digitaltwins` + `hapi` DBs, SEEK (MySQL + filestore), MinIO buckets, plugin
registry, gateway plugin configs, JupyterHub per-user volumes, Orthanc DICOM. Does
**not** cover Keycloak (realm export/import), Airflow run history/logs, or DAGs.

## Installing from the bundle (fresh VM) — the short version
Full detail in [`README.md`](README.md); the shape is:
1. Re-attach the volume, mount it (`util/mount_src.sh`).
2. Docker: airgap → step2 playbook (static binaries); connected → Docker's apt repo.
3. Configure `data/env` + `data/secrets.env` (incl. `REMOTE_COMPUTE`,
   `AIRFLOW_VAR_COMPUTE_QUEUE`; `REDIS_PASSWORD` is **required** now).
4. Deploy: step3 playbook — airgap loads the frozen images; connected adds
   `-e load_frozen_images=false` to build from source. It renders `.env`, installs
   the TLS cert + the `digitaltwins-platform.service` boot unit, and brings the
   stack up.
5. **Sync the DAGs** (they're not in the bundle — see gaps) and un-pause them.

## Known gaps (deliberately not in the bundle)
- **Workflow DAGs.** `workflow_*` + `tool/` DAGs are managed outside the repo, so a
  fresh install has an empty `services/airflow/dags/`. Sync from a source box with
  `util/sync-dags.sh <src> <this-box>`, wait ~a minute for the dag-processor, then
  **un-pause**. Until then, launching an assay silently no-ops (API 200, no run).
- **Plugin images.** A registered portal plugin needs its docker image too —
  `docker save`/`load` it separately.

## Adding the remote compute node
1. **Portal:** `REMOTE_COMPUTE=true` in `data/env` → `gen-env` → recreate (this
   publishes the Redis broker on the VLAN — auth + S3 logging are already on in
   base). Open the firewall: `util/ufw_for_remote_compute.sh <node_ip>` + the cloud
   security group for `8002/8003/8005/8010/8011` (restricted to the node's IP).
2. **Node** (its own VM + volume): install docker, `util/generate-compute-env.sh
   <portal_vlan_ip> > data on the node`, load `airflow-worker.tar.gz`, deploy
   `services/airflow/compute-worker` with `WORKER_QUEUES=remote`, enable
   `digitaltwins-worker.service`.
3. Push DAGs to the node: `util/sync-compute-dags.sh <node>`.
4. **Route work to it:** set `AIRFLOW_VAR_COMPUTE_QUEUE=remote` on the portal — but
   only once the DAGs actually tag tasks `queue="remote"` and the node is serving
   that queue, or those tasks hang in `queued`.
