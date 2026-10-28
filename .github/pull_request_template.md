## Description
What this change does and why.

## Related issue(s)
e.g. Closes #123

## Type of change
[feat / fix / docs / refactor / test / ci / chore] (the Conventional Commits type)

## How it was tested
- [ ] `make test` passes
- [ ] `make lint` (report-only) has no new findings
- Other testing, e.g. the deployment you tried it on (connected / airgapped, http / https):

## Checklist
- [ ] Docs updated (README, `docs/`, service READMEs) where behaviour changed
- [ ] `docs/codemap.md`, `util/SCRIPTS.md` or the service's `AGENTS.md` updated if structure or conventions changed (`make docs-check` passes)
- [ ] ADR added in `docs/decisions/` if this makes a significant design decision
- [ ] No secrets in the diff (the gitleaks pre-commit hook passes)
- [ ] Affected Docker images rebuilt and restarted when testing
