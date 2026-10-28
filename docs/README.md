# DigitalTWINS platform documentation

An index of the platform's guides. Start with the [project README](../README.md) and
the [architecture overview](architecture.md).

## Start here

Pick the path that fits what you're doing, and read the links in order.

| You are | Read |
|---|---|
| **New to the code** | [README](../README.md) → [architecture](architecture.md) → [code map](codemap.md) → [request flows](request-flows.md) → [glossary](glossary.md) → [development](development.md) → [testing](testing.md) |
| **An AI coding agent** | [AGENTS.md](../AGENTS.md) → [README](../README.md) → [code map](codemap.md) → the service's `README.md` and `AGENTS.md` → [ADRs](decisions/) |
| **Deploying or operating a host** | [deployment](deployment.md) → [util/README.md](../util/README.md) → [util/SCRIPTS.md](../util/SCRIPTS.md) → [diagnostics](diagnostics.md) → [production](production.md) |

[artifacts/](artifacts/) holds the dated design evidence for each past change. It's kept for audit
and may be out of date, so read the guides and [ADRs](decisions/) first.

## Deploy and operate

| Guide | What it covers |
|---|---|
| [deployment.md](deployment.md) | Step-by-step install on a connected host (`http://localhost` or https), default credentials, and the upgrade to `/api` and `builder` |
| [../util/SCRIPTS.md](../util/SCRIPTS.md) | One line on every script in `util/`, and which ones delete data |
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
| [../AGENTS.md](../AGENTS.md) | Instructions for AI coding agents: commands, safety rules, couplings and process rules |
| [development.md](development.md) | Getting a code change into a running deployment, and what each kind of change needs |
| [testing.md](testing.md) | Unit and integration tests, CI jobs and required checks |
| [future_refactoring.md](future_refactoring.md) | Known technical debt |

## Reference

| Guide | What it covers |
|---|---|
| [architecture.md](architecture.md) | Overview, service and container diagrams, data stores, Keycloak clients |
| [codemap.md](codemap.md) | Where code lives in each service, how the services connect, and where to look to change something |
| [request-flows.md](request-flows.md) | Sequence diagrams for sign-in, dataset upload, assay launch and tool deployment |
| [glossary.md](glossary.md) | Domain and platform terms: SDS, SEEK objects, SOP, tool, workflow, plugin |
| [gateway-pathway-access.md](gateway-pathway-access.md) | Which login protects each gateway path |
| [seek-integration.md](seek-integration.md) | How the platform authenticates to SEEK, account provisioning and visibility |
| [../services/keycloak/REALM.md](../services/keycloak/REALM.md) | The `digitaltwins` realm: clients, secrets, roles, groups and users |
| [../services/nginx/README.md](../services/nginx/README.md) | The edge gateway and how to change its routes |
| [../services/builder/README.md](../services/builder/README.md) | The tool, workflow and plugin builder service |
| [../services/portal/docs/plugin-system-architecture.md](../services/portal/docs/plugin-system-architecture.md) | How portal plugins are built, deployed and routed |
| [../services/airflow/README.md](../services/airflow/README.md) | The Airflow setup and its platform-managed DAG folders |
| [decisions/](decisions/) | Architecture Decision Records: why the platform is built the way it is |
| [artifacts/](artifacts/) | Dated design evidence for past changes, kept for audit (history, not reference) |
