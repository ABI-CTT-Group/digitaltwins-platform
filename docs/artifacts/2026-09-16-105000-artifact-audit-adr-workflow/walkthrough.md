# Walkthrough: Agent Artifact Audit Trail, ADR Workflow, Secret Scanning

## Summary

Established a regulated-environment-ready workflow for agentic coding artifacts in a medical software project. All design evidence is now git-tracked and linked to code changes.

## Changes Made

### 1. [AGENTS.md](file:///home/clin864/Projects/digitaltwins-platform/AGENTS.md)

Expanded from 12 lines to 44 lines, adding three sections:

- **Agent Artifacts** (updated): Added commit policy requiring artifacts in the same branch/PR as code. Fixed "timespamps" typo. Strengthened secret redaction rule to reference the gitleaks hook.
- **Architecture Decision Records** (new): Timestamped ADRs in `docs/decisions/YYYY-MM-DD-title.md`. Three promotion criteria (real alternatives, convention deviations, non-obvious tradeoffs). Two checkpoints (plan-approval time, task-end).
- **Secret Scanning** (new): Documents the gitleaks pre-commit hook and agent responsibilities for proactive redaction.

### 2. [docs/decisions/](file:///home/clin864/Projects/digitaltwins-platform/docs/decisions/)

- [README.md](file:///home/clin864/Projects/digitaltwins-platform/docs/decisions/README.md) — Explains what ADRs are and when to create them
- [TEMPLATE.md](file:///home/clin864/Projects/digitaltwins-platform/docs/decisions/TEMPLATE.md) — Standard template: Title, Date, Status, Context, Alternatives, Decision, Consequences

### 3. [.pre-commit-config.yaml](file:///home/clin864/Projects/digitaltwins-platform/.pre-commit-config.yaml) (new)

Gitleaks v8.30.1 pre-commit hook. Blocks commits containing secrets automatically.

### 4. [.gitignore](file:///home/clin864/Projects/digitaltwins-platform/.gitignore)

Removed `docs/artifacts/` exclusion (line 208). Agent artifacts are now tracked by git for audit trail compliance.

### 5. [secret-scan.yml](file:///home/clin864/Projects/digitaltwins-platform/.github/workflows/secret-scan.yml) (new)

GitHub Actions workflow running gitleaks on every PR and push to `main`. CI backstop that catches secrets even when the local pre-commit hook isn't installed.

### 6. Secret Redaction in Existing Artifacts

- Scanned all 29 artifact folders with `gitleaks detect --source docs/artifacts/ --no-git`
- Found 1 issue: `admin:admin` credentials in [implementation_plan.md](file:///home/clin864/Projects/digitaltwins-platform/docs/artifacts/2026-08-20-per-user-seek-auth/implementation_plan.md#L160) → replaced with `<USERNAME>:<PASSWORD>`
- Re-scan: **0 findings**

## Verification

| Check | Result |
|---|---|
| `gitleaks detect --source docs/artifacts/ --no-git` | ✅ 0 leaks |
| `gitleaks detect --source docs/decisions/ --no-git` | ✅ 0 leaks |
| `pre-commit run --all-files` | ✅ Passed |
| Pre-commit hook installed at `.git/hooks/pre-commit` | ✅ |

## Not Yet Done (requires your action)

- **Git commit**: All changes are unstaged. When ready, commit with a message like:
  ```
  docs: add agent artifact audit trail, ADR workflow, and gitleaks pre-commit hook
  ```
- **Team notification**: If others work on this repo, they need to run `pre-commit install` after pulling.
