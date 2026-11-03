# Log registration errors centrally, plus a milestone line per step

- **Date:** 2026-11-04
- **Status:** Accepted

## Context

A registration takes a dataset of any category (tool, workflow, measurement, model) from its first
upload request until it is committed and its FHIR push has finished. It can fail in the portal, the
builder or the API, and the reason is usually lost:

- The backends raise `HTTPException` with a useful `detail`, but the container log shows only
  uvicorn's access line with the status code.
- The API sets up no logging, so its own INFO lines are dropped.
- The portal shows toasts but doesn't log failed requests, and some calls swallow errors.

Operators debugging a registration have nothing to go on beyond a status code.

## Alternatives Considered

### Option A: log at each raise site and each catch site
- Pros: each message can carry context specific to its endpoint.
- Cons: about 100 `raise HTTPException` sites across the builder and API, and about 40 catch sites in
  the portal. New endpoints are easy to forget, the format drifts, and the diff is large.

### Option B: one hook per layer, plus explicit step milestones
- One FastAPI exception handler each in the builder and the API logs every `HTTPException` and
  validation error, then calls the default handler.
- One axios response interceptor in the portal logs every request that finally fails.
- Explicit INFO lines only at the step boundaries of each registration.
- Pros: small diff; new endpoints are covered automatically; one log format.
- Cons: generic messages (method, path, status, detail); expected 4xx responses are logged too.

### Option C: send browser errors to a backend log endpoint
- Pros: all errors in one place (container logs).
- Cons: a new authenticated endpoint that needs size and rate limits.

### Request or correlation ids across portal → builder → API
- Rejected for now: needs header plumbing in every client and middleware in both backends. The
  milestone lines log the ids that join the steps (build id, upload id, dataset uuid), which is enough
  to follow one registration with grep.

## Decision

Option B, with these rules:

- **Severity** is the same in both layers: a 4xx is a warning (`WARNING`, `console.warn`), and a 5xx
  or network failure is an error (`ERROR`, `console.error`). 404 gets no special case, and repeated
  failures (for example, while polling) are not deduplicated.
- **Milestones** use one grep-able form: `Registration <category> <step>: key=value ...`, where
  `<category>` is one of the four dataset categories.
- **The user** appears as `user=<preferred_username>` (never email) on milestones raised in a request.
  Milestones raised in background jobs (build finished, handoff, commit, FHIR push done) carry ids
  only.
- **Error lines** carry method, path (no query string), status and detail.
- **Browser-only errors** (CWL load and parse in the annotation step) get explicit `console.error`
  calls and are shown on the page; they are not sent to the backend.
- **The API** gains a root logging setup so its existing and new INFO lines appear.

## Consequences

- Every rejected request now writes a WARNING line. Expected 4xx responses, such as a 404 for an
  annotation draft that doesn't exist yet, add some noise. If that becomes a problem, drop 404 to INFO
  in the handler.
- Responses don't change; the handlers delegate to FastAPI's defaults.
- Usernames now appear in container logs, so log retention and access follow the same rules as other
  personal data. The builder's PAT-masking filter still applies. The API has no masking filter, so its
  error details must not contain secrets, as today.
- `docker logs <service> | grep Registration` gives one registration's trail per service. Joining
  the builder and API trails is done through the logged ids.
