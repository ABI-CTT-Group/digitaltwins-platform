# Plan: auto-provision SEEK accounts from Keycloak identity (JIT)

## Context

SEEK only links a Keycloak user (`sub`) to a SEEK user when that person first signs into the `/seek` UI with "Sign in with Keycloak" **and** fills in SEEK's "create your profile" form. Until then, the API's forwarded JWT is valid, but `keycloak_jwt_auth.rb` finds no `Identity(provider: 'oidc', uid: sub)`. The request then runs as **anonymous**: reads return only public items, and writes (tool/workflow registration, `create_sop`) fail.

Fix: when SEEK sees a valid Keycloak identity it doesn't know, it creates the SEEK account itself (User + Person + Identity, activated). This runs on both paths, so a user is created the same way whichever path they hit first.

Decisions (from the user):
- **Account only.** Project membership stays an admin action (`util/add-seek-project-member.sh`). A new user can read and own things, but can only write into projects they've been added to.
- **Email clash → refuse and log.** If a SEEK Person already has the token's email, don't create or link anything. Stay anonymous and log a warning. The realm has `verifyEmail: false`, so linking by email would let one account take over another.
- **Both paths.** The API token path and the `/seek` OIDC callback share one provisioner.

## Why provision inside SEEK (not elsewhere)

- **API side:** rejected. SEEK's REST API can't create identities, and it would need an admin credential, which is the global token we just removed.
- **Batch sync script:** rejected. It misses users created after it runs.
- **Keycloak event listener:** rejected. It's heavy and needs a Java SPI.
- **In SEEK:** chosen. SEEK already creates User + Identity on OIDC login when `omniauth_user_create` is on (`SessionsController#create_user_from_omniauth`). We extend that to also create the Person, and call the same code from the token path.

## Changes

All code changes are in the **`services/seek/ldh-deployment` submodule** (ABI-CTT-Group/ldh-deployment, currently detached HEAD). Each needs a submodule branch and commit plus a pointer bump in the main repo. Both files are already mounted into the `seek` container, so no compose change is needed.

### 1. `keycloak_jwt_auth.rb`: add `KeycloakJwtAuth.provision_user`
`provision_user(sub:, email:, first_name:, last_name:, username:)` returns a `User` or `nil`. It:
- returns `nil` (no provisioning) if `email` is blank or `username` starts with `service-account-`, so client-credentials tokens such as `service-account-api` stay anonymous as today;
- takes a MySQL `GET_LOCK("seek_kc_provision_<sub>", 10)`, released in `ensure`. The `(provider, uid)` index on `identities` is not unique, so this stops two concurrent first requests from creating two users. Under the lock it re-checks `Identity.find_by(provider: 'oidc', uid: sub)` and returns that user if it now exists;
- returns `nil` and logs `[keycloak_jwt_auth] not provisioning sub=… : email already used by Person …` if `Person.where('LOWER(email) = ?', email.downcase).exists?`;
- otherwise, in one transaction inside `Seek::Permissions::Authorization.disable_authorization_checks`:
  - `Person.create!(first_name:, last_name:, email:)`
  - `User.new(login: User.unique_login(username.presence || email.split('@').first), password/confirmation: random)`, with `check_email_present = false`, `person = person`, `save!`, then `activate`
  - `Identity.create!(provider: 'oidc', uid: sub, user:)`
  - logs `[keycloak_jwt_auth] provisioned SEEK user …`.

  It reuses SEEK's own `User.unique_login` and `User#activate`, and follows what `SessionsController#create_user_from_omniauth` / `PeopleController#create` do.

`user_from_keycloak_jwt` then changes `return nil unless identity` to call `provision_user` with token claims `sub`, `email`, `given_name`, `family_name`, `preferred_username`.

### 2. `keycloak_oidc.rb`: browser path uses the same provisioner
In the existing `Rails.application.config.to_prepare` block, override `SessionsController#create_user_from_omniauth(auth)`:
- `@user = KeycloakJwtAuth.provision_user(sub: auth.uid, email: auth.info.email, first_name: auth.info.first_name, last_name: auth.info.last_name, username: auth.info.nickname)`. omniauth_openid_connect's `uid` is the `sub`, matching existing identities;
- if `@user` is set → `check_login`. Registration is complete, so the user goes straight in with no profile form;
- if `nil` → `failed_login "No SEEK account could be created for #{auth.info.email}; ask an administrator."`.

This runs only when SEEK's `omniauth_user_create` setting is on (it already is here, since first-login registration works). I'll check this during implementation and note it in the docs.

### 3. Docs (main repo)
- `docs/seek-integration.md`: replace the "Link each user's SEEK identity" hardening note and the TL;DR mapping line. SEEK now provisions the account on the first valid token or browser login. Note the email-clash refusal, the service-account skip, and that project membership is still added by an admin.
- `docs/decisions/2026-10-14-seek-jit-user-provisioning.md` (ADR, from `docs/decisions/TEMPLATE.md`): the alternatives above, the email-clash and verifyEmail risk, and the choice to leave membership out.
- `docs/artifacts/<YYYY-MM-DD-HHMMSS>-seek-jit-user-provisioning/`: sync this plan (first step after approval), plus task list and walkthrough. Use repo-relative paths only, and keep local test ops and SEEK ids out.

## Tests first (TDD)

SEEK has no test harness here, so add `services/seek/ldh-deployment/test/keycloak_provisioning_check.rb`. It's a plain-assert script run through `rails runner -` (the same stdin pattern as `util/promote-seek-admin.sh`). Every case runs inside `ActiveRecord::Base.transaction { …; raise ActiveRecord::Rollback }`, so it leaves no rows and fires no `after_commit` jobs. It exits non-zero on any failure.

Cases:
1. New sub + email → returns an activated User; `registration_complete?` is true; Person has the right names and email; `Identity(oidc, sub)` exists.
2. Same sub again → same user, row counts unchanged.
3. Email already on an existing Person (any case) → `nil`, no rows created.
4. Blank email → `nil`.
5. `service-account-api` username → `nil`.

Run (Red before step 1, Green after):
```
docker compose exec -T seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' \
  < services/seek/ldh-deployment/test/keycloak_provisioning_check.rb
```
The file isn't mounted, so it's piped through stdin. `provision_user` comes from the mounted initializer, so restart `seek` after editing (step 4).

## Apply and verify

4. `docker compose restart seek`. The initializers are read-only bind mounts, so no rebuild is needed, and `workers` doesn't load them. Confirm it's healthy and the logs show no initializer errors.
5. Re-run the check script → all PASS.
6. End-to-end with a throwaway Keycloak test user (created and deleted through the Keycloak admin API; credentials only in the scratchpad):
   - Get a token (password grant, `client_id=api`), then call `GET http://localhost/digitaltwins-api/projects`. Expect 200, and the SEEK log shows `provisioned SEEK user`. Call again: no second provisioning line.
   - Browser: log in at `/seek` as a second fresh test user. Expect to land logged in with no profile form.
   - A clash user whose email matches an existing Person: the API call stays anonymous and the log shows the refusal.
   - Cleanup: delete the test users in Keycloak and the provisioned SEEK users. Keep this out of committed walkthroughs.
7. Existing users: the admin's API calls still resolve to the same SEEK user (no duplicate). Tool registration still works for a project member.

## Not in scope
- Auto-joining projects.
- Linking existing SEEK accounts by email (admins keep using the `util/*seek*` scripts).
- Keeping SEEK names/emails in step with later Keycloak profile edits.
