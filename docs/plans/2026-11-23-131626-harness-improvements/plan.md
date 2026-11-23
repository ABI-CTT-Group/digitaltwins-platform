# Harness improvements: live-work status, session handoff, permissions, glossary synonyms

Status: done

Branch: docs/harness-improvements

## Context

The harness works well when one session works at a time. It consists of:

- AGENTS.md as the single source, with pointer files
- `docs/plans/<YYYY-MM-DD-HHMMSS>-<slug>/` plan folders
- ADRs
- `make` targets shared with CI

Gaps show when several agent sessions share the repo, whether one after another or in parallel:

- **Nothing shows which plans are in flight.** Main has 100 plan folders, and `prototype` alone has 16
  more that main can't see until it merges.
- **Plan files have no fixed names.** Only 35 of the 100 folders on main have a `plan.md`. The others
  use `implementation_plan.md`, `task.md` and other names.
- **Nothing records where a session stopped.**
- **Every teammate's Claude Code asks permission for the same safe commands.**
- **The glossary doesn't name the synonyms to avoid.**

This plan makes five changes. A review on 2026-11-23 settled them; see [Decisions](#decisions).

## Changes

1. **A plan folder is live on its branch and history once merged.**
   - Problem: a new session can't tell which plans are in flight. AGENTS.md calls `docs/plans/` audit
     history, so agents can't use it to resume work.
   - Finding live work: AGENTS.md points at `gh pr list` (the team's open PRs, including from forks) and
     `git worktree list` (your own worktrees). It doesn't use a grep over `docs/plans/`. A plan closes
     in its PR, so `main` never holds an active plan, and a grep on a branch finds only that branch's
     own plan.
   - Header: the first lines of `plan.md` are `Status: active|done` and `Branch:`. A `done` line may
     carry a note, e.g. `Status: done (steps 3–4 dropped)`. The header tells a reader of a merged folder
     whether the work finished as planned. There is no `proposed` status (nothing merges as proposed)
     and no `Owner:` (the PR author and git log record it, which keeps names out of docs).
   - Closing: set `Status: done` and tick the remaining tasks in the PR's last commit. Set it back to
     `active` if review asks for more work. A plan folder reaches `main` only through its own merge,
     so it always arrives closed.
   - Fixed names: new plan folders use `plan.md` and `tasks.md`, copied from `docs/plans/TEMPLATE/`.
     Older folders keep their names and stay history.

2. **A handoff section in `tasks.md`.**
   - Problem: `tasks.md` records ticks, but not where a session stopped or what blocks it. Only 1 of the
     100 folders on main has anything like that.
   - Change: `tasks.md` ends with `## Handoff` (Stopped at / Blocked on), filled in before a session
     stops with only what the ticks can't show. The next session reads `tasks.md` first.
   - Close-out: in the PR's last commit, the Handoff section is cleared. Anything still open goes to
     `docs/future_refactoring.md` or the PR description, so merged history carries no stale state.

3. **Rephrase the plan-sync rules without the CRITICAL/MUST/NEVER wording.**
   - Keep the substance: plans written by tools outside the repo must land in `docs/plans/<folder>/`,
     redacted, and be committed in the same PR. For example, Claude Code plan mode writes to
     `~/.claude/plans/` and Antigravity writes to its own folder.
   - Problem: capitals and prohibitions make the forbidden behaviour more salient to models, not less.
     The `[ ] Sync plans to docs/plans/` checklist items also repeat through `tasks.md` files: 13 folders
     on main have them, usually 2 or 3 times each.
   - Change: state the rule once, positively: "Write the plan straight into
     `docs/plans/<folder>/plan.md`; if a tool wrote it elsewhere, copy it there before asking for
     review." Drop the per-step sync checklist items.

4. **Commit a `.claude/settings.json` permission allowlist.**
   - Problem: every teammate's Claude Code asks permission for the same safe commands.
   - Change: allow these commands:
     - `make test*`, `make lint`, `make docs-check` and `make gitleaks`
     - read-only git: `git status`, `git diff`, `git log` and `git worktree list`
     - read-only gh: `gh pr list` and `gh pr view`

     Gitignore `.claude/settings.local.json`, so personal overrides stay out of git. Keep the
     destructive util scripts and `docker compose` off the list, matching the safety rules.

5. **Name discouraged synonyms in `docs/glossary.md`.**
   - Problem: the glossary defines terms but doesn't name the synonyms to stop using. Drift such as
     "portal backend" for "builder" is only caught by reviewers.
   - Change: add an "Avoid: X, Y." sentence to the Meaning cell, only for terms where drift happens. No
     new column, because the table is already wide. The first pass covers the two renames backed by
     ADRs: Builder (avoid "portal backend") and Plan folder (avoid "artifacts"). Others are added when
     a reviewer catches real drift.

6. **GitHub templates.**
   - Problem: 13 of the last 15 merged PRs ignored the PR template and used another format
     (Summary / Evidence / Merge Danger), and the template has no field for the plan folder. Only the
     bug report warns against pasting secrets, and no issue template applies a label.
   - Change: the PR template merges both formats (Summary with Related issue, Plan folder, Type and AI
     use fields; Evidence; Merge danger; Checklist). The feature and document request templates get
     the secrets warning, and each issue template applies its label.
   - Not in scope: a security policy. The gap goes in `docs/future_refactoring.md`.

## Steps

One PR, one commit per step, so each can be reverted on its own.

1. **Plans convention (changes 1–3).**
   - Files:
     - new ADR `docs/decisions/2026-11-23-<title>.md`
     - the AGENTS.md "Plans" section
     - `docs/plans/README.md`: live on the branch, history once merged
     - `docs/plans/TEMPLATE/plan.md` and `tasks.md`
     - the glossary's "Plan folder" entry, for the new lifecycle
   - Verify: `make docs-check` passes, and a fresh agent session finds live work through
     `gh pr list` / `git worktree list` and knows to close its plan in the PR's last commit.
2. **Allowlist (change 4).**
   - Files: `.claude/settings.json` and `.gitignore`.
   - Verify: the JSON parses, and an allowlisted command runs without a prompt in a fresh session.
3. **Glossary synonyms (change 5).**
   - Files: "Avoid:" sentences for Builder and Plan folder.
   - Verify: `make docs-check` passes.
4. **Close-out.**
   - Set `Status: done`, tick the tasks, and clear the Handoff section.

## Decisions

Settled in a review on 2026-11-23:

| # | Question | Decision |
|---|---|---|
| 1 | Scope | This repo only. |
| 2 | Live tracker or history? | Live on its branch, history once merged. Live work is found through `gh pr list` and `git worktree list`, not a grep. |
| 3 | Allowlist | The make targets, read-only git, and `gh pr list` / `gh pr view`. Gitignore `.claude/settings.local.json`. |
| 4 | Glossary synonyms | An "Avoid:" sentence in the Meaning cell, not a new column. |
| 5 | Header | `Status: active\|done` (with an optional note) plus `Branch:`. No `proposed`, no `Owner:`. |
| 6 | File names | `plan.md` and `tasks.md` are required in new folders, copied from templates. |
| 7 | Handoff at close | The Handoff section is cleared; open items go to `docs/future_refactoring.md` or the PR description. Superseded the "Next" → "Follow-ups" rule (see 14). |
| 8 | Sync rule | One positive sentence. Drop the per-step sync items and Claude Code's `plansDirectory` setting (it writes flat files, which don't fit the folder layout). |
| 9 | Template location | `docs/plans/TEMPLATE/` |
| 10 | First "Avoid:" terms | Only the renames backed by ADRs: Builder and Plan folder. |
| 11 | Landing | One PR, one commit per step. The plan folder lands with the close-out commit, so its ticks never run ahead of the commits. |
| 12 | Template review | Blank line between the header lines (one paragraph otherwise). Each step's check lives only in `tasks.md`, as a command and the result that means done. `tasks.md` ends with a fixed close-out item. |
| 13 | Optional plan sections | Not in the template. One line in the AGENTS.md "Plans" section says when to add Risks (migrations, deploys, live data) and Out of scope (disputed scope). |
| 14 | Handoff section | `## Handoff` (Stopped at / Blocked on) replaces `## Progress / Next steps`. Done and Next repeated the checklist; only a step left partway and blockers can't be shown by ticks. |
| 15 | PR template | Merge the existing template with Summary / Evidence / Merge danger. Evidence is proof for this change; the Checklist holds the chores every PR needs, starting with `make test` and `make lint` passing locally (a reminder, even though CI runs the affected suites). |
| 16 | Plan folder field | A link, or "none": a human change may have no plan. |
| 17 | AI use field | One line: none, or drafted with a tool and reviewed by a named person. |
| 18 | Issue templates | The secrets warning on all three; each applies its label (bug, enhancement, documentation). The `v0.5.0` version example stays: it is the latest release tag. |
| 19 | Security policy | Out of scope; recorded as debt. No AGENTS.md line about the PR template. Lands in this PR, whose description is rewritten in the new template. |
