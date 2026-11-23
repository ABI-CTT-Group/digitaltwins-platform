# Tasks: harness improvements

Plan: [plan.md](plan.md)

- [x] 0. Review the plan and settle each decision (Decisions table in plan.md)
- [x] 1. Plans convention: ADR, AGENTS.md "Plans", `docs/plans/README.md`, `docs/plans/TEMPLATE/`, glossary "Plan folder" (`make docs-check` passes)
- [x] 2. Allowlist: `.claude/settings.json` + `.gitignore` (JSON parses; allowlisted command runs without a prompt)
- [x] 3. Glossary "Avoid:" sentences for Builder and Plan folder (`make docs-check` passes)
- [x] 4. Close-out: `Status: done`, tasks ticked, "Next" rewritten as "Follow-ups"
- [x] 5. AGENTS.md "Plans": one line on when to add Risks and Out of scope (`make docs-check` passes)
- [x] 6. Close out again: `Status: done`, "Next" rewritten as "Follow-ups"

## Progress / Next steps

- Done:
  - Proposal written (2026-11-23).
  - Review on 2026-11-23 settled the 11 decisions in plan.md. The open question is answered: a plan
    folder is live on its branch and history once merged.
  - Step 1 done: `make docs-check` passes.
  - Step 3 done: `make docs-check` passes.
  - Step 2 done:
    - The JSON parses.
    - `.claude/settings.local.json` is ignored and `.claude/settings.json` is not.
    - Checked by hand in a fresh session: allowlisted commands run without a prompt.
    - Rules use the "space before `*`" form. Per the Claude Code permissions docs, that form enforces a
      word boundary and also matches the bare command. That's why each make target has its own rule.
  - Templates reviewed (decision 12 in plan.md): fixes applied to the templates, AGENTS.md and this
    plan's header. `make docs-check` passes.
  - ADR 2026-11-12 reworded so it no longer names another repository; `make docs-check` passes.
  - Committed as one commit per step. The plan folder lands with the close-out commit, so the
    earlier commits each hold one change.
  - Reopened after review: added decision 13 and step 5.
- Follow-ups: none.
- Open questions / blockers: none.
