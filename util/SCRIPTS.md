# util/ script index

`util/` holds the scripts, Ansible playbooks and guides used to build, install and run the platform. `SCRIPTS.md` (this file) indexes everything in it; [`README.md`](README.md) is the install runbook.
**Destructive?** means the entry deletes or overwrites data, volumes, users, permissions or certs. `make docs-check` fails if an entry in `util/` is missing here, so add a row when you add or rename one.

## Guides in this folder

- [`README.md`](README.md): install runbook for the portal platform, airgapped or connected, plus data transfer, the SEEK admin scripts and observability.
- [`BUILD-FULL-SYSTEM.md`](BUILD-FULL-SYSTEM.md): ordered runbook for a whole system (build box, portal, observability and remote compute).
- [`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md): what's in the `/mnt/install_src` bundle and how to rebuild each piece.
- [`RESET.md`](RESET.md): returning a box to a clean baseline with `reset.sh`.
- [`compute-node-README.md`](compute-node-README.md): installing a remote Airflow compute node.
- [`legacy-buildout-utils.md`](legacy-buildout-utils.md): the old `buildout/util` scripts that weren't ported.

## Install and airgap bundles

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `build-bundle.sh` | Builds the whole airgap install bundle in one command (phase A of the full-system runbook) and ends with a completeness check. | Build box (connected), as your normal user | Only with `--clean` (deletes generated bundle files and all platform Docker volumes) | [BUILD-FULL-SYSTEM.md](BUILD-FULL-SYSTEM.md) |
| `fetch_airgap.sh` | Downloads the offline binaries (k3s, k9s, Helm, Alloy), k3s system images, Python wheels and apt debs into `airgap/`. | Build box (connected) | No | [README.md](README.md#observability-separate-optional) |
| `build-apt-debs.sh` | Builds the offline apt package set, with its full dependency closure, as a local apt repo. | Build box (connected, Ubuntu 24.04) | No | [README.md](README.md#2-install-ansible-from-the-local-packages) |
| `install-apt-debs.sh` | Installs packages from the bundled local apt repo on an airgapped box. | Target host, as root | No | [README.md](README.md#2-install-ansible-from-the-local-packages) |
| `freeze_images.sh` | Saves every Docker image the running platform uses into `digitaltwins-images-all.tar.gz`. | Build box (connected, stack running) | No | [README.md](README.md#rebuilding-the-frozen-image-archive-connected-host) |
| `build_image_bundle.sh` | Builds the observability image archive for k3s from the Helm charts; no running stack needed. | Build box (connected, with k3s and Helm) | No | [BUILD-FULL-SYSTEM.md](BUILD-FULL-SYSTEM.md) |
| `fetch_airgap_images.sh` | Exports every image in a running k3s into the observability image archive. The runbook prefers `build_image_bundle.sh`. | Build box (observability stack running) | No | [BUILD-FULL-SYSTEM.md](BUILD-FULL-SYSTEM.md) |
| `mkbundle` | Tars the contents of an install-source directory (default `/mnt/install_src`) into one archive. | Any host | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `mount_src.sh` | Mounts the install-source drive at `/mnt/install_src` and adds it to `/etc/fstab` (step 0). | Target host, as root | No | [README.md](README.md#0-mount-the-install-source) |
| `airgap.sh` | Sets UFW to deny all outgoing traffic and allow only SSH, HTTP and HTTPS in, to simulate an airgap (step 1). | Target host, as root | No | [README.md](README.md#1-optional-airgap-the-vm) |
| `unairgap.sh` | Allows outgoing traffic in UFW again. | Target host, as root | No | [README.md](README.md#1-optional-airgap-the-vm) |
| `airgap_build_step2.yml` | Ansible playbook: installs Docker and the Compose plugin from the bundled static binaries (step 2). | Target host (Ansible, `-c local`) | No | [README.md](README.md#3-install-docker-playbook) |
| `airgap_build_step3.yml` | Ansible playbook: deploys the platform (code sync, config rendering, images, SEEK bootstrap, stack start, systemd unit). | Portal host (Ansible, `-c local`) | Yes (mirrors code into the runtime copy with `--delete`; data volumes kept) | [README.md](README.md#5-deploy-the-platform-playbook) |
| `authorise-keys.yaml` | Ansible playbook: adds the bundle's operator SSH public keys to your `authorized_keys`, for boxes that don't run step 3. | Any target, usually the compute node (Ansible, `-c local`) | No | [BUILD-FULL-SYSTEM.md](BUILD-FULL-SYSTEM.md) |

## Environment and secrets

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `gen-env.sh` | Renders `.env` from `.env.template` plus the `env` and `secrets.env` input files. | Target host, from the repo root | No | [deployment.md](../docs/deployment.md#22-generate-env-and-the-keycloak-realm) |
| `gen-realm.sh` | Renders the Keycloak realm import from its template plus the `env` and `secrets.env` input files. | Target host, from the repo root | No | [REALM.md](../services/keycloak/REALM.md) |

## TLS certificates

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `issue-cert.sh` | Gets a Let's Encrypt cert with certbot's standalone mode before the platform is installed, and copies it into the bundle's `data/`; takes the domain. | Target host, as root (port 80 free, internet access) | Yes (overwrites that domain's cert files and the `fullchain.pem`/`privkey.pem` links in `data/`) | [deployment.md](../docs/deployment.md#24-tls-certificate-https-only) |
| `renew-cert.sh` | Renews the platform's Let's Encrypt cert through the running gateway's webroot and reloads nginx, with no downtime. | Portal host, as root (outbound internet) | Yes (replaces the gateway's `server.crt`/`server.key` and the bundle's copies) | [deployment.md](../docs/deployment.md#24-tls-certificate-https-only) |

## Keycloak

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `patch_keycloak_realm.py` | Adds a target host's redirect URIs and web origins, copied from the `localhost` ones, to the rendered realm import file. | Any host with the repo (Python 3) | No | — |
| `update_keycloak_domain.py` | Adds a new domain's redirect URIs and web origins, copied from the `localhost` ones, to every client in a live realm through the admin API. | Any host that can reach Keycloak (Python `requests`) | No | — |
| `fix_admin_cli.py` | Makes the realm's `admin-cli` client confidential with a given secret, and gives its service account user-management roles. | Any host that can reach Keycloak (Python `requests`) | Yes (replaces the `admin-cli` client's secret) | — |
| `fix_api_role.py` | Gives the `service-account-api` user the `airflow_admin` realm role. | Any host that can reach Keycloak (Python `requests`) | No | — |

## SEEK administration

The shell scripts reach SEEK with `docker compose exec seek`. The `.rb` files are Rails runner scripts with no wrapper: to use one, copy it into the `seek` container and run it with `rails runner` from `/seek`.

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `create-admin-user.sh` | Creates a SEEK server-admin user with a local password or a Keycloak-only login; skips one that already exists. | Portal host, from the repo root (execs into `seek`) | No | [deployment.md](../docs/deployment.md#5-bootstrap-seek) |
| `enable-features.sh` | Turns on the SEEK features the platform needs and sets the site base URL from `SEEK_SITE_BASE_URL`. | Portal host, from the repo root (execs into `seek`) | No | [deployment.md](../docs/deployment.md#5-bootstrap-seek) |
| `set-seek-password.sh` | Sets an existing SEEK user's local password. | Portal host, from the repo root (execs into `seek`) | Yes (replaces the user's password) | [development.md](../docs/development.md#change-type-playbook) |
| `seek-user-report.sh` | Read-only list of SEEK people: login, email, linked Keycloak `sub`, admin status and memberships. | Portal host (execs into `seek`) | No | [README.md](README.md#seek-admin--ownership-scripts) |
| `promote-seek-admin.sh` | Makes the SEEK person linked to a Keycloak `sub` a server admin; takes the sub. | Portal host (execs into `seek`) | No | [README.md](README.md#seek-admin--ownership-scripts) |
| `demote-seek-admin.sh` | Removes server-admin rights from the person linked to a Keycloak `sub`; refuses for the last admin unless `-f`. | Portal host (execs into `seek`) | Yes (removes admin rights) | [README.md](README.md#seek-admin--ownership-scripts) |
| `add-seek-project-member.sh` | Adds a person straight to a SEEK project, skipping the join request; takes a person and a project id. | Portal host (execs into `seek`) | No | [README.md](README.md#seek-admin--ownership-scripts) |
| `rm-seek-project-member.sh` | Removes a person from a SEEK project, with any project roles they held there. | Portal host (execs into `seek`) | Yes (deletes the membership and those roles) | [README.md](README.md#seek-admin--ownership-scripts) |
| `set-seek-programme-activation.sh` | Activates or deactivates a SEEK programme; deactivating hides it from ordinary users without deleting anything. | Portal host (execs into `seek`) | No | [README.md](README.md#seek-admin--ownership-scripts) |
| `transfer-seek-ownership.sh` | Moves item ownership and project or programme roles from one SEEK person to another, then rebuilds SEEK's permission cache and search index. | Portal host (execs into `seek`) | Yes (rewrites ownership and roles; asks first unless `-y`) | [README.md](README.md#seek-admin--ownership-scripts) |
| `rm-seek-tree.sh` | Deletes a SEEK programme or project and everything under it, whoever owns it; dry run unless `-y`. | Portal host (execs into `seek`) | Yes (deletes the whole tree) | [README.md](README.md#seek-admin--ownership-scripts) |
| `grant_project_access.rb` | Adds a person to the given projects and gives each project view and download access to all its items; takes a person id and project ids. | Inside the `seek` container (`rails runner`) | No | — |
| `grant_api_permissions.rb` | Makes every item in every project private and gives one API user view access to them; takes a login or email. | Inside the `seek` container (`rails runner`) | Yes (sets every item and project default to private) | — |
| `rollback_api_permissions.rb` | Removes the `admin` user's explicit permissions from every item in every project. | Inside the `seek` container (`rails runner`) | Yes (deletes those permissions) | — |
| `update_seek_permissions.rb` | Sets every project's default policy and every item to private (`NO_ACCESS`). | Inside the `seek` container (`rails runner`) | Yes (overwrites all sharing policies) | — |
| `revert_seek_permissions.rb` | Sets every private item and project default back to `ACCESSIBLE`; the reverse of `update_seek_permissions.rb`. | Inside the `seek` container (`rails runner`) | Yes (overwrites sharing policies, including ones that were private before) | — |

## Backup, restore and volumes

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `stage-dump.sh` | Read-only dump of an instance for migration: Postgres databases, SEEK, MinIO, plugin configs, and JupyterHub and Orthanc volumes. | Source host | No | [README.md](README.md#transferring-data-from-one-system-to-another) |
| `portal-restore.sh` | Restores a `stage-dump.sh` output into this instance, then re-applies the SEEK features and the platform admin. | Target host | Yes (overwrites the target's databases, SEEK, MinIO, and Orthanc and JupyterHub volumes; asks first) | [README.md](README.md#transferring-data-from-one-system-to-another) |
| `docker_archive_volumes.sh` | Tars every `digitaltwins-platform*` Docker volume into a backup directory; takes the directory. | Any Docker host | No | — |
| `docker_restore_volumes.sh` | Extracts each `<volume>.tar.gz` in a directory into the volume of that name, creating it if needed. | Any Docker host | Yes (writes over existing volume contents) | — |
| `docker_delete_volumes.sh` | Deletes every `digitaltwins-platform*` Docker volume, without asking. | Any Docker host | Yes (deletes all platform volumes) | [BUILD-FULL-SYSTEM.md](BUILD-FULL-SYSTEM.md) |

## Syncing code, DAGs and runtime

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `sync-runtime.sh` | Mirrors the bundle's `clean_src` checkout into the runtime copy, keeping generated files, then renders any that are missing; `-n` previews. | Portal host | Yes (rsync `--delete` on the runtime copy; generated files kept) | [development.md](../docs/development.md) |
| `sync-dags.sh` | Copies Airflow DAGs from one instance to another over ssh. | Control machine that can ssh to both | Only with `--mirror` (empties the target's DAG folder first) | [README.md](README.md#transferring-data-from-one-system-to-another) |
| `sync-compute-dags.sh` | Copies Airflow DAGs, plugins and config from the portal to a remote compute node. | Portal host | Only with `--delete` (removes node files the portal doesn't have) | [compute-node-README.md](compute-node-README.md#f-keeping-dags-in-sync-ongoing) |

## Reset

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `reset.sh` | Returns a box to a clean baseline so the install can be re-run, at one of three cumulative levels; `--dry-run` previews. | Target host, as root, run from the bundle copy | Yes (removes the stack, all data volumes and the runtime copy; higher levels also remove Docker, UFW rules and `/etc/letsencrypt`) | [RESET.md](RESET.md) |

## Remote compute and observability

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `compute-build.sh` | Copies the parts of the install bundle a compute node needs from the portal to the node; takes the node's ssh address. | Portal host | No | [compute-node-README.md](compute-node-README.md#b-compute-vm-a-clean-vm) |
| `generate-compute-env.sh` | Prints a compute node's `.env`, built from the portal's `.env` so the shared secrets match; takes the portal's VLAN IP. | Portal host | No | [compute-node-README.md](compute-node-README.md#a-portal-side-run-once-on-the-portal) |
| `ufw_for_remote_compute.sh` | Opens the portal ports a compute node needs in UFW, only to that node's IP; takes the IP. | Portal host | No | [compute-node-README.md](compute-node-README.md#a-portal-side-run-once-on-the-portal) |
| `install_observability_airgap.yaml` | Ansible playbook: installs k3s and the Grafana, Loki and Mimir stack, plus Alloy, from the airgap bundle. | Portal host (Ansible, `-c local`) | No | [README.md](README.md#observability-separate-optional) |
| `helm_mod` | Re-applies the Grafana Helm release with the admin password and OAuth secret from the environment. | Portal host, from `util/` (needs k3s and Helm) | No | [README.md](README.md#adjusting-observability-after-install) |
| `enable_compute_observability_ingress.yaml` | Ansible playbook: opens the Loki and Mimir ports to a compute node and binds their k3s port-forwards to `0.0.0.0`. | Portal host (Ansible, `-c local`) | No | [compute-node-README.md](compute-node-README.md#g-ship-telemetry-to-the-observability-stack-optional) |
| `install-compute-alloy.sh` | Installs Grafana Alloy on a compute node to ship its logs and metrics to the portal; takes the portal's VLAN IP. | Compute node, as your login user | No | [compute-node-README.md](compute-node-README.md#g-ship-telemetry-to-the-observability-stack-optional) |
| `install_compute_observability_airgap.yaml` | Ansible playbook equivalent of `install-compute-alloy.sh`. | Compute node (Ansible, `-c local`) | No | [compute-node-README.md](compute-node-README.md#g-ship-telemetry-to-the-observability-stack-optional) |
| `observability/` | Helm charts, values files, Alloy configs and Grafana dashboards that the observability playbooks read. | Not run (config) | No | [README.md](README.md#observability-separate-optional) |

## Tests and shared libraries

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `lib/` | Shell helpers sourced by other scripts. `compose-file.sh` picks the compose files that `gen-env.sh` writes into `COMPOSE_FILE`. | Sourced by `gen-env.sh` | No | [ADR](../docs/decisions/2026-10-23-airflow-worker-gpu-opt-in.md) |
| `tests/` | Shell tests for `util/`, run with `make test-util`. | Any host (via `make`) | No | [testing.md](../docs/testing.md) |
| `check_docs.py` | Checks the docs: relative links, the services code map, this index and the agent pointer files. Run with `make docs-check`. | Any host (via `make`) | No | [testing.md](../docs/testing.md#docs-check) |

## Legacy and one-off

| Script | Purpose | Runs on | Destructive? | Details |
|---|---|---|---|---|
| `export_realm_and_users` | Legacy: stops Keycloak, exports the `digitaltwins` realm with its users to a timestamped JSON file, then starts it again. | Portal host, from the repo root | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `realm_exporter` | Legacy: the same export into `./export/`. It never sets `REALM`, so it fails unless you set it first. | Portal host, from the repo root | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `get_token` | Legacy dev helper: prints a Keycloak access token for the Airflow client using a password grant. Hardcodes an old test domain and test user. | Any host | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `get_token2` | Legacy dev helper: prints an Airflow API token for a hardcoded test user on an old test domain. | Any host | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `get_token3` | Legacy dev helper: gets a Keycloak token, then exchanges it for an Airflow token. Hardcodes an old test domain and test user. | Any host | No | [legacy-buildout-utils.md](legacy-buildout-utils.md) |
| `populate-cpu-burn-assay.sh` | One-off: creates a demo "CPU Burn" programme-to-assay chain in SEEK with a sample dataset, wired to the `workflow_9000` DAG. Re-running creates a second chain. | Portal host, from the repo root | No | [populating_data.md](../docs/populating_data.md#method-2-using-seeks-rest-api) |
