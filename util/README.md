# Airgap buildout — DigitalTWINS platform

Everything needed to bring the platform up on an **airgapped Ubuntu 24.04**
machine with no Internet access. You can run it on `http`/`localhost` or behind
`https` on a (real or `/etc/hosts`-faked) domain.

This directory (`util/`) replaces the old `buildout/dev` + `buildout/util` tree.
Config is now **template-driven**: you fill in two small input files
(`data/env` + `data/secrets.env`) and the playbook renders `.env` and the
Keycloak realm for you via `gen-env.sh` / `gen-realm.sh`. You no longer hand-edit
a `data/.env` or place a `data/digitaltwins-realm.json`.

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
# pip + venv from the bundled debs
sudo dpkg -i /mnt/install_src/airgap/apt-debs/*.deb

# ansible from the bundled wheels (as your normal user)
cd ~
tar xzf /mnt/install_src/ansible-packages.tar.gz
pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages
```

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
- brings the whole stack up (`docker compose up -d`).

`COMPOSE_FILE` is written into `~/.bashrc`, so **log out/in** (or
`export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml`) before running
`docker compose` by hand.

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
| `/airflow/`         | `airflow-apiserver:8080`  | **No** — baked FAB admin (`admin`/`admin`). Realm has an `airflow` client, not wired. | passthrough (`AIRFLOW__API__BASE_URL`) |
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

## Files in `/mnt/install_src` (reference)

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
| `airgap/apt-debs/*.deb` | pip/venv debs (`apt-get download python3-pip python3-venv python3.12-venv`). |
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
