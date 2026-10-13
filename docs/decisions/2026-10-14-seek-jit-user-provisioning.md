# Provision SEEK accounts just-in-time from Keycloak identity

- **Date:** 2026-10-14
- **Status:** Accepted

## Context

The platform calls SEEK as the end user by forwarding their Keycloak JWT. SEEK's `keycloak_jwt_auth.rb` maps the token's `sub` to a SEEK user through the `identities` table. That row used to be created only when the person signed into the `/seek` UI with "Sign in with Keycloak" and then filled in SEEK's "create your profile" form.

Until they did, the API's calls ran as **anonymous**. Reads returned only public items, and writes (tool/workflow registration, SOP creation) failed. Nothing told the user why. The Keycloak realm has `registrationAllowed: false` (admins create users) and `verifyEmail: false`.

## Alternatives Considered

### Option A: Provision in the API
- Pros: Python, next to the code that sees the failure.
- Cons: SEEK's REST API cannot create identities. It would also need a SEEK admin credential, which brings back the global `SEEK_API_TOKEN` that was removed on purpose.

### Option B: Batch sync script (Keycloak users → SEEK)
- Pros: Simple; admins can run it at will.
- Cons: Users created after the last run are still broken until someone runs it again.

### Option C: Keycloak event listener
- Pros: Provisions at Keycloak user creation.
- Cons: Needs a custom Java SPI deployed into Keycloak, plus a privileged channel into SEEK. Heavy for what it does.

### Option D: Just-in-time provisioning inside SEEK
- Pros: Covers every user on first contact, with no extra credentials or services. SEEK already creates a User + Identity on OIDC login when `omniauth_user_create` is on, so this only extends that to create the Person too. One provisioner serves both the token path and the browser path.
- Cons: More logic in the monkey-patched initializers we carry on top of the upstream `ldh` image.

## Decision

Option D. `KeycloakJwtAuth.provision_user` (in `services/seek/ldh-deployment/keycloak_jwt_auth.rb`) creates an active User, a Person (from the token's `given_name`, `family_name`, `email`) and the `identities` row. It runs:
- from `user_from_keycloak_jwt` when no identity matches, and
- from an override of `SessionsController#create_user_from_omniauth` (in `keycloak_oidc.rb`) on first browser login.

A per-`sub` MySQL `GET_LOCK` serialises concurrent first requests, because the `(provider, uid)` index on `identities` is not unique.

It refuses to provision, and the caller stays anonymous, when:
- **The email already belongs to a SEEK Person.** Because the realm does not verify emails, linking by email would let a Keycloak user with a chosen email take over someone else's SEEK account. Refusing and logging leaves the decision to an admin.
- **The token has no email, or comes from a `service-account-*` user.** Machine tokens should not create people.

Project membership is deliberately **not** provisioned. Who may write into which project stays an admin decision (`util/add-seek-project-member.sh`).

## Consequences

- Platform users work against SEEK as themselves from their first API call or `/seek` visit. Nobody sees SEEK's profile form.
- A new user can still only write into projects an admin has added them to. A missing membership now shows up as a permission error, not as silent anonymity.
- An email clash leaves that user anonymous until an admin resolves it. Grep the SEEK log for `Not provisioning`.
- SEEK names and emails are taken once, at provisioning time. Later Keycloak profile edits are not synced.
- Upgrading the `ldh` image means re-checking the patched internals: `AuthenticatedSystem#current_user`, `SessionsController#create_user_from_omniauth`, `User.unique_login`, `User#activate`. `services/seek/ldh-deployment/test/keycloak_provisioning_check.rb` covers the provisioner itself.
