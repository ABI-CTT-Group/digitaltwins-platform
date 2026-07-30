# Productize deployment: template-driven config, consolidated DB, importable realm, reproducible airgap buildout

Branch: `env-config-generation` → `main` · 37 commits · 43 files · +6336 / −193

## Summary

Turns the platform from a hand-configured, multi-database deployment into a
reproducible one that can be stood up (including fully airgapped) from a single
set of templated inputs. Five related changes:

1. **Template-driven `.env`** — one place to set host inputs + secrets; `.env`
   is generated, not hand-edited.
2. **Database consolidation** — Keycloak and HAPI move off their own Postgres
   instances onto the shared Postgres.
3. **Keycloak realm as a template + custom login theme** — the realm imports on
   first boot from a committed, `envsubst`-rendered template.
4. **Airgap buildout tooling** (`util/`) — Ansible playbooks + scripts that
   deploy the whole stack onto a fresh (optionally airgapped) VM.
5. **Data migration tooling** — read-only source dump + target restore to move a
   running instance's data between boxes.

Verified live: deployed on the portal box over HTTPS with Keycloak login,
consolidated single Postgres, and a full data migration from staging
(SEEK/HAPI/MinIO/DICOM) restored and verified.

---

## 1. Template-driven config generation (`7a31c06`)

**Why.** `.env` held secrets, per-host values, and derived values all mixed
together and edited by hand — error-prone and not reproducible.

**How.** `.env.template` now carries only `${VAR}` placeholders. An operator
fills in two small files — `env` (non-secret host inputs: `PLATFORM_DOMAIN`,
`PLATFORM_PROTOCOL`, …) and `secrets.env` (all passwords/keys) — and
`util/gen-env.sh` renders `.env` from them, deriving `NGINX_MODE` / `SSL` /
`AIRFLOW_UID` from the protocol. The four Keycloak/auth URLs are derived from
`${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}` so they can't drift apart. The
generator fails loudly on any unset/empty placeholder. `env`/`secrets.env` are
git-ignored; `env.template` / `secrets.env.template` are the starters.

## 2. Database consolidation (`0abbc8e`)

**Why.** Keycloak ran on embedded H2 and HAPI on its own `postgres:13`, so a
deployment ran three database engines.

**How.** Keycloak now uses the shared Postgres (`KC_DB=postgres`, `start` +
`--http-enabled`, honouring `KC_HOSTNAME_STRICT`); HAPI points at the shared
Postgres via `SPRING_DATASOURCE_*`, and its dedicated `postgres:13` service +
volume are removed. `services/postgres/{keycloak_init.sql,hapi_init.sql}` create
the role/database on first boot. End state: one `postgres:16` serving
digitaltwins + airflow + keycloak + hapi, plus MySQL for SEEK only.

## 3. Keycloak realm template + login theme (`fe84e58`)

**Why.** The platform shipped no realm — Keycloak had to be configured by hand
or by importing an ad-hoc export.

**How.** `services/keycloak/digitaltwins-realm.json.template` is a committed
realm rendered by `util/gen-realm.sh`, which `envsubst`s **only** the platform's
own vars (domain/protocol, `KC_SSL_REQUIRED`, the OIDC client secrets, realm
admin password) and preserves Keycloak's own `${...}` tokens. Output goes to the
git-ignored `import/` dir; Keycloak imports it on first boot only. Adds the
custom `digitaltwins-login-theme` (mounted read-only into Keycloak).

## 4. Airgap buildout tooling (`607f395` … `cc11557`)

**Why.** Replaces the old `main_buildout` `buildout/` tree with tooling that
fits the new template-driven, single-gateway architecture.

**How.** In `util/`:
- `airgap_build_step2.yml` (Docker from static tarballs) and
  `airgap_build_step3.yml` (app deploy) Ansible playbooks; `mount_src.sh`,
  `airgap.sh`/`unairgap.sh` shell helpers for steps 0–1.
- `step3` renders `.env` and the realm via the `gen-*.sh` scripts, installs the
  gateway TLS cert, loads the frozen images **or** builds from source
  (`-e load_frozen_images=false`), bootstraps SEEK (admin/features/API token,
  written back to `secrets.env`), and precompiles SEEK's `/seek` assets.
- `freeze_images.sh` produces the airgap image bundle (union of compose-declared
  and actually-used images, so one-shots and the jupyter singleuser build are
  captured).
- `README.md` — full install runbook, gateway proxy-route table (with which
  services are Keycloak-authed), and the data-transfer procedure.
- `step3` excludes `services/airflow/dags/` from its code sync so
  developer-managed DAGs are never clobbered on redeploy.

## 5. Data migration tooling (`493b3a3`, `9f98c68`)

**Why.** Moving a live instance's data to a new box, across layout differences
(Keycloak H2-vs-Postgres, HAPI own-vs-shared Postgres).

**How.** `stage-dump.sh` (read-only source dump → `/tmp`), `portal-restore.sh`
(destructive target restore, confirmation-gated), `sync-dags.sh` (DAGs, kept
separate from the repo). Uses logical dumps / object mirrors, not raw volume
copies, so it survives the layout differences; credentials are read from the
containers' env so the two boxes need not share passwords.

---

## Testing / verification

- Clean rebuild on the portal box: all services healthy on one `postgres:16`
  (no pg13/H2), gateway HTTPS, realm imported + custom theme, portal→Keycloak
  login succeeds in a clean browser.
- Connected build path (`load_frozen_images=false`) and the frozen-archive path
  both exercised; `freeze_images.sh` produced a complete 25-image bundle.
- Full staging→portal data migration executed and verified: SEEK catalogue (5
  programmes / 10 projects), HAPI (31 resources), Orthanc DICOM (file-identical),
  MinIO (~4700 objects across buckets).

## Notes for reviewers

- **Not covered by the migration tooling:** Keycloak (H2→Postgres can't be
  DB-copied — do a realm export/import) and Airflow runtime metadata.
- **Secrets hygiene:** two internal Orthanc secrets that had been hardcoded in
  the tracked template were rotated; `secrets.env`/`env` are git-ignored.
- **Size / optional split:** this branch spans five themes. If a smaller review
  surface is preferred, it can be split into stacked MRs in this order —
  (1) config generation, (2) DB consolidation, (3) realm + theme, (4) buildout,
  (5) migration tooling — since each builds on the previous.
