# Tasks: Update LDH to v0.3.8 (SEEK 1.18.5)

Plan: [plan.md](plan.md)

- [x] 1. Bump `LDH_RELEASE` in `.env.template` (`grep '^LDH_RELEASE=' .env.template` prints `LDH_RELEASE=v0.3.8`)
- [x] 2. Update the version note in `docs/seek-integration.md` (`grep -n 'v0.3.8.*1.18.5' docs/seek-integration.md` matches; `make docs-check` passes)
- [x] 3. Confirm the image's SEEK version (`docker run --rm --entrypoint cat ghcr.io/nfdi4health/ldh:v0.3.8 config/version.yml` shows `patch: 5`)
- [ ] 4. Roll out to staging, then demo ([Upgrading LDH](../../seek-integration.md#upgrading-ldh): both Keycloak checks pass and Keycloak login to `/seek` works on each host)
- [ ] 5. Close out: `Status: done` in plan.md, remaining tasks ticked, Handoff cleared

## Handoff

- Stopped at: steps 1–3 done on the branch; step 4 (rollout to staging, then demo) not started.
- Blocked on: the branch merging, then a host-side upgrade on each host.
