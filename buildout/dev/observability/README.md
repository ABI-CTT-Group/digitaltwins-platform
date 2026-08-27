# Observability config — where to change what (day-2)

This directory **is the single source of truth** for the Grafana/Loki/Mimir/Alloy
configuration. The install playbook (`../install_observability_airgap.yaml`) reads
these files straight from the git checkout, stages copies, substitutes `${...}`
placeholders on those copies, and applies them. **The `${...}` placeholders here are
deliberate — never resolve them in place.**

## The golden rule

**Change config by editing the file/variable here (in git), then re-applying — never
by hand-editing the running system.** Editing any of the following is a dead end,
because they get overwritten or aren't tracked:

- `/mnt/install_src/airgap/observability/*` — the airgap bundle no longer even holds
  these; it's only binaries/images/wheels/debs now.
- `/tmp/observability/*` — ephemeral per-run staging.
- `/etc/alloy/config.alloy` — redeployed from git on every run.
- Grafana **UI** edits (dashboards, datasources, settings) — not persisted to git;
  lost on redeploy. Put dashboards in `dashboards/` instead.

## What to change → where → how to apply

| You want to change | Edit | Apply |
|---|---|---|
| Grafana settings (datasources, resources, options) | `grafana-values.yaml` | re-run playbook, or targeted `helm -n grafana upgrade` (see `../helm_mod`) |
| Grafana admin pw / OAuth client secret / public URL | env: `GRAFANA_ADMIN_PASSWORD` / `GRAFANA_OAUTH_SECRET` / `PLATFORM_DOMAIN` (in `secrets.env`+`env`, sourced before the run) | re-run playbook. **The OAuth secret must equal the `grafana` client's secret in Keycloak** (rendered from `secrets.env` at realm first-boot). |
| Loki settings (retention, limits) | `loki-values.yaml` | re-run, or `helm -n loki upgrade loki charts/loki-*.tgz -f loki-values.yaml` |
| Mimir settings | `mimir-values.yaml` | re-run, or `helm -n mimir upgrade …` |
| Mimir object-store (MinIO) creds | env: `MIMIR_MINIO_ROOT_USER` / `MIMIR_MINIO_SECRET_KEY` | re-run |
| What Alloy scrapes / ships | `config.alloy` (`${NODE_NAME}` is filled from the host) | re-run, then `sudo systemctl restart alloy` (the playbook restarts it) |
| Grafana dashboards | `dashboards/cm-*.yaml` (ConfigMaps) | re-run, or `kubectl -n grafana apply -f dashboards/<file>` |
| The `/grafana` gateway route / node IP | `../../../services/nginx/snippets/platform-routes.conf` / `NODE_IP` (auto-derived by `gen-env.sh`) | `docker exec <gateway> nginx -t && nginx -s reload` (bind-mounted, live) |

## Applying changes

- **Full re-run** (`install_observability_airgap.yaml`) is idempotent — safe to re-run
  to reconcile any of the above. This is the canonical apply path.
- **Targeted** applies (faster, no full run): `helm upgrade` for a values change,
  `kubectl apply` for a dashboard, `systemctl restart alloy` for `config.alloy`,
  `nginx -s reload` for the gateway route.
- **Never** regenerate config by editing the bundle or the deployed copies — always
  git → apply, so the running state always matches what's committed.
