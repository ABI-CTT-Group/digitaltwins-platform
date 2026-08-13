# Platform ↔ SEEK: authentication, access, and visibility

How the DigitalTWINS platform talks to SEEK, what that connection is allowed to
see, and how SEEK's own visibility model gates (or doesn't) different callers.
Written for anyone reasoning about **who can see what** — especially in a
locked-down / airgapped deployment.

## TL;DR

- The platform authenticates to SEEK with a **single bearer token**
  (`SEEK_API_TOKEN`) — no username/password.
- That token is a personal API token **minted for the SEEK `admin` user**, so
  every platform→SEEK request runs with **admin permissions**: it can read (and
  write) **all** SEEK data, public *and* private. SEEK's per-item sharing does
  **not** restrict the platform path.
- SEEK's per-item visibility **does** gate the **SEEK web UI** directly: private
  items are not visible to an anonymous (logged-out) visitor at `/seek`.
- Net: making items private stops the *world* from browsing them at `/seek`, but
  anyone who gets into the *portal* rides the admin token's full visibility — so
  the portal's own logic, not SEEK, is the access-control boundary there.

## How the platform authenticates to SEEK

The API's SEEK client sends only a bearer token — no credentials:

```python
# services/api/digitaltwins-api/src/digitaltwins/seek/querier.py
self._api_token = os.getenv("SEEK_API_TOKEN")
...
"Authorization": "Bearer " + self._api_token
```

`SEEK_API_TOKEN` is minted by `util/generate-token.sh`, which creates a SEEK
`ApiToken` **owned by a SEEK user — `admin` by default** (the buildout calls it
as `generate-token.sh admin`):

```ruby
user  = User.find_by(login: "admin")
token = ApiToken.new(user: user, title: "API token")
```

A SEEK API token authenticates **as its owning user**, so it is self-identifying
(that's why no username/password is needed) and it carries that user's
permissions. This is a **service-account** credential, entirely separate from the
portal's own Keycloak user login.

## What the token grants

Because the token belongs to `admin` (a SEEK **server admin**), the platform's
SEEK requests have **full visibility of every item** — regardless of
public/private/sharing — and **read *and* write**. SEEK applies the owning user's
permissions, and the admin's permission is "everything."

So: **the platform is not limited to public data. It sees all of SEEK.** SEEK's
per-item permissions are not a gate on this path.

## Three callers, three scopes

| Caller | How they auth | What they can see |
|---|---|---|
| **Anonymous** (logged-out browser at `/seek`) | nothing | only **SEEK-public** items (none, if everything is private) |
| **SEEK user** (login at `/seek`) | SEEK account | that user's **SEEK permissions** — public + own + shared-with-them |
| **Platform user** (login at `/` via Keycloak) | Keycloak → backend queries SEEK **as admin** | whatever the **portal chooses to surface** — the backend can retrieve *all* SEEK data; the gate is portal logic, not SEEK |

The key asymmetry: a **platform** login is potentially **broader** than a **SEEK**
login, because the backend uses the admin token, not the logged-in user's SEEK
identity. Anyone who can reach the portal effectively inherits admin-level SEEK
visibility, filtered only by what the portal decides to show.

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

- **The service token is admin-broad.** If the portal only needs public/shared
  items, consider minting `SEEK_API_TOKEN` for a **non-admin** SEEK user with a
  narrower share scope instead of `admin` — at the cost of not seeing
  legitimately-private items the portal may need. Deliberate trade-off.
- **Treat `SEEK_API_TOKEN` as an admin credential** — it is one. Protect and
  rotate it like any other secret in `secrets.env`.
- **Default new items to private** so a study isn't inadvertently made public by
  accepting a default sharing policy. (Check the actual current default on the
  box — see below.)
- **After a `portal-restore`**, SEEK's user DB is the *source's* — that includes
  the source's public/private choices and its user accounts. Review the imported
  sharing state (and prune source users) rather than assuming your local posture.

## Where the pieces live

| Piece | Location |
|---|---|
| Token minted (as `admin`) | `util/generate-token.sh` |
| Token used (bearer, read/write) | `services/api/digitaltwins-api/src/digitaltwins/seek/querier.py` |
| Token stored | `SEEK_API_TOKEN` in `secrets.env` → rendered into `.env` |
| SEEK admin created | `util/create-admin-user.sh`; reset with `util/set-seek-password.sh` |
| `/seek` gateway route | passthrough — see gateway-routes table in `util/README.md` |

## Checking the actual posture on a box

The theoretical model above is fixed; the *current* sharing/anonymous settings
live in SEEK's runtime config, so verify them on the box:

```
# Default access granted to "all visitors" (public) on NEW items.
# 0 = no access (private by default); higher = view/download/edit/manage.
docker compose exec seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner "puts Seek::Config.default_all_visitors_access_type"'
```

Ground-truth test — request a SEEK listing **without authenticating** and see
whether any data comes back (this is exactly what the world sees):

```
curl -s -o /dev/null -w '%{http_code}\n' https://<domain>/seek/programmes
curl -s -H 'Accept: application/json' https://<domain>/seek/projects | head -c 400
```

Empty / redirect-to-login = private; a populated list = world-visible.
