# DigitalTWINS Platform Installation Guide

This guide covers installation of the DigitalTWINS platform on an airgapped Ubuntu 24.04 machine. The platform can be run either:
- Over **HTTPS** behind a real or locally-resolved domain name
- Over **HTTP** on `localhost` (local development only — browser security restrictions prevent Keycloak from working over HTTP on non-localhost domains)

---

## Prerequisites

### SSL Certificates (HTTPS deployments only)

You will need `fullchain.pem` and `privkey.pem` for your domain, placed in `/mnt/install_src/data/`.

Pre-signed certificates are available for these domains:
- `test.digitaltwins.auckland.ac.nz`
- `abi1.drai.auckland.ac.nz`
- `abi2.drai.auckland.ac.nz`

To use one of these, create symlinks:
```bash
cd /mnt/install_src/data
ln -s abi2.drai.auckland.ac.nz.fullchain.pem fullchain.pem
ln -s abi2.drai.auckland.ac.nz.privkey.pem privkey.pem
```

If the domain doesn't resolve to your VM in DNS, add it to your local `/etc/hosts`:
```
<your-vm-ip>  abi2.drai.auckland.ac.nz
```

---

## Step 1 — Mount the Install Source

The install source must be mounted at `/mnt/install_src`. If it is attached as a block device (e.g. `/dev/vdb`):

```bash
sudo mkdir -p /mnt/install_src
sudo chmod 0755 /mnt/install_src
sudo chown ubuntu:ubuntu /mnt/install_src
sudo mount -o defaults /dev/vdb /mnt/install_src
echo "/dev/vdb /mnt/install_src auto defaults 0 0" | sudo tee -a /etc/fstab
```

Alternatively, run the Ansible playbook:
```bash
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/buildout/dev/airgap_build_step0.yml \
  -e "ansible_user=$USER"
```

---

## Step 2 — Install Ansible

Install the required Python packages and Ansible from the bundled packages:

```bash
sudo dpkg -i /mnt/install_src/airgap/apt-debs/*.deb

cd ~
tar xzf /mnt/install_src/ansible-packages.tar.gz
pip3 install --no-index --find-links ./ansible-packages/ ansible --break-system-packages
```

**Log out and back in** so that `~/.local/bin` (where Ansible is installed) is on your `$PATH`.

---

## Step 3 — Install Docker

```bash
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/buildout/dev/airgap_build_step2.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src"
```

**Log out and back in** so your user has Docker permissions.

---

## Step 4 — Configure Deployment Variables

### `env` — Deployment settings

Edit `/mnt/install_src/data/env` and set your deployment variables:

```bash
export PLATFORM_DOMAIN=abi2.drai.auckland.ac.nz   # your domain, or 'localhost'
export PLATFORM_PROTOCOL=https                      # 'https' or 'http' (localhost only)
```

Then source it:
```bash
source /mnt/install_src/data/env
```

### `.env.template` — Secrets and configuration

Edit `/mnt/install_src/data/.env.template` and fill in all `<strong_value>` placeholders with real passwords and secrets. This file is used to generate the platform's `.env` on first deploy.

> **Note:** `.env` is generated from `.env.template` on **first deploy only** and is never overwritten by subsequent runs. Keep your secrets here.

---

## Step 5 — Install the Platform

```bash
ansible-playbook -i "localhost," -c local \
  /mnt/install_src/clean_src/digitaltwins-platform/buildout/dev/airgap_build_step3.yml \
  -e "ansible_user=$USER" \
  -e "install_src_dir=/mnt/install_src"
```

This playbook will:
- Sync platform code to `~/digitaltwins-platform/`
- Generate `nginx.conf`, `config.js`, `.env`, and `digitaltwins-realm.json` from templates
- Load Docker images from `digitaltwins-images-all.tar.gz`
- Initialise Airflow
- Bootstrap the Keycloak realm and SEEK admin user
- Start all services

---

## Step 6 — Start the Platform

**Log out and back in** (or run the export below) so `COMPOSE_FILE` is set:

```bash
export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml
```

Then bring everything up:

```bash
docker compose down
docker compose up -d
```

---

## Step 7 — Verify

Open your browser to:

| Service    | URL |
|------------|-----|
| Portal     | `https://${PLATFORM_DOMAIN}/` |
| SEEK       | `https://${PLATFORM_DOMAIN}/seek` |
| JupyterLab | `https://${PLATFORM_DOMAIN}/jupyter` |
| Keycloak   | `https://${PLATFORM_DOMAIN}/auth` |
| Airflow    | `https://${PLATFORM_DOMAIN}/airflow` |

### Pre-configured test users

The realm import includes three users for testing. **Remove or change these on any production system.**

| Username | Password |
|----------|----------|
| `mp1`    | `mp1`    |
| `mp2`    | `mp2`    |
| `admin`  | `admin`  |

---

## Notes

### SEEK asset recompilation

The SEEK/LDH container bakes assets at image build time without `RAILS_RELATIVE_URL_ROOT` set.
After first deploy (or after pulling a new LDH image version), recompile assets inside the running container:

```bash
docker exec seek bundle exec rake assets:precompile
docker exec seek bundle exec rake tmp:clear
docker compose restart seek workers portal-frontend
```

### Airgapping the VM (optional)

To block outbound network access:
```bash
/mnt/install_src/clean_src/digitaltwins-platform/buildout/util/airgap.sh
```

### Observability (Grafana)

Set these variables, then run the observability playbook:

```bash
export GRAFANA_ADMIN_PASSWORD=yourpassword
export GRAFANA_OAUTH_SECRET=yoursecret

ansible-playbook -i 'localhost,' -c local \
  -e "ansible_user=$(whoami)" \
  -e "install_src_dir=/mnt/install_src/airgap" \
  /mnt/install_src/install_observability_airgap.yaml
```

Grafana will then be available at `https://${PLATFORM_DOMAIN}/grafana`, integrated with Keycloak.

---

## Install Source Reference

| Path | Description |
|------|-------------|
| `data/.env.template` | Template for the platform `.env` — fill in secrets before first deploy |
| `data/env` | Deployment variables (`PLATFORM_DOMAIN`, `PLATFORM_PROTOCOL`) — source before running step3 |
| `data/digitaltwins-realm.json` | Keycloak realm import (generated from template by step3) |
| `data/fullchain.pem`, `data/privkey.pem` | SSL certificate and key (symlink to your domain's files) |
| `data/public_keys/` | SSH public keys of users to be granted access to the VM |
| `clean_src/` | Platform source code (repo + submodules) |
| `digitaltwins-images-all.tar.gz` | All Docker images, bundled for airgapped deployment |
| `airflow-worker.tar.gz` | Airflow worker image only, for compute nodes |
| `ansible-packages.tar.gz` | Python packages required to install Ansible |
| `airgap/apt-debs/` | `.deb` packages for `python3-pip` and `python3-venv` |
| `docker-29.4.0.tgz` | Docker engine bundle |
| `docker-compose-linux-x86_64-v5.1.2` | Docker Compose binary |

### Rebuilding the Docker image bundle

On a connected machine with a working deployment:

```bash
docker compose ps -aq | \
  xargs docker inspect --format '{{.Config.Image}}' | \
  sort -u | \
  xargs docker save | \
  gzip > digitaltwins-images-all.tar.gz
```

For the Airflow worker image only (used by compute nodes):
```bash
docker save digitaltwins-platform-airflow-worker:latest | gzip > airflow-worker.tar.gz
```
