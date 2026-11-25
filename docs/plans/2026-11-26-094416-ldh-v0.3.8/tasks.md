# Tasks: Update LDH to v0.3.8 (SEEK 1.18.5)

Plan: [plan.md](plan.md)

- [x] 1. Bump `LDH_RELEASE` in `.env.template` (`grep '^LDH_RELEASE=' .env.template` prints `LDH_RELEASE=v0.3.8`)
- [x] 2. Update the version note in `docs/seek-integration.md` (`grep -n 'v0.3.8.*1.18.5' docs/seek-integration.md` matches; `make docs-check` passes)
- [x] 3. Confirm the image's SEEK version (`docker run --rm --entrypoint cat ghcr.io/nfdi4health/ldh:v0.3.8 config/version.yml` shows `patch: 5`)
- [x] 4. Roll out to staging, then demo: moved to [#418](https://github.com/ABI-CTT-Group/digitaltwins-platform/issues/418), not done in this plan
- [x] 5. Close out: `Status: done` in plan.md, remaining tasks ticked, Handoff cleared

## Handoff
