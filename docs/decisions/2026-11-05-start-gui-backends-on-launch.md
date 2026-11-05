# Start a GUI tool's backend when it is launched

- **Date:** 2026-11-05
- **Status:** Accepted. Supersedes the "Backends work as for tools" bullet of [2026-10-02-build-gui-workflow-tools.md](2026-10-02-build-gui-workflow-tools.md).

## Context

A GUI tool (a standalone tool, or a gui workflow's tool) may have a backend that runs as a compose project
behind `/plugin/<expose>/`. Until now an admin ran it by hand from the Tool Hub card's menu:
Deploy backend (build the image and create the containers), then Compose up/down.

When the builder stops, it removes every backend's containers and marks them down. When it starts again,
it brings back only the backends still marked up, which is none. So after every platform restart, every
backend stays down until an admin starts each one. Launch on the Tool Hub card then refuses with
"start the backend by Compose Up first". A gui assay's Launch never checks at all: the tool opens and its
calls to `/plugin/<expose>/` fail.

## Alternatives Considered

### Option A: start the backend on launch (chosen)
- Pros: one mechanism for the Tool Hub and assay launches, and for tools never deployed; only backends that
  someone launches use host resources; restarts stay fast.
- Cons: the first launch after a restart waits a few seconds, or minutes when the build has never been deployed.

### Option B: restore running backends on builder startup
- Pros: launches are instant after a restart.
- Cons: every backend that ever ran starts on every restart, used or not; a tool never deployed still needs
  an admin; the assay launch still needs a check.

### Option C: both
- Cons: two mechanisms to keep consistent, for little gain over A.

## Decision

`/tool-view`, which both the Tool Hub and a gui assay's Launch open, asks the builder to start the backend
of the tool it is about to mount (keyed by expose name) and waits before mounting it:
- If the build's deployment is completed but not running, the builder **starts** it (`compose up -d`).
- If the build has no deployment, or its last deploy failed, the builder **deploys** it (builds the image).
- If it is running, or the tool has no backend, the tool mounts at once.
- If a start fails, the deployment is marked failed with the error shown in `/tool-view`, so the next
  launch redeploys it.

The backend is ready when the compose command has finished; there is no HTTP readiness probe.

Any signed-in user may trigger a start or first deploy this way: it only runs code already built by the
builder, for the build that Launch loads. The menu keeps "Stop backend" (admin) and View logs; Deploy backend
and Compose up are removed. Each build has exactly one deployment row, and a failed deploy's error is stored
on it.

## Consequences

- Platform restarts no longer need an admin to bring GUI tools back.
- After an admin stops a backend, the next launch by anyone starts it again. Stopping is for freeing
  resources, not for disabling a tool.
- Backends keep running once started, until stopped or the platform restarts; there is no idle timeout.
- Non-admins can now cause image builds and container starts on the host, bounded to built tools.
- A tool whose app starts slowly may see a few 502s on its first requests.
