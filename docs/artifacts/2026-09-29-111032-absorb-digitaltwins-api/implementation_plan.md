# Implementation Plan: Absorb `digitaltwins-api` Submodule

**Date:** 2026-09-29  
**Branch:** `chore/absorb-digitaltwins-api` (off `main`)  
**Scope:** `digitaltwins-api` only (portal to follow separately)

---

## Decisions Captured

| Decision | Choice |
|---|---|
| Final path | `services/api/` (submodule contents moved up one level) |
| History strategy | Rewrite with `git filter-repo --to-subdirectory-filter services/api/` |
| Branches to import | `main` only |
| Working branch | `chore/absorb-digitaltwins-api` off `main` |
| Remote repo fate | Keep open; just remove from `.gitmodules` |
| Docker/CI updates | Yes — update `docker-compose.yml` and any path references |

---

## Pre-conditions

- [ ] Local `main` is up to date with `origin/main` (merged PR is already in)
- [ ] `git filter-repo` is installed (`pip install git-filter-repo` if not)
- [ ] No uncommitted changes in either repo

---

## Steps

### 1. Create the working branch

```bash
git checkout main
git pull origin main
git checkout -b chore/absorb-digitaltwins-api
```
✅ **Verify:** `git branch` shows `chore/absorb-digitaltwins-api` as current.

---

### 2. Prepare a rewritten clone of the submodule

We need a temporary copy of the submodule's history with every file path prefixed by `services/api/`.

```bash
# Clone a clean, standalone copy of the submodule
git clone --no-local /home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api /tmp/digitaltwins-api-prep

# Rewrite history: prefix all paths with services/api/
cd /tmp/digitaltwins-api-prep
git filter-repo --to-subdirectory-filter services/api/ --force
```

> `--to-subdirectory-filter services/api/` rewrites every commit so that files that
> were at `app/` in the submodule appear as `services/api/app/` in the monorepo history.

✅ **Verify:** `git log --oneline -3` still shows commits; `git ls-files | head -5` shows paths starting with `services/api/`.

---

### 3. Add the prepared clone as a remote in the monorepo

```bash
cd /home/clin864/Projects/digitaltwins-platform
git remote add api-import /tmp/digitaltwins-api-prep
git fetch api-import
```

✅ **Verify:** `git remote -v` shows `api-import`.

---

### 4. Merge the rewritten history (allowing unrelated histories)

```bash
git merge api-import/main --allow-unrelated-histories -m "chore: absorb digitaltwins-api submodule history into services/api/"
```

> This gives us a single merge commit that grafts the full submodule history into the monorepo DAG.
> Any conflicts here are real conflicts between files that existed in both repos at the same path —
> resolve them manually if they occur.

✅ **Verify:** `git log --oneline -5` shows the merge commit; `ls services/api/` shows the API source files.

---

### 5. Remove the submodule

```bash
# Deinit and remove the submodule tracking
git submodule deinit -f services/api/digitaltwins-api
git rm -f services/api/digitaltwins-api
rm -rf .git/modules/services/api/digitaltwins-api

# Remove the entry from .gitmodules
# (Edit .gitmodules to delete the [submodule "services/api/digitaltwins-api"] block)
```

✅ **Verify:** `.gitmodules` no longer contains `digitaltwins-api`; `ls services/api/` shows the absorbed files directly (not a submodule pointer).

---

### 6. Update `docker-compose.yml`

Current references to update:

```yaml
# line 83 — was:
- services/api/digitaltwins-api/docker-compose.yml
# becomes:
- services/api/docker-compose.yml

# line 84 — was:
project_directory: services/api/digitaltwins-api
# becomes:
project_directory: services/api
```

✅ **Verify:** `docker compose config` resolves without errors.

---

### 7. Scan and update remaining path references

The following files reference `services/api/digitaltwins-api` or the old submodule path and should be updated:

| File | Action |
|---|---|
| `docker-compose.yml` | Updated in step 6 |
| `util/sync-runtime.sh` | Check and update any path references |
| `util/BUILD-FULL-SYSTEM.md` | Update doc references |
| `util/INSTALL-BUNDLE.md` | Update doc references |
| `README.md` | Update any path references |

Run a sweep to catch anything missed:
```bash
grep -rn "services/api/digitaltwins-api" . --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="*.txt" | grep -v ".git/"
```

✅ **Verify:** No remaining references to `services/api/digitaltwins-api`.

---

### 8. Clean up the temp remote and clone

```bash
git remote remove api-import
rm -rf /tmp/digitaltwins-api-prep
```

---

### 9. Stage and commit the submodule removal + path updates

```bash
git add .gitmodules
git add docker-compose.yml
git add <any other updated files>
git commit -m "chore(submodules): absorb digitaltwins-api into services/api/

- Removes services/api/digitaltwins-api submodule
- Merges full commit history rewritten under services/api/
- Updates docker-compose.yml project_directory and include paths
- Updates doc and script references to the old submodule path"
```

---

### 10. Smoke-test the compose stack

```bash
docker compose config   # validates compose file resolution
docker compose build digitaltwins-api  # builds the API image from new path
```

✅ **Verify:** No build errors; image builds successfully.

---

### 11. Sync artifact to `docs/artifacts/`

```bash
mkdir -p docs/artifacts/2026-09-29-HHMMSS-absorb-digitaltwins-api
cp <this plan file> docs/artifacts/2026-09-29-HHMMSS-absorb-digitaltwins-api/implementation_plan.md
git add docs/artifacts/
git commit -m "docs(artifacts): sync absorb-digitaltwins-api implementation plan"
```

---

### 12. Push and open PR

```bash
git push -u origin chore/absorb-digitaltwins-api
```

Open PR: `chore/absorb-digitaltwins-api` → `main`

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Merge conflicts at step 4 | Resolve manually; most likely in `.gitignore`, `README.md`, or `docker-compose.yml` since both repos had them |
| `filter-repo` not installed | `pip install git-filter-repo` before starting |
| Old submodule path hard-coded in runtime scripts | Step 7 sweep catches these |
| `git submodule deinit` leaves stale `.git/modules` cache | `rm -rf .git/modules/services/api/digitaltwins-api` explicitly clears it |

---

## Out of Scope (portal submodule — next task)

The same process will be repeated for `services/portal/DigitalTWINS-Portal` after this PR is merged.
