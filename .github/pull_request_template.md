## Summary
What this change does and why. Add a diagram, diff sketch or tree when it makes the change clearer.

- Related issue(s): e.g. Closes #123, or none
- Plan folder: `docs/plans/<folder>/plan.md`, or none
- Type: feat / fix / docs / refactor / test / ci / chore (the Conventional Commits type)
- AI use: none, or drafted with <tool>, reviewed by <person>

## Evidence
How you know this change works: a before / after screenshot, command output, or the test that
failed and now passes. Name the deployment you tried it on, if any (connected / airgapped, http / https).

## Merge danger
- Door: one-way (hard to undo) or two-way (reverts cleanly)
- Blast radius: who or what breaks if this is wrong

## Checklist
- [ ] `make test` and `make lint` pass locally
- [ ] Docs updated (README, `docs/`, service READMEs) where behaviour changed
- [ ] `docs/codemap.md`, `util/SCRIPTS.md` or the service's `AGENTS.md` updated if structure or conventions changed (`make docs-check` passes)
- [ ] ADR added in `docs/decisions/` if this makes a significant design decision
- [ ] No secrets in the diff (the gitleaks pre-commit hook passes)
- [ ] Affected Docker images rebuilt and restarted when testing (or n/a)
