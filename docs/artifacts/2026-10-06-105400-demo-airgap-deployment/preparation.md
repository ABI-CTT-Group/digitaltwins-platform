# Demo deployment — source-box preparation (LOCAL ONLY — do not copy to the drive)

Companion to `DEPLOYMENT.md` (which travels). This file records how the drive
contents were produced on the dev box, what was removed, and the evidence that no
local-only data or secrets went onto the drive.

**Copy to the drive:** `install_src/` and `DEPLOYMENT.md` only. Keep `PREPARATION.md`,
`LEDGER.md`, `scripts/` and `.work/` here — they reference local paths, the backup, and
(in `.work/`) local-only strings and secrets used by the leak scan.

## Backup (source box, pristine)

`/home/clin864/Projects/archive/digitaltwins-platform/20261006/` — stage-dump (all DBs,
SEEK, MinIO, jupyter volumes, Orthanc) + `hapi.sql` + `keycloak.sql` + `config-backup/`
(live DAGs, rendered realm) + old `env`/`secrets.env`/`.env`. Never pruned; images excluded
(rebuildable from source).

## Pipeline (re-runnable, in order)

All scripts in `demo/scripts/`; `install_src/dtwins-migrate/` is the output.

1. `rsync` the backup → `install_src/dtwins-migrate/` (excluding Orthanc tars).
2. `build-pruned-digitaltwins.sh <backup> <migrate>` — throwaway postgres:16: load, apply
   `prune-digitaltwins.sql` (10 datasets, assays 41/42/43), drop `upload_session`, re-dump.
3. `build-pruned-seek.sh <backup> <migrate> demo/.work` — throwaway MySQL + LDH sandbox
   running `seek-prune.rb`:
   - removes all other programmes/projects/ISA trees and every asset outside project 12,
     plus the stale SOP 38;
   - removes people not needed by kept content (only admin1 remains) and unused
     institutions;
   - generic sweep of dangling polymorphic rows (orphaned content blobs and git repos that
     SEEK's own destroy leaves behind);
   - scrubs tokens, sessions, OAuth, logs, encrypted settings and password hashes;
   - rebuilds the auth lookup tables;
   - re-dumps, then rebuilds the filestore from **only referenced files** — never
     `secret_key_base`, `attr_encrypted/`, `tmp/` (bioschemas dumps of all local
     people/projects) or `rdf/`.
4. `prune-dump.sh <migrate>` (idempotent):
   - drops old env/secrets, `keycloak.sql`, `hapi.sql`, Orthanc, `models/` and the
     out-of-scope MinIO objects;
   - scrubs the old MinIO secret fallback from 5 ingested DAG/tool code copies;
   - drops the stale pending `measurements` row (pruned `example_sds_dicom`) from the
     plugin registry, then VACUUMs;
   - repacks the jupyter volume to `assay_41/`.
5. `gen-new-secrets.sh install_src/data`:
   - all-new values, verified disjoint from the old ones;
   - the MinIO ROOT/SERVER pair is a single shared value.
6. Source: plain `git archive` export of `dev_chinchien` (+ ldh submodule) into
   `install_src/clean_src/`, with **no `.git`**. The 3 docs that contain the old admin
   password were redacted (see Security findings).
7. Images:
   - portal-backend, portal-frontend and api were **rebuilt from the clean export**. The
     working-tree builds had baked in untracked local files: `app.log`, a local
     `plugin_registry.db` and `tmp/upload_*` in portal-backend; build leftovers named
     after pruned items in the frontend context.
   - airflow was rebuilt without nnUNet.
   - Then `util/freeze_images.sh`.

## Leak-scan procedure

Forbidden lists (in `.work/`, local only):

- `forbidden-seek.txt` — every removed SEEK title, description, name and email (from
  `seek-prune.rb`).
- `forbidden-datasets.txt` — pruned dataset names and UUIDs.
- `old-true-secrets.txt` — every old `*PASSWORD|SECRET|KEY|TOKEN|FERNET|CRYPT*` value.

Scanned:

- all of `install_src/` except the image archive;
- the decompressed history of every SEEK git repo;
- the layers of the rebuilt images.

Residual matches were reviewed by hand. Each is kept content or generic vocabulary,
such as "Breast" in the kept Duke breast-MRI dataset, or SEEK's seeded "Modelling"
assay-type terms.

## Security findings (action for you — not fixed here)

- **The current local admin password (`PLATFORM_ADMIN_PASSWORD` = `AIRFLOW_PASSWORD`)
  is committed in the public GitHub repo**, in:
  - `docs/artifacts/2026-08-26-144900-minio-credentials/{implementation_plan,walkthrough}.md`
  - `docs/artifacts/2026-09-04-144800-admin-identity-update/walkthrough.md`

  They were introduced 2026-09-04 (commit 5e303411) and are still in history.
  Recommendation: rotate the local admin password, and consider redacting those files
  (history rewrite is your call). The demo deployment does not use it.
- The old MinIO secret was a hardcoded fallback in the gitignored local DAG files and in
  ingested workflow-dataset copies. It was scrubbed from everything on the drive, but it
  is still in the local DAGs folder.
