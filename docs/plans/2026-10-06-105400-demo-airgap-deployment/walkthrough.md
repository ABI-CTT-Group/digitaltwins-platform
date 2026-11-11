# Walkthrough — demo airgap deployment (install bundle preparation)

Date: 2026-10-06. Plan: `plan.md`. Execution record: `task-checklist.md`. Source-box
procedure: `preparation.md`. Scripts: `scripts/`.

## Goal

Ship a fresh, airgapped `http://localhost` deployment to a remote Ubuntu 24.04 server, with:

- all-new credentials;
- only the demo scope: SEEK Test Programme (7) → Test Project (12), and assays 41
  (notebook), 42 (script, DAG `workflow_89`) and 43 (gui, VolView), all launchable from
  `study-dashboard?trail=7,12,10,11`;
- **no data or secrets that exist only on the source deployment** on the drive or the
  server.

The operator guide (`DEPLOYMENT.md`) and its drive staging area live outside the repo,
by decision.

## Approach: prune locally, ship only the result

The SEEK IDs, dataset UUIDs, DAG id, jupyter folder and portal build rows are all
interlocked, so the demo scope is carried over by **restore** rather than re-registration.
The design changed during the work:

1. **Plan-time:** restore everything on the target, then prune there.
2. **Final:** that design would have put foreign data (other projects, all SEEK users,
   old password hashes) on the drive and in the target's databases before deletion.
   Every prune now runs **on the source box in throwaway containers**, and only the
   pruned result is written to the drive.

## What the drive contains (`install_src/`, ~7.3 GB)

| Item | How it was produced |
|---|---|
| `clean_src/digitaltwins-platform/` | `git archive` export of `dev_chinchien` + the ldh submodule, with **no `.git`** and a `SOURCE_COMMIT` file. Three historical docs containing a credential were redacted in this copy, and the airflow worker's NVIDIA GPU reservation is commented out (the target has no GPU). |
| `data/env`, `data/secrets.env` | `gen-new-secrets.sh`: all-new values, verified disjoint from the old ones. |
| `digitaltwins-images-all.tar.gz` | 6.3 GB, 25 images (`util/freeze_images.sh`), after the rebuilds described below. |
| `airgap/apt-debs/`, docker/compose binaries, ansible wheels | `util/build-apt-debs.sh` (rsync added), static downloads. |
| `dtwins-migrate/` | the pruned data set, in `util/portal-restore.sh` format (below). |
| `dags-payload/` | the `workflow_89` DAG + `tool/` package, with the hardcoded MinIO secret fallback replaced by a fail-loud env lookup. |
| `demo-setup.sh` | one-shot post-install step (see Target flow). |

## The pruned data set (`dtwins-migrate/`)

- **Platform DB** — `build-pruned-digitaltwins.sh`: throwaway postgres:16 → `prune-digitaltwins.sql`
  (10 datasets: 3 measurements, 4 tools, 3 workflows; assays 41/42/43) → `upload_session`
  emptied → re-dumped with `--clean --if-exists`.
- **SEEK** — `build-pruned-seek.sh` + `seek-prune.rb` in a throwaway MySQL + LDH sandbox:
  - removes all other programmes/projects/ISA trees, every asset outside project 12, the
    stale SOP 38, people not needed by kept content (admin1 only remains) and unused
    institutions;
  - a **generic dangling-polymorphic sweep** deletes any `<x>_type/<x>_id` row whose target
    is gone. This caught 51 orphaned content blobs and 22 orphaned git repos that SEEK's own
    `destroy!` (and so `util/rm-seek-tree.sh`) leaves behind — 13,257 rows across 44 categories,
    all reviewed;
  - scrubs API tokens, sessions, OAuth tables, logs, encrypted settings and password hashes,
    then rebuilds the auth lookup tables;
  - **filestore rebuilt from referenced files only** (99 files): never `secret_key_base`,
    `attr_encrypted/`, `tmp/` (bioschemas dumps of every local person/project) or `rdf/`.
- **`prune-dump.sh`** (idempotent):
  - drops old env/secrets, `keycloak.sql`, `hapi.sql` (HAPI starts empty), the Orthanc
    tars, the `models/` bucket and out-of-scope MinIO objects;
  - scrubs the old MinIO secret from 5 ingested DAG/tool code copies stored in MinIO;
  - removes a stale pending measurement row (for a pruned dataset) from the plugin
    registry, then VACUUMs;
  - repacks admin1's jupyter volume to `assay_41/` only.
