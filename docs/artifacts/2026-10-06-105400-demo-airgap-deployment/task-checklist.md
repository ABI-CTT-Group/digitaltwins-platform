# Execution ledger — plan: /home/clin864/.claude/plans/i-want-to-do-structured-chipmunk.md
# Demo airgap deployment — source-box work. Steps 4–7 of the plan run on the remote server (see DEPLOYMENT.md).

Pre-flight: no shared code interfaces (ops plan). Constraint found at start: only 29 GB free on /home; frozen image archive (~20 GB) + pruned dump copy (~10 GB) must be staged directly on the portable drive, not under demo/install_src. Small bundle pieces staged locally.

## Checklist (source box)
- [x] 1a. pg_dump hapi -> 20261006/hapi.sql
- [x] 1b. Backup config: keycloak DB dump, rendered realm, live DAGs copy -> 20261006/
- [x] Sync artifacts to docs/artifacts/
- [x] 2a. scripts/prune-dump.sh written (runs against migrate copy on the drive)
- [x] 2b. dags-payload/ sanitized (no MinIO secret fallback) + live worker env verified
- [x] 2c. scripts/prune-digitaltwins.sql written
- [x] 2d. scripts/seek-orphan-sweep.rb written
- [x] Sync artifacts to docs/artifacts/
- [x] 3a. clean_src recursive clone
- [x] 3b. apt-debs, docker tgz, compose binary, ansible wheels fetched
- [x] 3c. data/env + data/secrets.env generated (new values)
- [x] 3d. freeze_images.sh -> install_src (6.3 GB, 25 images, slim airflow)
- [x] 3e. pruned migrate copy staged in install_src/dtwins-migrate (user copies demo/ to drive)
- [x] 8a. DEPLOYMENT.md written (secrets redacted, gitleaks-checked)
- [x] 8b. Final artifact sync to docs/artifacts/

