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
| frozen image archive, `alpine.tar`, docker/compose/ansible bundles, `letsencrypt.tar` | `/etc/letsencrypt` **on the VM** — but `letsencrypt.tar` on the volume backs it up (restore to keep LE renewal), and the active cert is also in `data/*.pem` |
| any `stage-dump` you put here before dropping the VM | `~/.bashrc`, SSH host keys, installed packages |

**Implication:** before you drop a VM that holds data you care about, dump it
**onto the volume** (below) so it persists. And keep the TLS cert in `data/` — not
just in `/etc/letsencrypt`, which the rebuild wipes.

## Bundle contents & how to (re)build each piece

```
/mnt/install_src/                        # (actual contents on abi_portal, 2026-08-06)
├── clean_src/digitaltwins-platform/     # the code (+ 3 submodules); tracks remote-compute
├── data/
│   ├── env, secrets.env                 # host config + secrets (rendered → .env)
│   ├── <domain>.fullchain.pem/.privkey.pem   # per-domain certs (abi1, abi2, test.digitaltwins…)
│   ├── fullchain.pem / privkey.pem      # symlinks → the active domain (currently abi1)
│   ├── public_keys/*.pub                # operator SSH keys
│   ├── backups/                         # staged data dumps (stage-dump output)
│   ├── docker-compose.yml.compute, .env.compute   # remote compute-node config
│   └── old/                             # archived config
├── digitaltwins-images-all.tar.gz  6.3G # all platform images (amd64) — RE-FREEZE on any change
├── airflow-worker.tar.gz           752M # worker image, for remote nodes
├── alpine.tar                       4M  # alpine image (offline stage-dump/restore + init helpers)
├── compute/                        171M # remote compute-node deployment staging
├── docker-29.4.0.tgz                83M # docker static binaries (airgap step2)
├── docker-compose-linux-x86_64-v5.1.2  # compose plugin (airgap step2)
├── airgap/                         1.7G # apt-debs, pip-wheels, binaries, charts, observability, versions.txt
├── ansible-packages.tar.gz          57M # ansible wheels
└── letsencrypt.tar                  40K # /etc/letsencrypt backup (preserves LE renewal state)
```

| Piece | How to (re)build it | Refresh when |
|---|---|---|
| `clean_src/…` | `git clone --recursive -b remote-compute …` (or `git pull && git submodule update --init --recursive` in place) | any code/submodule change |
| `data/env`, `data/secrets.env` | copy `env.template` / `secrets.env.template`, fill in | config/secret changes |
| `data/*.pem` (+ symlinks) | issue the cert (LE DNS-01 / institutional — a VPN box isn't HTTP-01-reachable), drop in, symlink to `fullchain.pem`/`privkey.pem` | cert renewal (~90 days for LE) |
| `digitaltwins-images-all.tar.gz` | on a **connected** host: build + `up -d` the stack, then `util/freeze_images.sh` | **submodule bump, any image/dep change, or `PLATFORM_DOMAIN` change** (frontend bakes the Keycloak URL at build time) |
| `airflow-worker.tar.gz` | `docker save digitaltwins-platform-airflow-worker:latest \| gzip > airflow-worker.tar.gz` | worker image changes |
| `docker-29.4.0.tgz` | `wget https://download.docker.com/linux/static/stable/x86_64/docker-29.4.0.tgz` | docker version bump |
| `docker-compose-linux-x86_64-v5.1.2` | `wget https://github.com/docker/compose/releases/download/v5.1.2/docker-compose-linux-x86_64` | compose version bump |
| `alpine.tar` | `docker pull alpine && docker save alpine > alpine.tar` | rarely — offline helper image for `stage-dump`/`portal-restore` + `minio-logs-init` |
| `airgap/` | offline package set: `apt-debs/`, `pip-wheels/`, `binaries/`, observability `charts/`, `versions.txt` | rarely |
| `ansible-packages.tar.gz` | `pip3 download ansible -d ./ansible-packages/ && tar czf ansible-packages.tar.gz ansible-packages/` | rarely |
| `compute/` + `data/*.compute` | remote compute-node deployment files (staged for the node) | when compute-node config changes |
| `letsencrypt.tar` | `tar -C /etc -cf letsencrypt.tar letsencrypt` after issuing/renewing a cert | after a cert change — preserves LE renewal state across a VM rebuild |

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
