# Remove the stale env template in services/api/

## Context

`services/api/.env.template` is an old copy of the root `.env.template`, and the two have drifted apart.
`docs/codemap.md` already lists it as inactive. Nothing reads it:

- The platform renders only the root `.env` (`util/gen-env.sh`).
- The API image excludes `.env` (`services/api/.dockerignore`).
- No guide tells anyone to copy the template.
- `load_dotenv()` in `src/digitaltwins/settings.py` searches upward from the package. In an editable install it would
  load a `services/api/.env` if one existed; otherwise it falls through to the repository root `.env`. No documented
  workflow creates `services/api/.env`.

It is also misleading and unsafe:

- Its header calls it "the single source of truth".
- It lacks 17 keys of the root template.
- It keeps `KEYCLOAK_VERIFY_SSL=false`.
- It holds literal values for `KC_BOOTSTRAP_ADMIN_PASSWORD`, `POSTGRES_PASSWORD`, `JUPYTERHUB_CLIENT_SECRET`,
  `ORTHANC_KEYCLOAK_CLIENT_SECRET`, `ORTHANC_AUTH_SECRET_KEY` and `ORTHANC_AUTH_SERVICE_PASSWORD`, where the root
  template uses `${...}` placeholders. The two `ORTHANC_AUTH_*` values are the ones once in the root template, which
  `docs/production.md` records as rotated.
- `gitleaks detect --no-git` reports a finding in this file.

The repository is public. Removing the file stops it being copied, but the values remain in git history, so each
host's operator must confirm none of them is in use. That check is out of this change: the user runs it on the hosts.

No ADR: this removes an unused file and follows the existing rule of one `.env`, at the root.

## Steps

1. `git rm services/api/.env.template`.
   → `git grep -n "api/.env.template"` finds only `docs/codemap.md` and `docs/plans/`.
2. `docs/codemap.md`: remove the file's row from the inactive-files table.
3. `docs/production.md` (Secrets handling): note that the API's copy of the template also held those values and is
   removed.
4. Verify:
   - `make docs-check` passes.
   - `docker compose config -q` passes.
   - `make test-api` passes.
   - gitleaks finds nothing in the plan folder.
   - No secret value appears in the plan, the commit messages or the PR; variable names only.
5. Sync the plan and tasks. Commit only when asked.

## Outcome: where implementation differed from the plan

- One of the removed values, the Orthanc Keycloak client secret, is also the fallback default of
  `ORTHANC_KEYCLOAK_CLIENT_SECRET` in `services/pacs/docker-compose.yml` and
  `services/pacs_pretend_external/docker-compose.yml`. `util/gen-env.sh` refuses to render an unset or empty variable,
  so the fallback is unused on a rendered deployment. Changing it would recreate the Orthanc containers, so it is
  recorded in `docs/future_refactoring.md` ("Default credentials") instead.