- Shipped as-is by decision: the plugin registry (1 plugin) and the gateway plugin
  configs (empty).

## Images

- The portal-backend and portal-frontend Dockerfiles `COPY .` with no `.dockerignore`, so
  working-tree builds had baked in untracked local files (`app.log`, a local
  `plugin_registry.db`, `tmp/upload_*`). **portal-backend, portal-frontend and api were
  rebuilt from the clean export.**
- The airflow images were rebuilt without the nnUNet venv (worker 23.4 GB → 4.3 GB).
- The live source containers were recreated on the rebuilt images and verified healthy.

## Target flow (`DEPLOYMENT.md`, written for non-experts)

1. Mount the drive at `/mnt/install_src` (portable drive, attached volume, or a symlinked
   copied folder).
2. `install-apt-debs.sh` + ansible wheels → `airgap_build_step2.yml` (docker) →
   `airgap_build_step3.yml` (platform; loads the frozen images).
3. `demo-setup.sh`:
   - `portal-restore.sh` (asks for `yes`);
   - `set-seek-password.sh admin1186` (admin1's SEEK login, set to the new admin
     password);
   - `rake seek:reindex_all`;
   - copies the DAG, waits for it to appear, then unpauses `workflow_89`;
   - prints `seek-user-report.sh`.
4. Browse via SSH tunnel and launch the three assays.

## Verification (source box)

- **Platform-DB prune** run in a throwaway container: report checked (10 datasets, 3
  assays `ready=t`).
- **SEEK sandbox result:** programme 7, project 12, 1 investigation, 1 study, assays
  41–43, workflows 87–89/94–97, SOPs 37/39/40, 1 person (admin1), 1 institution.
- **Leak scan** of everything bound for the drive. It used three forbidden lists: removed
  SEEK titles/names/emails, pruned dataset names/UUIDs, and old secret values.
  - Coverage: all of `install_src/` except the image archive; the decompressed history of
    every SEEK git repo; the filesystems of all 7 locally built images (exported and
    grepped).
  - Result: **0 old secret values anywhere**.
  - The remaining text matches were reviewed by hand. Each is kept content (the Duke
    breast-MRI DICOM headers, a kept notebook heading, kept workflow/SOP filenames), SEEK
    seed vocabulary, ITK's DICOM dictionary, or committed public frontend assets.
- **`gitleaks`:** clean on the guide, the scripts and this folder.
- **Fresh-context review (fix-first).** It caught that generated
  `MINIO_SERVER_SECRET_KEY` ≠ `MINIO_ROOT_PASSWORD`, which breaks every S3 client. Fixed:
  one shared value, documented. Also fixed: rsync added to the apt bundle, a drive-uid
  `chown`, `-K` for password-sudo, dry-run before destructive SEEK steps.
- **`demo-setup.sh`** is syntax-checked only. It needs a freshly installed target, so its
  first real run is on the server.

## Findings for the owner

- **A source-deployment credential was found in historical artifacts in this repo.** It
  was redacted in the shipped export and reported to the owner, with a recommendation to
  rotate it. The demo deployment does not use it.
- `MINIO_SERVER_SECRET_KEY` must equal `MINIO_ROOT_PASSWORD`. This is undocumented in
  `secrets.env.template`.
- The LDH image's default `config/database.yml` is sqlite; only its entrypoint swaps in
  MySQL. One-shot `rails runner` containers must copy `docker/database.docker.mysql.yml`
  first.
- `AIRFLOW_DB_PASSWORD` / `KEYCLOAK_DB_PASSWORD` are effectively fixed by the postgres
  init SQL.
- `services/airflow/docker-compose.yml` reserves an NVIDIA GPU for `airflow-worker`
  unconditionally. On a server without one, `docker compose up` fails with `could not
  select device driver "nvidia"`. This happened on the first real install. The demo
  bundle comments the reservation out; the repo still has it.

## Known leftovers (accepted)

- Demo realm users (`test1`, `test2`, `clinician`, `researcher`) are kept, by decision.
- `workflow_89` stages its inputs under `airflow-workspace/workflow_1/` (a hardcoded id
  in the DAG).
- Jupyter Download/Submit use the hub's default API token (upstream behaviour).
