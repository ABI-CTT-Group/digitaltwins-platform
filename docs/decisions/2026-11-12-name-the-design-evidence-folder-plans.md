# Name the design-evidence folder `docs/plans/`

- **Date:** 2026-11-12
- **Status:** Accepted

## Context

Each change keeps its design evidence (implementation plan, task checklist, walkthrough) in a dated folder,
committed with the code for audit. The folder was `docs/artifacts/` and the rules called its contents
"artifacts", the name Google Antigravity gives these documents. Elsewhere "artifact" means build or CI output
(GitHub Actions artifacts, Maven artifacts, the builder's "build artifacts" here), and in VeriFlow, which shares
these rules, it already means an agent's output (`GET /api/v1/orchestrate/{run_id}/artifacts/{agent_name}`).
An agent told to "sync artifacts" could reach for the wrong thing.

## Alternatives Considered

### Option A: Keep `docs/artifacts/`
- Pros: no change; 89 folders and their links stay where they are.
- Cons: the name stays tied to one tool and keeps clashing with build and pipeline outputs.

### Option B: `docs/plans/`
- Pros: the name most agent tooling and readers recognise (Claude Code plan mode, superpowers' `docs/plans/`,
  Spec Kit's `plan.md`); no clash in either repo.
- Cons: a folder also holds a walkthrough, which records what happened rather than a plan.

### Option C: `specs/` (GitHub Spec Kit, Kiro)
- Pros: popular for spec-driven agent work.
- Cons: suggests requirements specifications, not an audit trail of plans and walkthroughs.

## Decision

Option B, in both digitaltwins-platform and VeriFlow so their rules stay identical. The term changes with the
folder: a document is a "plan" and one dated folder is a "plan folder". Uses of "artifact" that mean build,
Docker or pipeline output are unchanged.

## Consequences

- Existing plan folders keep their names and contents; text inside them that says `docs/artifacts/` is
  history and is not rewritten. Relative links between them still resolve.
- Links from outside the repo to `docs/artifacts/...` break.
