# Implementation Plan: Absorb `DigitalTWINS-Portal` Submodule

**Date:** 2026-09-29  
**Branch:** `chore/absorb-portal` (off `main`, after API PR #321 is merged)  
**Scope:** `DigitalTWINS-Portal` portal submodule only

---

## Decisions Captured

| Decision | Choice |
|---|---|
| Final path | `services/portal/` (submodule contents moved up one level, removing `DigitalTWINS-Portal/`) |
| History strategy | Rewrite with `git filter-repo --to-subdirectory-filter services/portal/` |
| Branches to import | `main` only |
| Working branch | `chore/absorb-portal` off `main` |
| Remote repo fate | Keep open; just remove from `.gitmodules` |
| Docker/CI updates | Yes — update `docker-compose.yml` references |

> **Note:** The `.gitkeep` file at `services/portal/.gitkeep` will be removed as part of this work — it was only there to track the otherwise-empty directory.

---

## Pre-conditions

- [ ] Local `main` pulled up to date (API PR #321 already merged)
- [ ] `git filter-repo` installed (already done from API task)
- [ ] No uncommitted changes

---

## Steps

### 1. Create the working branch

```bash
git checkout main
git pull origin main
git checkout -b chore/absorb-portal
```
✅ **Verify:** `git branch` shows `chore/absorb-portal` as current.

---

### 2. Prepare a rewritten clone of the portal submodule

```bash
git clone --no-local /home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal /tmp/portal-prep

cd /tmp/portal-prep
git filter-repo --to-subdirectory-filter services/portal/ --force
```

✅ **Verify:** `git ls-files | head -5` shows paths starting with `services/portal/`.

---

### 3. Add as a remote and fetch

```bash
cd /home/clin864/Projects/digitaltwins-platform
git remote add portal-import /tmp/portal-prep
git fetch portal-import
```

✅ **Verify:** `git remote -v` shows `portal-import`.

---

### 4. Merge the rewritten history

```bash
git merge portal-import/main --allow-unrelated-histories \
  -m "chore: absorb DigitalTWINS-Portal submodule history into services/portal/"
```

✅ **Verify:** `git log --oneline -3` shows the merge commit; `ls services/portal/` shows portal source files.

---

### 5. Remove the submodule

```bash
git submodule deinit -f services/portal/DigitalTWINS-Portal
git rm -f services/portal/DigitalTWINS-Portal
rm -rf .git/modules/services/portal/DigitalTWINS-Portal
```

Then remove the `.gitkeep` (no longer needed):

```bash
git rm services/portal/.gitkeep
```

✅ **Verify:** `.gitmodules` no longer contains `DigitalTWINS-Portal`; `ls services/portal/` shows absorbed files directly.

---

### 6. Update `docker-compose.yml`

Current references to update (lines 20 and 41):

```yaml
# was:
file: ./services/portal/DigitalTWINS-Portal/docker-compose.yml
# becomes:
file: ./services/portal/docker-compose.yml
```

Both `portal-backend` and `portal-frontend` extends blocks reference this path.

✅ **Verify:** `docker compose config` resolves without errors.

---

### 7. Sweep for remaining path references

```bash
grep -rn "services/portal/DigitalTWINS-Portal" . \
  --include="*.yml" --include="*.yaml" --include="*.sh" \
  --include="*.md" --include="*.txt" | grep -v ".git/"
```

✅ **Verify:** No remaining references to `services/portal/DigitalTWINS-Portal`.

---

### 8. Clean up temp remote and clone

```bash
git remote remove portal-import
rm -rf /tmp/portal-prep
```

---

### 9. Commit

```bash
git add .gitmodules docker-compose.yml services/portal/.gitkeep services/portal/DigitalTWINS-Portal
git add <any other updated files>
git commit -m "chore(submodules): absorb DigitalTWINS-Portal into services/portal/

- Removes services/portal/DigitalTWINS-Portal submodule
- Merges full commit history rewritten under services/portal/ (234 commits)
- Updates docker-compose.yml extends file paths for portal-backend and portal-frontend
- Removes services/portal/.gitkeep (directory no longer empty)"
```

---

### 10. Smoke-test

```bash
docker compose config   # validates compose file resolution
docker compose build portal-backend portal-frontend  # verify builds from new path
```

✅ **Verify:** No build errors.

---

### 11. Sync artifact and commit

```bash
mkdir -p docs/artifacts/$(date +%Y-%m-%d-%H%M%S)-absorb-portal
cp <this plan> docs/artifacts/.../implementation_plan.md
git add docs/artifacts/
git commit -m "docs(artifacts): sync absorb-portal implementation plan"
```

---

### 12. Push and open PR

```bash
git push -u origin chore/absorb-portal
```

Open PR: `chore/absorb-portal` → `main`

---

## Differences from API Absorption

| Aspect | API | Portal |
|---|---|---|
| Submodule path | `services/api/digitaltwins-api/` | `services/portal/DigitalTWINS-Portal/` |
| Target path | `services/api/` | `services/portal/` |
| Commits on main | 658 | 234 |
| Extra cleanup | — | Remove `services/portal/.gitkeep` |
| Compose references | 1 service block | 2 service blocks (`portal-backend`, `portal-frontend`) |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Merge conflicts | Resolve manually; likely candidates are `.gitignore`, `README.md` |
| `.gitkeep` conflict | If merge brings in a file at that exact path, delete it post-merge |
| Compose path references missed | Step 7 grep sweep catches these |
