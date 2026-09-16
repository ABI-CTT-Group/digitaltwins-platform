# Task: Agent Artifact Audit Trail, ADR Workflow, Secret Scanning

- [x] Update AGENTS.md (commit policy, ADR workflow, secret scanning, fix typo)
- [x] Create `docs/decisions/README.md`
- [x] Create `docs/decisions/TEMPLATE.md`
- [x] Create `.pre-commit-config.yaml` with gitleaks hook
- [x] Update `.gitignore` — remove `docs/artifacts/` exclusion
- [x] Install pre-commit framework and gitleaks hook
- [x] Scan existing 29 artifact folders with gitleaks
  - Found 1 issue: `admin:admin` in curl example → redacted
  - Re-scan: clean (0 findings)
- [x] Sync artifacts to `docs/artifacts/`
- [x] Verify: `pre-commit run --all-files` → Passed
