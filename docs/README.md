# DigitalTWINS platform documentation

An index of the platform's guides. Start with the [project README](../README.md) and
the [architecture overview](architecture.md).

## Deploy and operate

| Guide | What it covers |
|---|---|
| [deployment.md](deployment.md) | Step-by-step install on a connected host (`http://localhost` or https), default credentials, and the upgrade to `/api` and `builder` |
| [../util/README.md](../util/README.md) | Install runbook for airgapped or production hosts with the Ansible playbooks, plus macOS/arm64 dev hosts, gateway routes and moving data between systems |
| [../util/BUILD-FULL-SYSTEM.md](../util/BUILD-FULL-SYSTEM.md) | The order to build a whole system in: build box, platform, observability, remote compute |
| [../util/INSTALL-BUNDLE.md](../util/INSTALL-BUNDLE.md) | The `/mnt/install_src` bundle an airgapped install runs from |
| [../util/compute-node-README.md](../util/compute-node-README.md) | Adding a remote Airflow compute node |
| [../util/RESET.md](../util/RESET.md) | Resetting a host back to a clean baseline with `util/reset.sh` |
| [production.md](production.md) | Hardening checklist before running in production |
| [domain-change.md](domain-change.md) | Changing `PLATFORM_DOMAIN` on an existing deployment |
| [diagnostics.md](diagnostics.md) | "How do I check X" commands, by area |

## Use the platform

| Guide | What it covers |
|---|---|
| [populating_data.md](populating_data.md) | Creating SEEK research objects, linking assays to workflows, deploying workflows, importing measurement datasets |
| [workflow-dag-authoring.md](workflow-dag-authoring.md) | Writing and deploying a script workflow as an Airflow DAG |
| [../services/api/README.md](../services/api/README.md) | The `digitaltwins` Python package: install, upload, query and download datasets |
| [../services/api/docs/import-dataset.md](../services/api/docs/import-dataset.md) | Importing a dataset from a terminal with one command |
| [../examples/workflow/workflow_image_conversion/README.md](../examples/workflow/workflow_image_conversion/README.md) | An example script workflow dataset (DICOM to NIfTI/NRRD) |

## Develop

| Guide | What it covers |
|---|---|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Branches, commits, tests and pull requests |
| [development.md](development.md) | Getting a code change into a running deployment, and what each kind of change needs |
| [testing.md](testing.md) | Unit and integration tests, CI jobs and required checks |
| [future_refactoring.md](future_refactoring.md) | Known technical debt |

## Reference

| Guide | What it covers |
|---|---|
| [architecture.md](architecture.md) | Overview, service and container diagrams, data stores, Keycloak clients |
| [gateway-pathway-access.md](gateway-pathway-access.md) | Which login protects each gateway path |
| [seek-integration.md](seek-integration.md) | How the platform authenticates to SEEK, account provisioning and visibility |
| [../services/keycloak/REALM.md](../services/keycloak/REALM.md) | The `digitaltwins` realm: clients, secrets, roles, groups and users |
| [../services/nginx/README.md](../services/nginx/README.md) | The edge gateway and how to change its routes |
| [../services/builder/README.md](../services/builder/README.md) | The tool, workflow and plugin builder service |
| [../services/portal/docs/plugin-system-architecture.md](../services/portal/docs/plugin-system-architecture.md) | How portal plugins are built, deployed and routed |
| [../services/airflow/README.md](../services/airflow/README.md) | The Airflow setup and its platform-managed DAG folders |
| [decisions/](decisions/) | Architecture Decision Records: why the platform is built the way it is |
