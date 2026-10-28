# Make lint a required CI check

- **Date:** 2026-10-28
- **Status:** Accepted

## Context

[2026-10-16-ci-make-in-pinned-containers.md](2026-10-16-ci-make-in-pinned-containers.md) made lint and
type-check report-only: the `lint` job ran `make lint-python` and `make lint-frontend` with
`continue-on-error`, so it always showed green. `main` had 135 ruff errors, 33 eslint problems and 14
vue-tsc errors at the time, so a blocking job would have failed every PR.

Report-only lint went unread. Findings piled up because a new one looked like the old ones. Among them
was a duplicate route-handler name in the builder, a real defect. The lint cleanup (PR #371) brought all
three tools to 0.

## Alternatives Considered

### Option A: Keep lint report-only
- Pros: never blocks a PR.
- Cons: findings pile up again, and nobody looks at a check that is always green.

### Option B: Require ruff only
- Pros: ruff (pyflakes-class rules only) has few false positives.
- Cons: the frontend has no unit coverage of its types, so vue-tsc errors (wrong props, wrong API
  types) would build up again unseen. The Docker build doesn't type-check.

### Option C: Require the whole lint job (ruff, eslint and vue-tsc)
- Pros: one check, the same as `make lint` locally; keeps `main` at 0.
- Cons: a frontend dependency bump can break vue-tsc (the duplicate vite and rollup copies already
  need two workarounds in `vite.config.ts`), and eslint warnings fail it as well as errors.

## Decision

Option C. The job's name is now `lint` (it was `lint (report-only)`), and its steps no longer have
`continue-on-error`. The frontend step runs even when the Python step fails, so one run reports both.
`lint` is added to the "CI required checks" ruleset after this change merges, so open PRs that still
run the old workflow aren't left waiting for a check they never report.

The job still runs only when api, builder, frontend or jupyterhub code changes; GitHub counts a skipped
required check as passing. `docs check` stays report-only.

## Consequences

- A PR must pass `make lint`. Contributors run it locally before pushing, as they do `make test`.
- A lint finding has to be fixed, or suppressed in the code with the reason (`# noqa: <rule>`,
  `// @ts-expect-error <reason>`). There is no baseline file.
- If you rename the job, update the ruleset in the same change
  ([docs/testing.md](../testing.md#what-ci-checks)).
- Aligning the vite and rollup versions (`docs/future_refactoring.md`) removes the two `vite.config.ts`
  workarounds. The `@ts-expect-error` fails `lint` once it's no longer needed.
