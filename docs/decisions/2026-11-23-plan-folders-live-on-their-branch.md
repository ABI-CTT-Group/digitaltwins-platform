# Plan folders are live on their branch and closed when they merge

- **Date:** 2026-11-23
- **Status:** Accepted

## Context

Plan folders (`docs/plans/YYYY-MM-DD-HHMMSS-<feature>/`) are design evidence, committed with each change
for audit. Their rules were written for one agent session at a time. With several sessions in turn or in
parallel, gaps show:

- **Nothing shows whether a plan is in flight, finished or dropped.** `main` had 100 folders while
  `prototype` held 16 more that `main` couldn't see.
- **File names vary.** Only 35 of the 100 folders on `main` had a `plan.md`.
- **Nothing records where a session stopped.**
- **The sync rule is repeated and shouted.** It was written in CRITICAL/MUST/NEVER wording and repeated
  as `[ ] Sync plans` items through `tasks.md` files.

## Alternatives Considered

### Option A: Plans as a live tracker on `main`
- Plans merge early as `proposed` or `active`, and a follow-up PR closes each one.
- Pros: a grep for `Status: active` on `main` lists work in flight.
- Cons:
  - Every plan needs an extra PR.
  - `main` shows finished work as active until that PR merges.
  - The plan is split from the code it designs, which weakens audit tracing.

### Option B: Live on the branch, closed at merge
- A plan folder is live while its branch is open. It closes in the PR's last commit.
- Live work is found through `gh pr list` and `git worktree list`.
- Pros:
  - One PR per change, as now.
  - Everything on `main` is closed.
- Cons:
  - Seeing live work needs `gh` and network access.
  - A grep over `docs/plans/` can't find it.

### Option C: History only, no status
- Pros: no new convention.
- Cons:
  - A reader of an old folder can't tell whether the work finished or was cut short.
  - A session picking up work has no handoff to read.

## Decision

Option B, with these changes:

- **Header:** `plan.md` opens with `Status: active|done` and `Branch:`. A `done` line may carry a note,
  e.g. `done (steps 3–4 dropped)`.
  - No `proposed` status: nothing merges as proposed.
  - No `Owner:`: the PR author and git log record it.
- **Fixed names:** new folders use `plan.md` and `tasks.md`, copied from `docs/plans/TEMPLATE/`.
- **Handoff:** `tasks.md` ends with `## Progress / Next steps` (Done / Next / Open questions). A session
  updates it before it stops.
- **Close-out:** in the PR's last commit, "Next" becomes "Follow-ups".
- **Sync rule:** stated once and positively. Write the plan into the plan folder, or copy it there before
  asking for review. The per-step sync checklist items are dropped.

## Consequences

- **Older folders are unchanged.** They have no header and keep their file names, so they stay history.
- **`main` never shows an active plan.** Live work is seen only through open PRs and local worktrees.
