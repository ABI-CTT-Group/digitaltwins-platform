# Agent Artifact Audit Trail, ADR Workflow, and Secret Scanning

Establish a regulated-environment-ready workflow for agentic coding artifacts. This project is medical software (IEC 62304 / ISO 13485 context), so all design evidence must be traceable and committed.

## Context

- **Current state**: 29 agent artifact folders exist in `docs/artifacts/` but are gitignored. No ADR workflow exists. No automated secret scanning.
- **Goal**: Commit all artifacts for audit trail, add ADR workflow for significant decisions, and enforce secret scanning before commits.

## Proposed Changes

### 1. AGENTS.md Update

#### [MODIFY] [AGENTS.md](file:///home/clin864/Projects/digitaltwins-platform/AGENTS.md)

Update the existing Agent Artifacts section and add two new sections:

**Changes to existing "Agent Artifacts" section:**
- Add instruction that artifacts must be committed in the same branch/PR as the code changes (not kept gitignored)
- Strengthen secret redaction rule to reference the gitleaks pre-commit hook as the enforcement mechanism
- Fix the typo on line 4 ("timespamps" → "timestamps")

**New "Architecture Decision Records" section:**
- Location: `docs/decisions/YYYY-MM-DD-title.md`
- Promotion criteria (only when):
  - A real choice between alternatives was evaluated
  - Deviation from an existing convention or architecture
  - Non-obvious tradeoff with future consequences
- Two checkpoints:
  1. **At plan-approval time** — draft ADR alongside the plan when a real choice is involved
  2. **At task-end** — catch decisions that emerged mid-implementation, or update the plan-time ADR if the outcome diverged

**New "Secret Scanning" section:**
- Reference the gitleaks pre-commit hook
- Require `gitleaks detect` scan on `docs/artifacts/` before staging any artifact files

---

### 2. ADR Template and Directory

#### [NEW] `docs/decisions/README.md`

Brief explanation of what ADRs are, when to create one, and pointer to the template.

#### [NEW] `docs/decisions/TEMPLATE.md`

Standard ADR template with sections:
- **Title**: Short descriptive title
- **Date**: YYYY-MM-DD
- **Status**: Proposed / Accepted / Superseded by [link]
- **Context**: What is the issue we're deciding on?
- **Alternatives Considered**: What options were evaluated?
- **Decision**: What was chosen and why?
- **Consequences**: What are the tradeoffs and implications?

---

### 3. Secret Scanning Setup

#### [NEW] `.pre-commit-config.yaml`

Configure pre-commit with gitleaks hook:
```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.22.1  # will pin to latest stable at install time
    hooks:
      - id: gitleaks
```

> [!IMPORTANT]
> This requires `pre-commit` to be installed (`pip install pre-commit`) and initialized (`pre-commit install`). The plan includes running these commands.

> [!NOTE]
> We rely on GitHub's native secret scanning for the CI-level checks (to be enabled via GitHub's Security settings), rather than a separate Gitleaks GitHub Action, to avoid potential organizational costs.

---

### 4. Gitignore Update

#### [MODIFY] [.gitignore](file:///home/clin864/Projects/digitaltwins-platform/.gitignore)

Remove line 208 (`docs/artifacts/`) so artifacts are tracked by git.

---

### 5. Retroactive Commit of Existing Artifacts

- Run `gitleaks detect --source docs/artifacts/ --no-git` to scan existing 29 folders
- Fix any findings (redact secrets)
- Stage and note for a single commit: `docs: add historical agent artifacts for audit trail`

> [!WARNING]
> The actual `git commit` will NOT be run automatically — per your rules, commits are only made when explicitly requested. The plan will prepare everything for commit and report scan results.

---

## Verification Plan

### Automated Tests
- `gitleaks detect --source docs/artifacts/ --no-git` — must return 0 findings before staging
- `pre-commit run --all-files` — must pass after setup

### Manual Verification
- Review updated `AGENTS.md` for correctness and completeness
- Verify `docs/decisions/` directory and template exist
- Verify `.pre-commit-config.yaml` is valid
- Confirm `docs/artifacts/` is no longer in `.gitignore`
- Confirm all 29 existing artifact folders are staged
