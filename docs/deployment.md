# Deploying the DigitalTWINS platform

This guide installs the platform by hand on a host **with Internet access**, either
for local development on `http://localhost` or on a domain over https. It runs the
same steps, in the same order, as the install playbook
[`util/airgap_build_step3.yml`](../util/airgap_build_step3.yml).

> [!NOTE]
> For an **airgapped** or production host, use the playbook instead: see
> [`util/README.md`](../util/README.md). To build a whole system with observability
> and remote compute, start at
> [`util/BUILD-FULL-SYSTEM.md`](../util/BUILD-FULL-SYSTEM.md). Before going live,
> work through the [production checklist](production.md).

**Requirements:** Ubuntu 24.04 (amd64), Docker Engine with the Compose v2 plugin
(`docker compose`), and git. An NVIDIA GPU is optional (see `AIRFLOW_WORKER_GPU`
below). To install Docker and add yourself to the `docker` group, follow
[Installing on a connected machine](../util/README.md#installing-on-a-connected-machine).
macOS and arm64 hosts work for development only; see
[Installing on a Mac or other arm64 host](../util/README.md#installing-on-a-mac-or-other-arm64-host).

Run every command below from the repository root.

---

## 1. Clone the repository

SEEK is a git submodule, so clone recursively:

```bash
git clone --recursive https://github.com/ABI-CTT-Group/digitaltwins-platform.git
cd digitaltwins-platform
```

In an existing clone, run `git submodule update --init --recursive` after each pull.

## 2. Configure

### 2.1 Fill in `env` and `secrets.env`

> [!IMPORTANT]
> `.env` is **generated**, not hand-edited. `.env.template` is a `${VAR}` template:
> copying it would leave literal `${...}` placeholders. Fill in the two input files
> below and run the generator instead.

```bash
cp env.template env                    # non-secret host config
cp secrets.env.template secrets.env    # every password and key
```

Edit `env`:

- **Protocol and domain.** For a local developer setup (http, no TLS), comment out
  the https block and uncomment the localhost block:
  ```bash
  export PLATFORM_PROTOCOL=http
  export PLATFORM_DOMAIN=localhost
  export KC_HOSTNAME_STRICT=false
  export KC_HOSTNAME_STRICT_HTTPS=false
  ```
  For a real deployment keep `https` and set `PLATFORM_DOMAIN` to your domain. The
  Keycloak URLs (`KC_HOSTNAME`, `KEYCLOAK_PUBLIC_URL`, `ORTHANC_KEYCLOAK_URL`),
  `NGINX_MODE` and `SSL` are derived from these two values, so they can't drift
  apart.
- **Platform admin.** `PLATFORM_ADMIN_USERNAME` (default `admin1`) and
  `PLATFORM_ADMIN_EMAIL` name one admin identity used by Keycloak, SEEK and Airflow.
  Its password is `PLATFORM_ADMIN_PASSWORD` in `secrets.env`.
- **GPU.** `AIRFLOW_WORKER_GPU=auto` gives the Airflow worker the host's NVIDIA GPU
  when the NVIDIA Container Toolkit is installed. Set `true` or `false` to force it.

Fill in **every** value in `secrets.env`, e.g. with `openssl rand -hex 32`
(`AIRFLOW__CORE__FERNET_KEY` needs a Fernet key; the file shows how to make one).
Keep `secrets.env` private: it is git-ignored.

### 2.2 Generate `.env` and the Keycloak realm

```bash
util/gen-env.sh -e env -s secrets.env     # renders .env; fails loudly on any unset variable
util/gen-realm.sh -e env -s secrets.env   # renders services/keycloak/import/digitaltwins-realm.json
```

`gen-env.sh` also renders `services/nginx/snippets/minio-discovery.json` from
`PLATFORM_DOMAIN`, which MinIO's single sign-on needs, and writes `COMPOSE_FILE`
into `.env` (adding the GPU and remote-compute overrides when enabled). Don't export
`COMPOSE_FILE` in your shell: it would override the value in `.env`.

Keycloak imports the realm **on its first boot only**. To change it later, edit the
live realm in the admin console or recreate Keycloak's data; see
[REALM.md](../services/keycloak/REALM.md).

### 2.3 SEEK's database settings

SEEK keeps its own MySQL, configured in
`services/seek/ldh-deployment/docker-compose.env`. Create it from the `MYSQL_*`
values in `secrets.env`:

```bash
set -a; . ./secrets.env; set +a
cat > services/seek/ldh-deployment/docker-compose.env <<EOF
MYSQL_HOST=db
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_DATABASE=seek
MYSQL_USER=seek
MYSQL_PASSWORD=${MYSQL_PASSWORD}
EOF
chmod 600 services/seek/ldh-deployment/docker-compose.env
```

### 2.4 TLS certificate (https only)

Put the certificate chain and key for `PLATFORM_DOMAIN` where the gateway reads them:

```bash
install -m 0644 /path/to/fullchain.pem services/nginx/certs/server.crt
install -m 0600 /path/to/privkey.pem  services/nginx/certs/server.key
```

[`util/issue-cert.sh`](../util/issue-cert.sh) and
[`util/renew-cert.sh`](../util/renew-cert.sh) obtain and renew Let's Encrypt
certificates. To test a domain whose DNS doesn't point at this host, add it to
`/etc/hosts`.

## 3. Build the images

```bash
docker compose build
```

## 4. Initialise Airflow

`airflow-init` migrates Airflow's database and creates its admin user (the platform
admin):

```bash
docker compose up airflow-init
docker compose down
```

## 5. Bootstrap SEEK

Start SEEK on its own, create the platform admin as SEEK's server admin, and turn on
the features the platform needs (single sign-on, programmes, workflows, the GA4GH
TRS API and git support):

```bash
set -a; . ./env; . ./secrets.env; set +a
docker compose up -d seek
```

Wait a minute or two for SEEK's first-boot migrations to finish
(`docker compose logs -f seek`), then:

```bash
util/create-admin-user.sh "$PLATFORM_ADMIN_USERNAME" "$PLATFORM_ADMIN_PASSWORD" "$PLATFORM_ADMIN_EMAIL"
SEEK_SITE_BASE_URL="${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/seek" util/enable-features.sh
docker compose down
```

If `create-admin-user.sh` fails because the `users` table doesn't exist yet, SEEK is
still migrating: wait and run it again.

## 6. Launch the platform

```bash
docker compose up -d
```

Then compile SEEK's web assets for the `/seek` path. The SEEK image ships them built
for the root path, so without this step SEEK's pages load without styles or scripts:

```bash
docker compose exec seek bundle exec rake assets:precompile
docker compose exec seek bundle exec rake tmp:clear
docker compose restart seek workers portal-frontend
```

Run these three commands again whenever the SEEK image changes or the SEEK container
is recreated (see [SEEK `/seek` asset precompile](../util/README.md#seek-seek-asset-precompile)).

To start the platform at boot, the playbook installs the
[`digitaltwins-platform.service`](../digitaltwins-platform.service) systemd unit; set
its `WorkingDirectory` to your clone if you install it by hand.

## 7. Add workflows

A new install has no workflow DAGs. A script workflow registered as a dataset is
deployed to Airflow automatically when an admin registers or approves it; see
[Populating data](populating_data.md) and
[Writing and deploying a script workflow DAG](workflow-dag-authoring.md). To copy
the DAGs of another deployment, use `util/sync-dags.sh`. New DAGs start paused:
un-pause them in the Airflow UI before launching an assay that uses them.

## 8. Service access and credentials

Open `http://localhost` or `https://<PLATFORM_DOMAIN>`. Every service is reached
through the gateway:

| Service | Path | Sign in with | Notes |
|:--|:--|:--|:--|
| Portal | `/` | Keycloak | Main entry point |
| REST API | `/api/` | Keycloak bearer token | Interactive docs at `/api/docs`; the portal's builder is at `/api/builder/` |
| SEEK | `/seek/` | Keycloak, or the platform admin's local SEEK account | Data catalogue |
| Airflow | `/airflow/` | Keycloak | Workflow runs; Keycloak users with the `airflow_admin` role are Airflow admins |
| JupyterHub | `/jupyter/` | Keycloak | Only members of the `admin` and `researcher` groups |
| Keycloak | `/auth/` | see below | Identity and access management |
| MinIO console | `/minio/` | Keycloak, or `minioadmin` / `MINIO_ROOT_PASSWORD` | Object storage |
| Orthanc 1 and 2 | `/orthanc-1/`, `/orthanc-2/` | Keycloak | PACS |
| HAPI FHIR | `/fhir/` | none | No authentication; see the [production checklist](production.md) |

**Accounts:**

| Account | Username | Password | Where it works |
|:--|:--|:--|:--|
| Platform admin | `PLATFORM_ADMIN_USERNAME` (default `admin1`) | `PLATFORM_ADMIN_PASSWORD` | Keycloak realm `digitaltwins` (so every service above), SEEK server admin, Airflow admin |
| Keycloak administrator | `admin` | `KC_BOOTSTRAP_ADMIN_PASSWORD` | Keycloak admin console (`/auth/admin/`, `master` realm) |
| Test users | `clinician`, `researcher`, `test1`, `test2` | same as the username | Keycloak realm `digitaltwins`. **Disable or remove them before production.** |

For each Keycloak client, role and group, see
[REALM.md](../services/keycloak/REALM.md). For who can reach which path, see
[gateway-pathway-access.md](gateway-pathway-access.md). To check on a running
platform, see [diagnostics.md](diagnostics.md).

## 9. Upgrading: `/digitaltwins-api` → `/api`, `portal-backend` → `builder`

The platform API moved from `/digitaltwins-api` to `/api`, and its service was renamed from
`digitaltwins-api` to `api`. The portal backend moved to its own service folder, `services/builder`,
and runs as the `builder` service; its endpoints moved from `/api/tools/...` and `/api/workflow/...`
to `/api/builder/tools/...` and `/api/builder/workflow/...`. The old paths no longer work: there is
no redirect. See the ADRs [2026-10-20-api-prefix-and-portal-builder-split](decisions/2026-10-20-api-prefix-and-portal-builder-split.md)
and [2026-10-21-builder-as-its-own-service](decisions/2026-10-21-builder-as-its-own-service.md).

An existing deployment upgrades once, from the repository root:

1. **Rename one secret, keeping its value.** In `secrets.env`, rename `PORTAL_DB_PASSWORD` to
   `BUILDER_DB_PASSWORD`. Keep the value: it is the password of the existing `portal` database
   role, and a new value would lock the builder out of its tables.
2. **Regenerate `.env`.** The `DIGITALTWINS_API_*` variables are now `API_*`, `API_PUBLIC_URL`
   ends in `/api`, `PORTAL_DB_*` is now `BUILDER_DB_*`, `BACKEND_PORT` / `PORTAL_BACKEND_URL` are
   `BUILDER_PORT` / `BUILDER_URL`, and `PORTAL_BACKEND_HOST` / `PORTAL_KEYCLOAK_BASE_URL` are gone
   (`PLATFORM_DOMAIN` / `KEYCLOAK_PUBLIC_URL` carry the same values):
   ```bash
   util/gen-env.sh -e env -s secrets.env
   ```
   On a remote Airflow compute node, regenerate its env too
   (`util/generate-compute-env.sh <portal_vlan_ip> > compute.env`) and restart its worker.
   Any DAG code of your own that reads `DIGITALTWINS_API_BASE_URL` or `DIGITALTWINS_API_PORT` must
   switch to `API_BASE_URL` / `API_PORT`.
3. **Rebuild and restart.** `--remove-orphans` removes the old `digitaltwins-api` and
   `portal-backend` containers. Stopping `portal-backend` stops every plugin backend it started and
   marks it down, as any restart of it always has; the builder does not start them again, so
   redeploy the ones you need from the Tool Hub (admin) afterwards. Then reload the gateway's routes:
   ```bash
   sudo docker compose build api builder portal-frontend
   sudo docker compose up -d --remove-orphans
   docker exec ${PROJECT_NAME}-gateway nginx -t && docker exec ${PROJECT_NAME}-gateway nginx -s reload
   ```
   JupyterHub restarts with the stack and registers the API under its new service name. Its
   startup also revokes the old `digitaltwins-api` service's token.
4. **Re-push stale FHIR links.** Measurement datasets pushed before the move link their files under
   `/digitaltwins-api/...` in HAPI. Re-push them, checking the list first:
   ```bash
   sudo docker compose exec api python -m digitaltwins.cli.repush_fhir_urls --dry-run
   sudo docker compose exec api python -m digitaltwins.cli.repush_fhir_urls
   ```
   Each re-push downloads the dataset from MinIO again and gives its HAPI resources new ids.
   Datasets never pushed, or whose push failed, get the new links on their next push.
