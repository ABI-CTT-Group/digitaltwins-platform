# Task: SEEK JIT user provisioning

- [x] Sync implementation plan to docs/artifacts/
- [x] Write failing check script `services/seek/ldh-deployment/test/keycloak_provisioning_check.rb` (Red)
- [x] Add `KeycloakJwtAuth.provision_user` + call it from `user_from_keycloak_jwt`
- [x] Override `SessionsController#create_user_from_omniauth` in `keycloak_oidc.rb`
- [x] Restart `seek`; check script passes (Green)
- [x] End-to-end: API token path, browser path, email-clash refusal; clean up test users
- [x] Update `docs/seek-integration.md`
- [x] Write ADR `docs/decisions/2026-10-14-seek-jit-user-provisioning.md`
- [x] Write walkthrough
- [x] Sync artifacts to docs/artifacts/ (after each document change)
- [x] Secret check (gitleaks) on artifacts
