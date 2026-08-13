# Platform ↔ SEEK: authentication, access, and visibility

How the DigitalTWINS platform talks to SEEK, what that connection is allowed to
see, and how SEEK's own visibility model gates (or doesn't) different callers.
Written for anyone reasoning about **who can see what** — especially in a
locked-down / airgapped deployment.

## TL;DR

- The platform authenticates to SEEK with a **single bearer token**
  (`SEEK_API_TOKEN`) — no username/password.
- That token is a personal API token **minted for the SEEK `admin` user**, so
  every platform→SEEK request runs **as that user** and sees that user's
  **authorized view**: public items + items shared with them + items in their
  projects + what they own. (Not an anonymous or read-only client.)
- **Whether a SEEK *server-admin* can read *other* users' private items is not
  assumed here** — SEEK's admin-vs-sharing behaviour is version-dependent; verify
  it on your instance (see "Checking the actual posture on a box"). On our
  deployments today, all research content is owned by the token's admin user, so
  the platform sees all of it — because it *owns* it, not because admin is a data
  superuser.
- SEEK's per-item visibility **does** gate the **SEEK web UI**: private items are
  not visible to an anonymous (logged-out) visitor at `/seek`.
- Net: making items private stops the *world* from browsing them at `/seek`. What
  the *platform* can surface is bounded by both what the token's SEEK user is
  authorized to see **and** the portal's own logic.

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

A SEEK API token acts with **its owning user's permissions**. The platform's token
belongs to the SEEK `admin` user, so it can read (and write) everything **that
user** is authorized for: public items + items shared with them + items in their
projects + items they own.

The token owner being a **server admin** does **not**, on its own, establish that
it can read *other* users' private items. Authorization for research assets is
driven by each item's **sharing policy**, and whether server-admin status bypasses
that policy for *viewing* is version-dependent and **unverified here**. So **don't
assume the platform can see a private item that was never shared with the token's
user** — test it if it matters (below).

Empirically on our deployments, all SEEK research content is contributed by the
token's admin user, so the platform does see all of it — but that's because it
**owns** it, not because admin is a data superuser. The cross-user case (an item
private to a *different* user) is genuinely untested.

## Three callers, three scopes

| Caller | How they auth | What they can see |
|---|---|---|
| **Anonymous** (logged-out browser at `/seek`) | nothing | only **SEEK-public** items (none, if everything is private) |
| **SEEK user** (login at `/seek`) | SEEK account | that user's **SEEK permissions** — public + own + shared-with-them |
| **Platform user** (login at `/` via Keycloak) | Keycloak → backend queries SEEK **as the admin token's user** | whatever the **portal chooses to surface**, bounded by what that SEEK user is authorized to see (public + shared + own/projects) |

The key asymmetry: a **platform** login is decoupled from the caller's own SEEK
identity — the backend always queries as the token's user, not as the person
logged into the portal. So what a portal user sees is gated by the **portal's**
logic on top of the token user's authorized view, not by that person's own SEEK
permissions. How broad the token user's view is depends on item sharing (and, for
the cross-user case, the unverified admin-bypass question above).

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

- **The service token is the SEEK `admin` user's.** Its reach is that user's
  authorized view (and possibly more, *if* your SEEK grants server-admins a
  view-bypass — verify). To bound it tighter, mint `SEEK_API_TOKEN` for a
  **non-admin** SEEK user and share into it exactly the items the portal needs — at
  the cost of the portal not seeing anything that user isn't shared into.
  Deliberate trade-off.
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

The model above is fixed; the *current* posture (sharing defaults, what's public,
who owns what) is runtime state — verify it. Use `jq '.data | length'` for the
counts, **not** `head -c` (byte-truncation can hide entries or mangle the JSON).

**1. What the world sees (anonymous).** Hit each listing with no auth:
```
for kind in programmes projects investigations studies assays; do
  n=$(curl -s -H 'Accept: application/json' https://<domain>/seek/$kind | jq '.data | length')
  echo "$kind: $n"
done
```
`0` = private (good, for research assets). Note: **projects/programmes are
public-by-design SEEK containers**, so a non-zero count there is expected and only
exposes their *names* — the content lives in studies/assays.

**2. What the token sees vs. what exists.** Compare the token's view to the raw DB
counts (which ignore sharing). If they match and everything is one owner's, the
"admin sees all" vs "sharing gates it" question stays unresolved — you only learn
the difference when a *second* user has private items:
```
# raw counts (all items, unfiltered by sharing):
docker compose exec seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner "puts %(studies=#{Study.count} assays=#{Assay.count} investigations=#{Investigation.count})"'
# who owns the studies:
docker compose exec seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner "Study.all.each { |s| puts %(#{s.id}\t#{s.title}\t#{s.contributor&.name}) }"'
# what the token actually returns:
curl -s -H 'Accept: application/json' -H "Authorization: Bearer $SEEK_API_TOKEN" https://<domain>/seek/studies | jq '.data | length'
```

**3. Default sharing for NEW items** (the forward-looking risk — current items
being private doesn't mean the next one will be):
```
docker compose exec seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner "puts Seek::Config.default_all_visitors_access_type"'
```
`0` = new items private-by-default; higher grants view/download/edit to anonymous.

**4. To settle the cross-user admin question** (does the admin token see *another*
user's private item?): create a private study as a **non-admin** SEEK user, then
run the token'd `/seek/studies` count above — if it appears, admin bypasses
sharing; if not, sharing gates the token too.

### Observed on `staging` (fold in your own results and date them)
- Anonymous: `studies=0`, `assays=0` → research content is **private**.
  `projects` returns the full list (names only) — expected SEEK-container behaviour.
- `Study.count`=10, all contributed by the `admin` user; token returns 10 → the
  platform sees everything **because it owns everything**. Cross-user visibility
  therefore **untested** (no non-admin-owned private items exist).
- `meta.base_url` was `http://localhost:8001` — SEEK's **Site base URL** is not set
  to the domain (fix in SEEK admin → Settings; breaks absolute links / email).
