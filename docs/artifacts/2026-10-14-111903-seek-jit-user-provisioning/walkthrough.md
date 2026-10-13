# Walkthrough: SEEK just-in-time user provisioning

## Problem

A platform user's forwarded Keycloak JWT only worked in SEEK after they had signed into `/seek` once and filled in SEEK's profile form. Before that, SEEK found no `identities` row for their `sub`, so it ran the request as anonymous. Reads were public-only and writes failed.

## What changed

**`services/seek/ldh-deployment/keycloak_jwt_auth.rb`** (submodule)
- New `KeycloakJwtAuth.provision_user(sub:, email:, first_name:, last_name:, username:)`.
  - Under a per-`sub` MySQL `GET_LOCK`, it re-checks for an existing identity.
  - It refuses if a Person already has that email (case-insensitive).
  - Otherwise, in one transaction, it creates Person → User (unique login, random password, activated) → `Identity(provider: 'oidc', uid: sub)`.
  - It returns `nil`, so the caller stays anonymous, for a blank email or a `service-account-*` username.
- `user_from_keycloak_jwt` calls it when no identity matches, using the token's `email`, `given_name`, `family_name` and `preferred_username` claims.

**`services/seek/ldh-deployment/keycloak_oidc.rb`** (submodule)
- A private override of `SessionsController#create_user_from_omniauth` calls the same provisioner. A first-time `/seek` login therefore lands logged in, with no profile form. A refusal shows "No SEEK account could be created … contact an administrator".

**`services/seek/ldh-deployment/test/keycloak_provisioning_check.rb`** (submodule, new)
- Plain-assert script run through `rails runner -`. Each case runs in a rolled-back transaction.
- Cases: new identity; same `sub` again (idempotent); email clash; blank email; service account.

**Docs**
- `docs/seek-integration.md`: new "Account provisioning" section; updated hardening note and pieces table.
- `docs/decisions/2026-10-14-seek-jit-user-provisioning.md`: ADR.

## Verification

1. **Red:** the check script failed (`provision_user` undefined) before the change.
2. **Green:** after the change, all 14 checks pass, and the rolled-back runs leave no rows behind.
3. **`seek` restarted:** the initializers are read-only bind mounts, so no rebuild was needed. The container is healthy and the override is loaded as a private method.
4. **End-to-end with throwaway Keycloak users** (created and deleted by the test):
   - API path: the first `GET /digitaltwins-api/projects` provisions one active, registered SEEK user; a second call reuses it.
   - Browser path: a first `/seek` login lands logged in on SEEK's "create or join a project" page, not the profile form.
   - Email clash: the API call stays anonymous, no identity is created, and the browser login is refused.
   - No duplicate `identities` rows exist after the runs.
5. **Existing users:** the platform admin's API call resolves to their existing SEEK user, with no provisioning.

## Run the check script

```
docker compose exec -T seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' \
  < services/seek/ldh-deployment/test/keycloak_provisioning_check.rb
```

## Not done

- Project membership is not provisioned, by design (see the ADR).
- No tool/workflow registration write test was run for a newly provisioned member. That path is unchanged for users who already have an identity.
