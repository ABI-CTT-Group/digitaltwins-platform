# Platform ↔ SEEK: authentication, access, and visibility

How the DigitalTWINS platform talks to SEEK, what that connection is allowed to
see, and how SEEK's own visibility model gates (or doesn't) different callers.
Written for anyone reasoning about **who can see what** — especially in a
locked-down / airgapped deployment.

## TL;DR

- The platform authenticates to SEEK using **Keycloak-issued JWT Bearer tokens**.
- When a user interacts with the portal, the API forwards the user's Keycloak JWT to SEEK on a per-request basis.
- SEEK intercepts these tokens via a custom initializer (`keycloak_jwt_auth.rb`), cryptographically verifies them against Keycloak's JWKS endpoint, and maps the token's `sub` UUID to a specific SEEK user via the `identities` table. A Keycloak user SEEK has not seen yet gets a SEEK account created on the spot (see [Account provisioning](#account-provisioning)).
- Therefore, every platform→SEEK request runs **as the authenticated user** and sees exactly that user's **authorized view**: public items + items shared with them + items in their projects + what they own. 
- The legacy global `SEEK_API_TOKEN` singleton has been completely removed to prevent unauthorized cross-tenant data access.

## How the platform authenticates to SEEK

The API's SEEK client extracts the Keycloak token from the caller and dynamically injects it into every downstream SEEK request:

```python
# services/api/src/digitaltwins/seek/querier.py
self._api_token = api_token # Injected via Depends(get_querier)
...
"Authorization": "Bearer " + self._api_token
```

On the SEEK side, the request is intercepted before hitting Rails controllers. We monkey-patch the `AuthenticatedSystem` module to decode and verify the JWT signature against the Keycloak JWKS public keys. 

If valid, SEEK looks up the Keycloak UUID (`sub`) in the `identities` table (where `provider: 'oidc'`). If a match is found, the request executes as that SEEK user. If not, SEEK provisions the account first (below) and then runs the request as the new user.

## Account provisioning

There is no batch Keycloak→SEEK sync. SEEK creates the account the first time it sees a Keycloak user, whichever path comes first:

- an API call carrying the user's JWT (`keycloak_jwt_auth.rb`, `KeycloakJwtAuth.provision_user`), or
- the user's first "Sign in with Keycloak" at `/seek` (`keycloak_oidc.rb` overrides `SessionsController#create_user_from_omniauth` to call the same provisioner).

It creates an active SEEK User, a Person (name and email from the token's `given_name`, `family_name`, `email`) and the `identities` row (`provider: 'oidc'`, `uid: <sub>`), so nobody sees SEEK's "create your profile" form. The browser path relies on SEEK's admin setting *omniauth user create* being on.

It deliberately does **not** provision when:

- **The email already belongs to a SEEK Person** (case-insensitive), e.g. a local SEEK account or an admin-created profile. It never links by email: the realm does not verify emails, so that would let one Keycloak user take over another's SEEK account. The call stays anonymous, the browser login is refused, and SEEK logs `Not provisioning sub=…: email already used by Person <id>`. An admin resolves it with the `util/*seek*` scripts.
- **The token has no email**, or **`preferred_username` starts with `service-account-`** (client-credentials tokens). These stay anonymous, as before.

Provisioning gives an account, not access: **project membership is still an admin action** (`util/add-seek-project-member.sh`). A new user can read public items and own what they create, but can only register tools/workflows into projects they have been added to.

## What the token grants

Because every request executes as the caller's specific SEEK user, the platform is strictly bound by SEEK's internal sharing and permission models.

A user will only see:
- Items marked as Public.
- Items explicitly shared with their SEEK user account.
- Items belonging to Projects they are a member of.
- Items they have personally created/owned.

## Three callers, three scopes

| Caller | How they auth | What they can see |
|---|---|---|
| **Anonymous** (logged-out browser at `/seek`) | nothing | only **SEEK-public** items (none, if everything is private) |
| **SEEK user** (login at `/seek`) | SEEK account | that user's **SEEK permissions** — public + own + shared-with-them |
| **Platform user** (login at `/` via Keycloak) | Keycloak → backend queries SEEK **forwarding the JWT** | **Exactly the same** as if they were logged into the SEEK UI directly. |

## SEEK-UI visibility (the anonymous / world case)

SEEK enforces its own per-item sharing at its web UI, independent of the platform:

- **Private items are not anonymously browsable.** A logged-out visitor to
  `/seek` sees only items shared publicly. If nothing is public, they see nothing
  — no projects, studies, or assays.
- Two extra levers for defense-in-depth:
  1. **SEEK's server-level anonymous-access setting** — whether logged-out users
     may view public content at all.
  2. **The gateway.** `/seek` is currently an nginx **passthrough** (no auth at
     the edge — see the gateway-routes table in `util/README.md`), so SEEK itself
     is the only gate. A locked-down deployment could additionally restrict
     `/seek` at the network/gateway layer.

## Hardening notes for a secure / airgapped deployment

- **Watch for provisioning refusals:** a user whose email clashes with an existing SEEK Person stays anonymous until an admin resolves it (see [Account provisioning](#account-provisioning)). Grep the SEEK log for `Not provisioning`.
- **Default new items to private** so a study isn't inadvertently made public by
  accepting a default sharing policy.
- **After a `portal-restore`**, SEEK's user DB is the *source's* — that includes
  the source's public/private choices and its user accounts. Review the imported
  sharing state (and prune source users) rather than assuming your local posture.

## Where the pieces live

| Piece | Location |
|---|---|
| SEEK JWT Auth Interceptor + account provisioning | `services/seek/ldh-deployment/keycloak_jwt_auth.rb` |
| SEEK browser OIDC login (uses the same provisioner) | `services/seek/ldh-deployment/keycloak_oidc.rb` |
| Provisioning check script | `services/seek/ldh-deployment/test/keycloak_provisioning_check.rb` |
| Token forwarded (bearer) | `services/api/src/digitaltwins/seek/querier.py` |
| API Dependency Injection | `services/api/app/routers/dependencies.py` (`get_querier`) |
| `/seek` gateway route | passthrough — see gateway-routes table in `util/README.md` |
