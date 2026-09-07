## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution (TDD)

**Define success criteria. Loop until verified.**

- **Agentic TDD:** Always write failing tests first (Red), write minimum code to pass (Green), then clean up (Refactor). Do not consider a task complete until tests pass.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## Git

- Use Conventional Commits format
- Do NOT commit changes to Git unless explicitly requested by the user.
- **Atomic Commits:** Every commit should represent one—and only one—logical unit of work. Ensure that if a change breaks, you can revert that single commit without undoing unrelated work.
- **Pre-Commit Secret Check:** Before staging or committing any files, you MUST actively check for and redact any accidental secrets (passwords, tokens, keys).


## Agent Artifacts

Maintain timestamped folders in docs/artifacts/ and immediately sync all agent-generated planning or summary documents (e.g., implementation plans, task checklists, walkthroughs).
timespamps should be in the format `YYYY-MM-DD-HHMMSS` and reflect the time of creation or last update. For example, if you create a plan for a feature called "user-auth" on March 15, 2024, at 14:30:00, the folder should be named `docs/artifacts/2024-03-15-143000-user-auth/`.
**CRITICAL REQUIREMENT:** Whenever you generate, modify, or update any planning or summary artifact, you MUST immediately duplicate or sync the updated version to a time-stamped folder in `docs/artifacts/<date>-<feature-name>/`. Do not wait until the end of your task to sync them.

**OPERATIONAL STEPS TO ENFORCE THIS:**
1. **Task Tracking:** If you maintain a task checklist (e.g., a `task.md` or internal TODO list), you MUST explicitly include a checklist item like `[ ] Sync artifacts to docs/artifacts/` immediately following any step that modifies a document.
2. **Immediate Sync:** Every time you use your file-writing capabilities to create or update a plan or artifact, your very next action MUST be executing a terminal command (or equivalent file operation) to copy the updated file into the `docs/artifacts/` directory.
3. **Pre-Feedback Check:** NEVER pause your execution to ask the user for review, feedback, or approval without first verifying that all updated artifacts have been synced to the project directory.
4. **Secret Redaction:** NEVER include actual passwords, API keys, or sensitive environment variables in implementation plans or walkthroughs. Always use placeholders like `<REDACTED>`. You must actively verify no secrets exist before syncing to `docs/artifacts/`.

## Planning and Implementation

- When asked to create a plan or implementation plan, generate the plan but **do not begin implementation** until explicit approval is given.
- If feedback or comments are provided on a plan, review and update the plan accordingly. **Do not implement** any changes until the updated plan receives explicit approval.
