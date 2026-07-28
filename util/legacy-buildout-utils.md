# Legacy `buildout/util` utilities (not ported)

The old `main_buildout` branch had a large `buildout/util/` toolkit. The current
`util/` carries forward only what fits the new template-driven, single-gateway,
consolidated-DB architecture. The scripts below were **left on `main_buildout`**
and are catalogued here so they can be found later.

They are **not** on `main`/this branch. Retrieve one without checking the branch out:

```bash
git show main_buildout:buildout/util/<name>            # print it
git show main_buildout:buildout/util/<name> > util/<name>   # pull it over
```

> Purposes below are **inferred from the filename** unless noted — read the file
> before trusting it. Most predate the new architecture and are likely stale.

## Already carried over (for reference)

| Old (`buildout/util/`) | New (`util/`) |
|---|---|
| `airgap.sh`, `unairgap.sh` | same names |
| `create-admin-user.sh`, `enable-features.sh`, `generate-token.sh` | same names |
| `mount_install_src` | `mount_src.sh` (hardened) |
| `backup_data.sh` | `stage-dump.sh` + `portal-restore.sh` (adapted for migration) |
| `export_realm_and_users`, `realm_exporter`, `mkbundle` | same names (kept as legacy reference) |

## Not ported — catalogued here

### Airgap enforcement
| File | Inferred purpose |
|---|---|
| `airgap_enforce.sh` / `airgap_enforce.yml` | Stricter airgap enforcement (likely superseded by `airgap.sh`). |
| `airgap_unenforce.sh` / `airgap_unenforce.yml` | Reverse of the above (cf. `unairgap.sh`). |

### Backup / volumes (cold, raw-volume style)
| File | Inferred purpose |
|---|---|
| `backup.sh` | Tar the docker volumes to `~/backups`. |
| `backup_vols_cold.sh` | Cold volume backup (requires `docker compose down`). |
| `new_vols` / `delete_vols` / `restore_vols` | Create / remove / restore the named data volumes. Note: these hardcode the old volume-name list — the new migration path uses logical dumps instead. |

### Certificates
| File | Inferred purpose |
|---|---|
| `create_root_ca` | Create a root CA. **Deprecated** per the old readme ("got a cert from zerossl"). |
| `create_server_jks` / `create_app_cert` / `create_nginx_cert` | Server keystore / app / nginx cert creation (CA-era). |
| `getcert` | Obtain a cert (Let's Encrypt?). |
| `renew_cert` | Renew a cert. |

### Keycloak / tokens
| File | Inferred purpose |
|---|---|
| `integrate-keycloak.sh` | Wire a service to Keycloak. |
| `get_token` / `get_token2` / `get_token3` | Fetch OIDC/access tokens (iterations). |

### Remote compute nodes
| File | Inferred purpose |
|---|---|
| `generate-compute-env.sh` | Generate the `.env` for an Airflow remote-compute worker. |
| `ufw_for_remote_compute.sh` | UFW rules for a remote compute node. |
| `ufw_for_walled_garden.sh` | UFW rules for a walled-garden network. |

### Code sync / deploy
| File | Inferred purpose |
|---|---|
| `clean_src_syncer` | Sync `clean_src` (the Mac→box rsync we currently do by hand). |
| `sync_vms.sh` | Sync between VMs. |
| `deploy-sync-excludes` | rsync exclude list for deploys. |

### Misc
| File | Inferred purpose |
|---|---|
| `swap_seek_ip.sh` | Swap SEEK's IP / re-resolve DNS (cf. the post-restart SEEK boot window). |
| `tagger` | Tag docker images (for the freeze/registry). |
| `rebuild.sh` | Rebuild the stack. |
| `nuker` | Tear everything down (destructive). |
| `api_examples.txt` | REST API usage examples (reference notes). |
