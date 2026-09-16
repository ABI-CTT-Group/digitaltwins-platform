## Agent Artifacts

Maintain timestamped folders in `docs/artifacts/` and immediately sync all agent-generated planning or summary documents (e.g., implementation plans, task checklists, walkthroughs).
Timestamps should be in the format `YYYY-MM-DD-HHMMSS` and reflect the time of creation or last update. For example, if you create a plan for a feature called "user-auth" on March 15, 2024, at 14:30:00, the folder should be named `docs/artifacts/2024-03-15-143000-user-auth/`.

**CRITICAL REQUIREMENT:** Whenever you generate, modify, or update any planning or summary artifact, you MUST immediately duplicate or sync the updated version to a time-stamped folder in `docs/artifacts/<date>-<feature-name>/`. Do not wait until the end of your task to sync them.

**COMMIT POLICY:** Artifacts MUST be committed in the **same branch/PR** as the code changes they relate to. This is a regulated-environment requirement — design evidence must be linked to implementation for audit traceability.

**OPERATIONAL STEPS TO ENFORCE THIS:**
1. **Task Tracking:** If you maintain a task checklist (e.g., a `task.md` or internal TODO list), you MUST explicitly include a checklist item like `[ ] Sync artifacts to docs/artifacts/` immediately following any step that modifies a document.
2. **Immediate Sync:** Every time you use your file-writing capabilities to create or update a plan or artifact, your very next action MUST be executing a terminal command (or equivalent file operation) to copy the updated file into the `docs/artifacts/` directory.
3. **Pre-Feedback Check:** NEVER pause your execution to ask the user for review, feedback, or approval without first verifying that all updated artifacts have been synced to the project directory.
4. **Secret Redaction:** NEVER include actual passwords, API keys, or sensitive environment variables in implementation plans or walkthroughs. Always use placeholders like `<REDACTED>`. You must actively verify no secrets exist before syncing to `docs/artifacts/`. A `gitleaks` pre-commit hook enforces this at commit time, but you MUST still redact proactively — do not rely on the hook as the sole control.

---

## Architecture Decision Records (ADRs)

When a task involves a **significant design decision**, document it as an ADR in `docs/decisions/`.

**Location:** `docs/decisions/YYYY-MM-DD-title.md` (timestamped, one per decision).
**Template:** See `docs/decisions/TEMPLATE.md`.

**When to create an ADR — only when:**
- A real choice between alternatives was evaluated
- A deviation from an existing convention or architecture was made
- A non-obvious tradeoff with future consequences was accepted

Do NOT create ADRs for routine fixes, minor refactors, or straightforward implementations with no real alternatives.

**Two checkpoints:**
1. **At plan-approval time:** When the implementation plan involves a real choice between alternatives, draft an ADR alongside the plan. Present it to the user for review together with the plan.
2. **At task-end:** Check whether any decisions emerged mid-implementation that weren't captured at plan time. If so, create or update the ADR. If the outcome diverged from the plan-time ADR, update it to reflect what actually happened.

ADRs MUST be committed in the **same branch/PR** as the related code changes.

---

## Secret Scanning

A `gitleaks` pre-commit hook is configured in `.pre-commit-config.yaml` to automatically block commits containing secrets. This is a mandatory control for this regulated-environment project.

**Agent responsibilities:**
1. **Proactive redaction:** Always use placeholders like `<REDACTED>` for any passwords, API keys, tokens, or sensitive environment variables in all documents.
2. **Pre-sync scan:** Before staging artifact files, verify no secrets are present. If unsure, run `gitleaks detect --source docs/artifacts/ --no-git` and fix any findings.
3. **Never bypass:** Do not advise or assist in bypassing the pre-commit hook.