## Log
- Step 1 complete: hapi.sql (58 tables) + keycloak.sql (88 tables) dumped; config-backup/ (dags + rendered realm) archived into 20261006/.
- Step 2b complete: dags-payload/ built (workflow_image_conversion_test.py + tool/{__init__,download_samples,dicom_to_nifti,dicom_to_nrrd}); hardcoded MinIO secret fallback replaced with fail-loud os.environ lookup; py_compile OK; verified all airflow services carry MINIO_SECRET_KEY env.
- Step 2c complete: prune-digitaltwins.sql VERIFIED against the real dump in a throwaway postgres:16 container -> exactly 10 datasets + assays 41/42/43 remain, inputs/outputs intact.
- Step 2d complete: seek-orphan-sweep.sh dry-run on live box: 124 orphans identified incl. stale SOP 38.
- Ruling: tar --delete corrupts the jupyter volume tar (core dumps, left assay_32) -> prune-dump.sh repacks via root alpine extract/retar instead. Cost if wrong: jupyter volume perms; mitigated by uid-preserving root repack.
- Ruling: sweep ships as seek-orphan-sweep.sh (bash heredoc, house style of rm-seek-tree.sh) instead of a bare .rb. Cost if wrong: none (equivalent).
- Ruling: Template/FileTemplate excluded from sweep - the 4 "ISA minimal starter template" rows are SEEK seed data, not user content. Cost if wrong: 4 stray template rows visible to admins.
- Constraint: only 29 GB free on /home -> frozen image archive (~20 GB) goes directly to the portable drive; pruned migrate copy (~10 GB) staged locally.
- Step 2a complete: prune-dump.sh run against the migrate copy -> 1.3 GB set, MinIO keep-set exact (3 measurements, 4 tools, 3 workflows + 3 build dirs, volview tool-build), jupyter tar repacked to assay_41 only (155 MB, jovyan uid preserved), idempotent re-run verified.
- Ruling: prune-dump.sh had two pipefail+grep -q SIGPIPE bugs that silently skipped the jupyter repack; fixed with grep -c. Cost if wrong: none now (verified by re-run + tar listing).
- Step 3a complete: clean_src recursive clone at e4393e64 (main) + ldh submodule b4e2b92b.
- Step 3b complete: apt-debs (106 debs + Packages + INSTALL.list), docker-29.4.0.tgz, compose v5.1.2, ansible-packages.tar.gz.
- Step 3c complete: data/env (http/localhost) + data/secrets.env generated via gen-new-secrets.sh; all keys non-empty; verified no old secret value reused; secrets never printed.
- Verified on live SEEK: admin1 (sub 1afb2774...) is member + project_administrator of project 12 + server admin -> target step 5d is verify-only.
- Image archive sizing: 24 unique image IDs, 162 GB tag-sum; airflow apiserver/scheduler share layers but worker differs -> archive est. 25-35 GB compressed. Must be written DIRECTLY to the portable drive (27 GB free locally).
- Step 8a complete: DEPLOYMENT.md written; gitleaks: no leaks in DEPLOYMENT.md, scripts/, docs/artifacts copy.
- User mid-flight decisions: demo/ is the drive staging area (no mount here); docker build cache pruned (-70 GB, approved); nnUNet venv commented out of services/airflow/Dockerfile by user -> airflow images rebuilt WITHOUT nnUNet (worker 23.4 GB -> 4.3 GB), airflow services RESTARTED and verified healthy (workflow_89 unpaused, cwl_venv present, nnunet_venv gone), freeze redone: 6.3 GB archive, 25 images incl. alpine+mc helpers.
- Ruling: clean_src checked out dev_chinchien (aff29813) instead of main - the gui-assay launch code (volviewParams.ts etc.) is not on main yet and the live images were built from dev_chinchien. Cost if wrong: none for the target (it loads frozen images); keeps source/image parity.
- Note: source box's Dockerfile nnUNet comment-out is an uncommitted working-tree edit; re-enable + rebuild when local workflow_39/nnUNet testing resumes (documented in DEPLOYMENT.md §8).
- Final review (fresh-context subagent): verdict fix-first. FIXED: (1) CRITICAL MINIO_SERVER_SECRET_KEY must equal MINIO_ROOT_PASSWORD -> gen-new-secrets.sh emits one shared value, secrets regenerated + verified match, coupling documented in DEPLOYMENT.md §0 + saved to memory; (2) rsync added to apt-debs (114 debs, INSTALL.list updated); (3) runbook mount step chowns /mnt/install_src/data (drive preserves build-box uid); (4) runbook notes -K for password-sudo; (5) §5a shows rm-seek-tree dry-run loop before -y. MOOT: ".partial archive" finding — freeze completed before fixes (6.3 GB final file verified). Final: minor (deferred): frozen archive includes Orthanc/orthanc-auth images though PACS data dropped — compose still runs those services, images required.
- Final review: fixes verified by re-running gen-new-secrets.sh (MINIO pair MATCHES, all keys non-empty, no old-value reuse) and rebuilt apt repo (grep rsync INSTALL.list OK).

