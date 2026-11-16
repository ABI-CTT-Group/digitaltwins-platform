# Tasks: restart unless-stopped

- [x] Check out `dev_chinchien` and fast-forward it to `origin/main`
- [x] Sync plan to `docs/plans/2026-11-17-115139-restart-policy-unless-stopped/plan.md`
- [x] Write ADR `docs/decisions/2026-11-17-restart-policy-unless-stopped.md`
- [x] Red: write `util/tests/test_restart_policy.sh`, mount the tracked service compose files in `make test-util`; it fails on the gaps
- [x] Green: set `restart: unless-stopped` in the compose files; update `services/hapi-fhir/README.md`
- [x] `make test-util` passes
- [x] `make test`, `make lint`, `make docs-check`, `make gitleaks` pass
- [x] `docker compose config` shows `unless-stopped` on every service except the one-shots
- [x] Commit on `dev_chinchien`
- [ ] Push and open the PR into `main` (after your go-ahead)
