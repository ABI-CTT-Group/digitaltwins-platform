# Plans

Each folder here is the design evidence for one change: the plan, the task checklist and the
walkthrough written while the change was made, named `YYYY-MM-DD-HHMMSS-<feature>/`. They're
committed in the same pull request as the change, so an auditor can trace every change to its design.
This is a regulated-environment requirement; the rules are in [AGENTS.md](../../AGENTS.md#plans).

A plan folder is live while its branch is open. Start one by copying [TEMPLATE/](TEMPLATE/). It
closes, with `Status: done` in its `plan.md`, in the last commit of its pull request, so every folder
on `main` is closed. To see work in progress, use `gh pr list`.

**Once merged, these are history, not reference.** A folder describes the repo as it was on its date, and later
changes aren't written back into it, so paths, names and steps may be out of date. To learn how the
platform works today, read the [guides](../README.md), the [code map](../codemap.md) and the
[ADRs](../decisions/) first. Use a plan folder when you need to know why or how a past change was made.

`make docs-check` doesn't check links in this folder.
