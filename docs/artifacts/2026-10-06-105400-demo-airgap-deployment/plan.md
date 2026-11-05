# Demo deployment of DigitalTWINS platform on a remote airgapped Ubuntu server

## Context

Stand up a fresh deployment of the platform on a remote, bare Ubuntu server reached only as `http://localhost` (browse on the box or via SSH tunnel), with **all-new credentials**, carrying over **only** Test Programme (7) / Test Project (12) and the data needed to run the three demo assays (SEEK 41 notebook, 42 script/Airflow, 43 GUI/VolView) from `study-dashboard?trail=7,12,10,11`. Artifacts travel by portable drive. The current box keeps a backup (data + config, no images).

**Strategy (user-approved): full restore, then prune.** SEEK/Postgres IDs (project 12, assays 41–43, workflows 89/95/97, dataset UUIDs, DAG id `workflow_89`, jupyter folder `assay_41`, `portal.workflow_builds.seek_id=95`) are all interlocked; re-registration would renumber everything. So: `stage-dump` → prune the dump copy → `portal-restore` on the target → prune SEEK/DB on the target.

**User decisions:**
- Access: keep `PLATFORM_PROTOCOL=http`, `PLATFORM_DOMAIN=localhost`; browse via SSH tunnel (`ssh -L 8080:localhost:80 <server>`) or on the server.
- Transfer: portable drive mounted as `/mnt/install_src` on the target (bare Ubuntu 24.04, assume nothing installed; it does have PyPI access, so the assay-41 notebook's `%pip install sparc-me` works — no image change needed).
- Users: **no test_admin** — reuse `admin1` with a **new** `PLATFORM_ADMIN_PASSWORD`; **keep** the 4 demo realm users (test1/test2/clinician/researcher). No realm-template or repo changes.
- Prune: delete other programmes/projects + **sweep SEEK orphans** (assets left behind by `rm-seek-tree.sh`); drop Orthanc PACS data; skip observability stack.
- Deployment doc: markdown in `/home/clin864/Projects/archive/digitaltwins-platform/demo/` **only** — outside the repo, never committed (nothing to gitignore since the path is outside the repo; do not copy it into the repo).
- Existing dump: `/home/clin864/Projects/archive/digitaltwins-platform/20261006/` (11 GB, complete except `hapi.sql` — HAPI lives in the shared Postgres, which `stage-dump.sh` skips). Keep this directory **pristine as the backup**; all pruning happens on a copy.

## Key facts from exploration

- Live stack runs from `/home/clin864/Projects/digitaltwins-platform` (containers `digitaltwins-platform-*`; DAGs bind-mounted from `services/airflow/dags/` there).
- `util/portal-restore.sh` restores whatever files exist in the dump dir (every step is `[ -f ]`/`[ -d ]`-guarded) → pruning the dump copy is the selective-restore lever. It does NOT touch Keycloak (fresh realm render = fresh credentials, free) or Airflow DAGs/metadata.
- Keep-list (digitaltwins DB + MinIO):
  - measurements: `e77702f0…` (test_dicom), `754c4202…` (test_curated_dataset), `8dfbb026…` (test_converted)
  - tools: `74e61c96…` (dicom_to_nifti, seek 87), `750ca604…` (dicom_to_nrrd, 88), `1a5830fa…` (mri_curation, 96), `718cb9b2…` (volview, 94)
  - workflows: `752540e2…` (image_conversion, 89), `1a6c77d6…` (mri_curation, 97), `7434f526…` (volview, 95) + wizard-build dirs `workflowimageconversion_47940800`, `workflowmricuration_5708120f`, `workflowvolview_7c361058`
  - tool-builds: `workflowvolview_7c361058` (VolView UMD bundle)
  - assay rows: 41, 42, 43 only (others: 1, 24, 31, 32, 37, 38, 39 → prune)
- Prune-list: measurements `199eeb0e…`, `a8221374…`, `clinical report.xlsx`; whole `models/` bucket dir; workflows `276ddb38…`, `270752f8…`; `airflow-workspace/` contents (scratch); both Orthanc tars.
- SEEK to delete on target: programmes 1, 2, 3, 5 (projects 2–11) + project 1 (no programme). Keep programme 7 / project 12. Workflows 89/95/97 are already in project 12 ✓.
- `secrets.env`: all values get new `openssl rand -hex 32` **except** `AIRFLOW_DB_PASSWORD=airflow` and `KEYCLOAK_DB_PASSWORD=keycloak` — these are hardcoded in `services/postgres/{airflow,keycloak}_init.sql`; changing them breaks a fresh install. Document this; they're docker-network-internal.
- The `workflow_89` DAG file (`services/airflow/dags/workflow_image_conversion_test.py`, gitignored) hardcodes the **live MinIO secret** as fallback (line 56). Must be sanitized before copying. New DAGs boot **paused** → explicit unpause step.
- `freeze_images.sh` images are domain-portable (no baked domain; `INSTALL-BUNDLE.md`'s re-freeze note is stale). Freeze from the live stack with `PLATFORM_DIR=/home/clin864/Projects/digitaltwins-platform`.
- admin1's pinned Keycloak sub (`1afb2774-0277-494f-a976-34a72683d972`) survives the realm re-render, so the restored SEEK `identities` row keeps working and `portal-restore.sh` step 10 re-promotes admin1 to SEEK server admin automatically. Verify (and if needed set) admin1's **project administrator** role in project 12.
- Jupyter: restore `jupyter_user_vols/digitaltwins-platform_jupyterhub_user_admin1.tar`, pruned inside to `assay_41/` only (drop assay_31/32/37/40, PACS). URL `/jupyter/user/admin1/lab/tree/assay_41` then works unchanged.
- GUI assay needs no extra container: VolView bundle is served from the public-read `tools` bucket; portal rows (`portal.workflows` + `portal.workflow_builds`) come in the digitaltwins dump (includes the `portal` schema).

## Workspace

Everything generated lives in `/home/clin864/Projects/archive/digitaltwins-platform/demo/`:

```
demo/
├── DEPLOYMENT.md              # the deployment runbook (user-facing doc, secrets <REDACTED>)
├── install_src/               # bundle staging → rsync to portable drive
│   ├── clean_src/digitaltwins-platform/   # fresh recursive clone
│   ├── data/{env, secrets.env}            # NEW values (never from repo root / old data)
│   ├── digitaltwins-images-all.tar.gz
│   ├── docker-29.4.0.tgz, docker-compose-linux-x86_64-v5.1.2
│   ├── airgap/apt-debs/, ansible-packages.tar.gz
│   ├── dags-payload/          # sanitized workflow_89 DAG + tool/ package
│   └── dtwins-migrate/        # PRUNED copy of the 20261006 dump (+ hapi.sql)
└── scripts/
    ├── prune-dump.sh          # prunes dtwins-migrate copy per keep-list
    ├── prune-digitaltwins.sql # target-side DB prune (assays, datasets, portal schema)
    └── seek-orphan-sweep.rb   # target-side rails-runner orphan sweep
```

## Steps

### 1. Complete the backup (source box, read-only)
- `pg_dump hapi` from `digitaltwins-platform-database-1` → `20261006/hapi.sql` (stage-dump skipped it because HAPI is in the shared Postgres).
- Archive config into `20261006/`: live DAG folder copy, Keycloak realm export (`kc.sh export` or the rendered realm), already-present `env`/`secrets.env`/`.env`. This directory is the backup — leave otherwise untouched.

### 2. Build the pruned migration set (source box)
- Copy `20261006/` → `demo/install_src/dtwins-migrate/`, then `scripts/prune-dump.sh`:
  - delete both Orthanc tars, `minio/models/`, measurements/workflows prune-list items, `airflow-workspace` contents;
  - repack the admin1 jupyter tar keeping only `assay_41/`;
  - keep `digitaltwins.sql`, `seek_mysql.sql`, `hapi.sql`, `seek_filestore/`, `plugin_registry.db`, `nginx_plugin_configs.tar` as-is (DB pruning happens on the target).
  - remove the copied `env`/`secrets.env`/`.env` from the migrate dir (old secrets must not travel).
- `dags-payload/`: copy `workflow_image_conversion_test.py` + `tool/` (no `__pycache__`, no `tool/tests/`), **strip the hardcoded MinIO secret fallback** (fail-loud `os.environ["MINIO_SECRET_KEY"]` instead); verify the live worker gets `MINIO_SECRET_KEY` from env (`docker exec … printenv`) so the fallback is truly unused.

### 3. Build the install bundle (source box, internet)
Follow `util/BUILD-FULL-SYSTEM.md` Phase A selectively (skip A.3 deploy — the live stack already runs the current images — and skip all observability pieces):
- Fresh `git clone --recursive` into `install_src/clean_src/` (never copy the working tree — repo root holds live secrets/.env).
- `util/build-apt-debs.sh`, download docker 29.4.0 tgz + compose v5.1.2 binary, `pip3 download ansible` → `ansible-packages.tar.gz`, `docker pull alpine && docker save` (restore scripts need alpine + minio/mc; `freeze_images.sh` includes both via `EXTRA_IMAGES`).
- Verify running containers match current code (recent `docker compose build`), then `PLATFORM_DIR=/home/clin864/Projects/digitaltwins-platform INSTALL_SRC_DIR=$PWD/install_src util/freeze_images.sh`. Check the archive lists the singleuser + any plugin images.
- Fill `install_src/data/env` (http / localhost / strict=false, `REMOTE_COMPUTE=false`) and `data/secrets.env` from the templates with **new** values (`openssl rand -hex 32`); new human `PLATFORM_ADMIN_PASSWORD`; keep `AIRFLOW_DB_PASSWORD=airflow`, `KEYCLOAK_DB_PASSWORD=keycloak` (hardcoded in init SQL). Run `gitleaks detect --no-git` over `demo/` docs/scripts (not the secrets files themselves) before any repo sync.
- rsync `install_src/` to the portable drive.

### 4. Install on the remote server (per util/README steps 0–5)
- Mount drive at `/mnt/install_src` (`mount_src.sh`, `SRC_DEV=` override for USB). Optionally `airgap.sh`.
- `install-apt-debs.sh` → ansible from wheels → re-login → `airgap_build_step2.yml` (docker) → re-login.
- `set -a; source data/secrets.env data/env; set +a` → `airgap_build_step3.yml` (default frozen-image load). Smoke-check `/`, `/seek`, `/auth`, `/airflow`, `/jupyter` as `http://localhost`.

### 5. Restore + prune data (remote)
- Copy `dtwins-migrate/` to `/tmp/dtwins-migrate`, run `util/portal-restore.sh` (restores digitaltwins+portal schema, hapi, SEEK DB+filestore, MinIO keep-set, plugin registry, nginx plugin configs, admin1 jupyter volume; re-stamps SEEK site base + re-promotes admin1 by sub).
- SEEK prune: `util/rm-seek-tree.sh programme 1|2|3|5 -y` and `project 1 -y`; then `scripts/seek-orphan-sweep.rb` via rails runner — destroy every Workflow/SOP/DataFile/Model/Document/Publication etc. whose projects don't include 12 (and assay 41's stale SOP 38 link), rebuild auth lookup + reindex; finish with `util/seek-user-report.sh` to review carried-over SEEK people (remove non-project-12 people or at least confirm no local-password logins remain; reset any needed local password with `util/set-seek-password.sh` to new values).
- DB prune: `scripts/prune-digitaltwins.sql` — delete `assay` rows ∉ {41,42,43} (+ `assay_input`/`assay_output`), `dataset` rows ∉ keep-list (+ `dataset_description`, `dataset_mapping`, `manifest`, `subject`/`sample` orphans, `dataset_fhir_annotation`, `upload_session`), `portal.workflows`/`portal.workflow_builds` rows not tied to seek 89/95/97. (HAPI restored whole — contains FHIR annotations for pruned datasets; accepted leftover, invisible in the portal.)
- Verify admin1 is **project administrator** of project 12 (carried by the dump); if not: `util/add-seek-project-member.sh sub:1afb2774-… 12` + rails one-liner to grant the role.

### 6. Airflow + assays (remote)
- Copy `dags-payload/` into `~/digitaltwins-platform/services/airflow/dags/`, wait for the dag-processor scan (~1 min), then `docker compose exec airflow-scheduler airflow dags unpause workflow_89` and confirm `is_paused=False` + it appears at `/airflow/dags/workflow_89`.
- admin1 must log into the portal once (fresh Keycloak session) — SEEK identity already maps via the pinned sub.

### 7. End-to-end verification (remote, as admin1 with the new password)
- `http://localhost/study-dashboard?trail=7,12,10,11` lists exactly assays 41/42/43, Launch enabled (`ready=t`).
- Assay 41: Launch opens `/jupyter/user/admin1/lab/tree/assay_41`; volume spawns with the folder; notebook's `%pip install sparc-me` succeeds (PyPI reachable).
- Assay 42: Launch triggers a real `workflow_89` DAG run; watch it succeed in `/airflow`; output lands in `airflow-workspace`.
- Assay 43: Launch opens `/tool-view?assay=43`, VolView bundle loads from the `tools` bucket, streams the `test_converted` NIfTI.
- Portal dataset pages show only the 3 measurements + 3 workflows + 4 tools; SEEK shows only Test Programme/Test Project; `/seek` search finds no pruned assets.
- Reboot test: `digitaltwins-platform.service` reconverges the stack.

### 8. Documentation + housekeeping
- Write `demo/DEPLOYMENT.md`: the full runbook as executed (bundle layout, new-secrets policy incl. the two fixed DB passwords, SSH-tunnel access, prune inventory with kept IDs/UUIDs, assay verification results, known leftovers: HAPI annotations, demo realm users, `workflow_1` staging-prefix quirk in the DAG). All secrets `<REDACTED>`. **Not committed** — lives only in the demo folder (outside the repo).
- Per AGENTS.md, sync the implementation plan/walkthrough artifacts (redacted) to `docs/artifacts/2026-10-06-HHMMSS-demo-airgap-deployment/` in the repo as work proceeds.

## Reused tooling (no new platform code)
`util/stage-dump.sh` (already run) · `util/portal-restore.sh` · `util/mount_src.sh`, `airgap.sh`, `install-apt-debs.sh`, `airgap_build_step2.yml`, `airgap_build_step3.yml` · `util/freeze_images.sh`, `build-apt-debs.sh` · `util/rm-seek-tree.sh`, `seek-user-report.sh`, `add-seek-project-member.sh`, `set-seek-password.sh`, `promote-seek-admin.sh` (via restore) · `gen-env.sh`/`gen-realm.sh` (via step 3). New items are only the three small helper scripts + runbook in `demo/scripts/`.

## Gaps the request missed (now covered)
1. `hapi.sql` missing from the dump (HAPI on shared Postgres) → step 1.
2. The `workflow_89` DAG embeds the live MinIO secret and isn't in git → sanitize + explicit sync (step 2) and unpause (step 6).
3. New DAGs boot paused → explicit unpause.
4. `AIRFLOW_DB_PASSWORD`/`KEYCLOAK_DB_PASSWORD` are effectively fixed by init SQL → documented exception to "all new secrets".
5. `localhost` issuer means LAN-IP access breaks login → SSH-tunnel access model documented.
6. `digitaltwins` DB and MinIO hold data beyond SEEK's tree → dedicated DB/bucket prune, not just `rm-seek-tree.sh`.
7. Restored SEEK carries all user rows (old local password hashes) → review/reset step.
8. Assay-41 notebook needs `sparc-me` at runtime → confirmed PyPI reachable from the server (user), so no image change.

## Risks / notes
- `portal-restore.sh` MinIO mirror never deletes target-side objects — fine here (fresh target).
- Launching assay 42 during verification creates real DAG runs (not idempotent) — expected.
- If the portable drive is formatted exFAT/NTFS, symlinks/permissions in `clean_src` may not survive — use ext4.
- `rm-seek-tree.sh` cascade behaviour for non-ISA assets is unverified upstream — that's exactly what the orphan sweep covers; sweep runs dry-run-style (report first, then destroy).
