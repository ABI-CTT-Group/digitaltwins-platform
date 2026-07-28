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

**Source both files** so the playbook tasks can read them:

```bash
source /mnt/install_src/data/secrets.env
source /mnt/install_src/data/env
```

## 5. Deploy the platform (playbook)

```bash
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/util/airgap_build_step3.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src"
```

This step (all automatic):
- rsyncs `clean_src` → `~/digitaltwins-platform` (you do **not** copy code yourself),
- renders `.env` (`gen-env.sh`) and the Keycloak realm (`gen-realm.sh`),
- installs the gateway TLS cert to `services/nginx/certs/server.{crt,key}`,
- loads the frozen docker images,
- initialises Airflow,
- bootstraps SEEK (admin user, features, API token → written back to
  `secrets.env`, then `.env` re-rendered),
- precompiles SEEK's assets for the `/seek` path (see note below),
- brings the whole stack up (`docker compose up -d`).

`COMPOSE_FILE` is written into `~/.bashrc`, so **log out/in** (or
`export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml`) before running
`docker compose` by hand.

## 6. Verify

Open a browser to (swap in your `PLATFORM_DOMAIN`; `http://localhost` for the
localhost/http build):

| URL | Service |
|---|---|
| `https://${PLATFORM_DOMAIN}/`         | Portal |
| `https://${PLATFORM_DOMAIN}/seek`     | SEEK (catalogue) |
| `https://${PLATFORM_DOMAIN}/jupyter`  | JupyterHub |
| `https://${PLATFORM_DOMAIN}/auth`     | Keycloak admin |
| `https://${PLATFORM_DOMAIN}/airflow`  | Airflow |

**Pre-canned realm users** (from the realm template — change/remove for
production): `admin` (password = your `KEYCLOAK_REALM_ADMIN_PASSWORD`), and the
plaintext test users `clinician`/`clinician`, `researcher`/`researcher`,
`test1`/`test1`, `test2`/`test2`.

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

## Files in `/mnt/install_src` (reference)

| File | Purpose |
|---|---|
| `clean_src/` | this repo + its 3 submodules (the deployment source). |
| `data/env`, `data/secrets.env` | your host config + secrets → rendered into `.env`. Never commit these. |
| `data/<domain>.fullchain.pem`/`.privkey.pem` | per-domain TLS cert/key; symlink the chosen one to `fullchain.pem`/`privkey.pem`. |
| `data/public_keys/*.pub` | operator SSH keys, authorised by step 5. |
| `digitaltwins-images-all.tar.gz` | all docker images. Rebuild on a connected host with: `docker compose ps -aq \| xargs docker inspect --format '{{.Config.Image}}' \| sort -u \| xargs docker save \| gzip > digitaltwins-images-all.tar.gz`. **Re-freeze if `PLATFORM_DOMAIN` changes** — the frontend bakes the Keycloak URL at build time. |
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
