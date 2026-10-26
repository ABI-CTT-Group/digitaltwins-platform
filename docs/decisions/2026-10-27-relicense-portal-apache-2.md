# Relicense the portal under Apache 2.0

- **Date:** 2026-10-27
- **Status:** Accepted

## Context

The repository is licensed under the Apache License 2.0 (root `LICENSE`), and the
README presents the whole platform as Apache 2.0. `services/portal/LICENSE`, added
in 2025-03 when the portal was its own repository, is Creative Commons
Attribution-NonCommercial 4.0 (CC BY-NC 4.0). Since the portal was absorbed into this
repository (PR #322), one tree has carried two licenses. CC BY-NC is a licence for
creative content, not software. It forbids commercial use, which conflicts with the
platform's aim of supporting clinical translation via commercialisation, and it is
not compatible with Apache 2.0 for combined distribution.

The project team confirmed that the CC BY-NC licence on the portal was a mistake.

## Alternatives Considered

### Option A: Relicense the portal under Apache 2.0
- Pros: one licence for the whole repository; the README statement becomes true; no
  barrier to commercial use or to combining portal and platform code.
- Cons: needs the agreement of the portal's copyright holders. Code already
  distributed under CC BY-NC stays available under those terms to whoever received it.

### Option B: Keep CC BY-NC and document the exception
- Pros: no licensing change.
- Cons: two incompatible licences in one deployable product; blocks commercial use
  of the portal; the README must carry a caveat.

## Decision

Option A. `services/portal/LICENSE` is replaced with the same Apache 2.0 text as the
root `LICENSE`.

## Consequences

- The whole repository, including `services/portal`, is Apache 2.0 from this commit on.
- Whoever holds copyright in the portal code must agree to the change. That
  agreement is not recorded in the repository.
- Earlier commits keep the CC BY-NC text; that history is not rewritten.
