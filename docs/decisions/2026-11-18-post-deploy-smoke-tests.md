# Post-deploy smoke tests live in the root `tests/` and run by hand

- **Date:** 2026-11-18
- **Status:** Accepted

## Context

The root `tests/` folder held only a `.gitkeep`, listed as debt with "use it for end-to-end tests,
or remove it". Every test suite was a unit suite that runs offline in a throwaway container, so
nothing checked that a deployed platform works as a whole: that the gateway reaches each service,
that Keycloak's issuer matches the public URL, that a user can sign in and reach the API and the
builder. Those are the things a deploy, an upgrade or a config change breaks.

End-to-end checks need the whole stack running, and the stacks we can point them at (local,
staging, demo) hold real data.

## Alternatives Considered

### Option A: Delete the folder
- Pros: removes the placeholder with no new code.
- Cons: still no check of a deployed platform.

### Option B: Playwright browser tests in the portal frontend
- Pros: exercise real screens, including the Keycloak sign-in page.
- Cons: cover one service's UI, not every service behind the gateway; they belong in
  `services/portal/frontend/e2e/`, not the root; heavier to write and keep stable.

### Option C: pytest HTTP smoke tests in the root `tests/`, run by hand against a running stack
- Pros: cover every service through the gateway in about a dozen fast requests; work against any
  host by URL; reuse the Makefile's pinned-image pattern; sign in through `/api/login`, so no
  client secret is needed.
- Cons: someone must remember to run them; they check that services answer, not that user
  journeys work.

### Option D: Start the full stack in CI and run end-to-end tests before merging
- Pros: automatic, catches breakage before it reaches a host.
- Cons: needs SEEK, Airflow, JupyterHub and Keycloak, plus secrets, on a CI runner: slow, heavy and
  a much larger job than the problem warrants today.

## Decision

Option C. `make smoke` runs pytest + httpx from the pinned Python image with `--network host`,
mounting only `tests/`. `SMOKE_URL` picks the host. Sign-in reads `SMOKE_USERNAME` and
`SMOKE_PASSWORD` from the caller's shell, passed to the container by name, and those checks skip
when they're unset. The tests are not part of `make test` or CI.

Browser tests (B) can be added later in the portal frontend's own folder; CI end-to-end tests (D)
can reuse these checks if a stack ever runs in CI.

## Consequences

- There is now a quick answer to "is this deploy healthy?" for any host.
- The tests must stay read-only, because they target real data. `tests/README.md` lists the GETs
  with side effects that must never be called from them.
- Nothing runs them automatically: their value depends on running them after each deploy.
- `make lint` and the CI lint filter now cover `tests/`.