## Rework 2 — keep local-only data/secrets off the drive (user request)
User decisions: drop HAPI; ship plugins; prune SEEK locally + strip unneeded SEEK people; drive gets install_src/ + DEPLOYMENT.md only.
- Platform DB pruned LOCALLY (build-pruned-digitaltwins.sh: throwaway pg16 -> 10 datasets, assays 41/42/43; upload_session emptied).
- SEEK pruned LOCALLY (build-pruned-seek.sh + seek-prune.rb in throwaway MySQL+LDH sandbox): programme 7/project 12/1 inv/1 study/assays 41-43, workflows 87-89,94-97, SOPs 37,39,40; people -> admin1 only; 1 institution; 13,257 dangling polymorphic rows swept (incl. 51 orphan content blobs + 22 orphan git repos SEEK's destroy leaves); tokens/sessions/oauth/logs/encrypted settings/password hashes scrubbed; filestore rebuilt from referenced files only (99 files) — secret_key_base, attr_encrypted key, tmp bioschemas dumps of all local people/projects, rdf cache NOT shipped.
- Ruling: LDH image default database.yml is sqlite; one-shot containers bypass the entrypoint swap -> wrapper copies database.docker.mysql.yml first. (First runs hit empty sqlite; admin-identity guard aborted them harmlessly.)
- prune-dump.sh: drops hapi.sql; scrubs OLD MinIO secret from 5 ingested DAG/tool code copies in MinIO; drops stale pending measurements row (pruned example_sds_dicom) from plugin_registry.db + VACUUM; fixed a pipefail/grep -l abort-on-rerun bug.
- Ruling: clean_src replaced by a git-free `git archive` export (+ldh submodule, SOURCE_COMMIT file) with 3 docs redacted — the OLD LOCAL ADMIN PASSWORD is committed in the public repo (docs/artifacts 2026-08-26 minio-credentials, 2026-09-04 admin-identity-update; commit 5e303411). Not fixed in the repo (history rewrite = user decision); reported.
- Ruling: portal-backend/portal-frontend/api images rebuilt FROM THE CLEAN EXPORT — working-tree builds had baked untracked local files (backend: app.log 12 MB, local plugin_registry.db, tmp/upload_*; no .dockerignore). Live portal-backend/frontend/api recreated on the clean images (healthy, portal 200, /data registry intact). Archive re-frozen: 6.3 GB.
- Leak scan (final): 0 old real secrets in any drive file or any locally built image filesystem (7 images exported+grepped); removed-content matches all reviewed = kept content (Duke breast-MRI DICOM headers, kept notebook heading, kept workflow/SOP filenames, SEEK seed vocab, ITK DICOM dictionary) or committed public frontend assets (public/eps).
- DEPLOYMENT.md rewritten server-only (no local paths/inventory/backup); local details moved to PREPARATION.md (not shipped). Target SEEK steps reduced to set-seek-password (login admin1186) + reindex + report.
- Removed obsolete: install_src/demo-scripts/, scripts/seek-orphan-sweep.sh (superseded by seek-prune.rb). Working secret lists in .work/ deleted after the scan.
- Simplified DEPLOYMENT.md to 4 steps; post-install steps (restore, SEEK password+reindex, DAG copy/wait/unpause, report) moved into install_src/demo-setup.sh (bash -n + shellcheck clean; not executable here — target-only).
- DEPLOYMENT.md rewritten as a beginner guide (non-expert audience): prerequisites, lsblk drive discovery, per-step expected output/duration, SSH tunnel incl. Windows, troubleshooting table; admin notes collapsed.
- DEPLOYMENT.md: install files may arrive as portable drive, attached volume, or copied folder (symlink path added to step 1).
- DEPLOYMENT.md: added 'Your sudo password' section (BECOME = Ubuntu account sudo password, not SSH key passphrase; sudo -n check; press Enter if passwordless).
- DEPLOYMENT.md: disk requirement corrected 100 GB -> 60 GB (estimate ~50 GB: 8 files + 25-30 images + 2 data + 2 misc + 10 headroom; not measured on a fresh docker).
- Added DEPLOYMENT-DOMAIN.md (self-contained beginner guide for https + domain: env sed, cert option A IT / option B issue-cert.sh, openssl check, renewal, domain troubleshooting); DEPLOYMENT.md links to it; demo-setup.sh now prints the configured URL. Domain path NOT test-run.
- Domain step-6 verification: rendered .env/realm/minio-discovery for a sample domain in scratch via gen-env/gen-realm -> all https://<domain>, ssl mode, sslRequired external. Gateway alias = PLATFORM_DOMAIN handles in-container calls; those verify TLS -> internal-CA certs would break logins: added public-CA requirement (option A), step-6 preflight check, troubleshooting row. Scratch copy (contained secrets) deleted. Note: my first inspection mistakenly read the LIVE repo's localhost .env (wrong cwd) — corrected.
- Added install_src/set-domain.sh (switch data/env localhost<->domain; keeps env.localhost; secrets untouched; DNS + cert-match advisory checks; tested 6 cases in scratch incl. exact revert). DEPLOYMENT-DOMAIN.md steps 3/4 now use it. Shipped data/env remains localhost.
- 2026-10-06 Nectar test_demo (auckland, 30 GB root, domain demo-digitaltwins.abi-ctt-ctp.cloud.edu.au): step 6 hit 'No space left on device'. User attached 100 GB volume; I formatted /dev/vdb (verified blank), mounted at /var/lib/docker via fstab LABEL=dockerdata nofail, cleared the 19 GB of old images from the root disk (first attempt no-op'd: unprivileged glob expansion of sudo rm -rf /var/lib/docker/*), docker restarted. Root 18 GB free, volume 93 GB free; fstab verified. Next: user re-runs step 6.
