# Platform ↔ SEEK: authentication, access, and visibility

How the DigitalTWINS platform talks to SEEK, what that connection is allowed to
see, and how SEEK's own visibility model gates (or doesn't) different callers.
Written for anyone reasoning about **who can see what** — especially in a
locked-down / airgapped deployment.

## TL;DR

- The platform authenticates to SEEK using **Keycloak-issued JWT Bearer tokens**.
- When a user interacts with the portal, the API forwards the user's Keycloak JWT to SEEK on a per-request basis.
- SEEK intercepts these tokens via a custom initializer (`keycloak_jwt_auth.rb`), cryptographically verifies them against Keycloak's JWKS endpoint, and maps the token's `sub` UUID to a specific SEEK user via the `identities` table.
- Therefore, every platform→SEEK request runs **as the authenticated user** and sees exactly that user's **authorized view**: public items + items shared with them + items in their projects + what they own. 
- The legacy global `SEEK_API_TOKEN` singleton has been completely removed to prevent unauthorized cross-tenant data access.

## How the platform authenticates to SEEK

The API's SEEK client extracts the Keycloak token from the caller and dynamically injects it into every downstream SEEK request:

```python
# services/api/digitaltwins-api/src/digitaltwins/seek/querier.py
self._api_token = api_token # Injected via Depends(get_querier)
...
"Authorization": "Bearer " + self._api_token
```

On the SEEK side, the request is intercepted before hitting Rails controllers. We monkey-patch the `AuthenticatedSystem` module to decode and verify the JWT signature against the Keycloak JWKS public keys. 

If valid, SEEK looks up the Keycloak UUID (`sub`) in the `identities` table (where `provider: 'keycloak'`). If a match is found, the request executes as that SEEK user.

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

- **Ensure Keycloak sync:** Ensure the synchronization between Keycloak and SEEK users operates correctly so that the `identities` mapping is intact. A missing mapping means the user will be treated as an anonymous caller by SEEK.
- **Default new items to private** so a study isn't inadvertently made public by
  accepting a default sharing policy.
- **After a `portal-restore`**, SEEK's user DB is the *source's* — that includes
  the source's public/private choices and its user accounts. Review the imported
  sharing state (and prune source users) rather than assuming your local posture.

## Where the pieces live

| Piece | Location |
|---|---|
| SEEK JWT Auth Interceptor | `services/seek/ldh-deployment/keycloak_jwt_auth.rb` |
| Token forwarded (bearer) | `services/api/digitaltwins-api/src/digitaltwins/seek/querier.py` |
| API Dependency Injection | `services/api/digitaltwins-api/app/routers/query.py` |
| `/seek` gateway route | passthrough — see gateway-routes table in `util/README.md` |
