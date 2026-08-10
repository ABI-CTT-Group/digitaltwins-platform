# Resetting a box to re-install (`util/reset.sh`)

On a **VM** you start over by dropping and recreating it. On a **physical box**
(or any box you can't casually reimage) you can't — so `util/reset.sh` gives you
the equivalent: it tears the platform back down to a clean baseline so you can
re-run the install with the same procedure, **without touching `/mnt/install_src`**
(the bundle, `data/`, certs all survive).

> ⚠️ **Untested as shipped, and destructive.** Always `--dry-run` first and read
> what it will do. It wipes all platform data.

## Run it from the bundle, not the runtime
reset.sh deletes the runtime repo copy (`~/digitaltwins-platform`). Run it from the
**bundle** copy so it isn't deleting itself:
```
sudo /mnt/install_src/clean_src/digitaltwins-platform/util/reset.sh --dry-run
```
(It refuses to run if launched from inside the runtime dir.)

## Tiers (cumulative)

| `--level`  | What it does | Preserved | When |
|---|---|---|---|
| `platform` (default) | Stop + remove the stack and **all data volumes** (SEEK/PG/MinIO/Keycloak), remove the `digitaltwins-platform`/`-worker` systemd units, delete the runtime repo copy. | docker engine, apt state, images, bundle | Re-run a clean install from the deploy stage; data is disposable. |
| `apt` | Everything above **plus** repair the apt/pip damage a bundle `dpkg -i *.deb` leaves behind (half-configured certbot, python3.12 version skew). | docker engine, images, bundle | apt is wedged (the classic "unmet deps / not-going-to-be-installed" mess). **Needs the box ONLINE once.** |
| `bare` | Everything above **plus** prune all docker images/volumes, remove the docker engine, `ufw --force reset`, wipe `/etc/letsencrypt`. | bundle only | You want as close to a fresh VM as you can get without reimaging. |

## Usage
```
# preview (always do this first)
sudo /mnt/install_src/clean_src/digitaltwins-platform/util/reset.sh --level apt --dry-run

# do it (prompts you to type the hostname to confirm)
sudo .../util/reset.sh --level apt

# non-interactive (e.g. scripted)
sudo .../util/reset.sh --level platform --yes
```
Override the runtime location if it isn't `~/digitaltwins-platform`:
`--runtime /path/to/runtime` (or `RUNTIME_DIR=…`).

## Safety rules baked in
- **Confirmation-gated** — type the hostname, or pass `--yes`.
- **`--dry-run`** prints every action and changes nothing.
- **Never removes system Python.** The apt repair *re-aligns* `python3.12*` to the
  archive version; it never `purge`s `python3` / `python3-minimal` /
  `python3.12-minimal` (that bricks Ubuntu). Only the platform-added packages
  (`certbot`, `python3-acme`, `python3-certbot`) are purged.
- **Never touches `/mnt/install_src`.**
- **Idempotent / best-effort** — safe to re-run; each step tolerates "already gone".

## Why the `apt` tier exists (the root cause it undoes)
The apt mess comes from installing the airgap bundle with `dpkg -i apt-debs/*.deb`,
which (a) can't resolve certbot's deps (leaving `iU` half-configured packages) and
(b) unpacks the bundle's `python3.12` debs when they're a *different point-release*
than the box's, jamming the whole apt resolver.

**Prevention (so you don't need the `apt` tier next time):** on re-install don't
`dpkg -i *.deb` — use `util/install-apt-debs.sh` (treats `apt-debs/` as a local apt
repo so deps resolve), or just `apt-get install …` when the box is online. And note
an airgapped box never needs certbot at all — it can't reach Let's Encrypt; issue
the cert on a reachable box and drop it into `data/`.

## After a reset
- **`platform`** → re-render `.env` (`util/gen-env.sh`), `util/sync-runtime.sh`,
  bring the stack up (or enable the systemd unit). See [`README.md`](README.md).
- **`apt`** → same, on repaired apt. (`certbot` is intentionally gone; that's fine.)
- **`bare`** → start from the top of [`README.md`](README.md) (step 2 reinstalls docker).

Companion docs: [`README.md`](README.md) (install), [`INSTALL-BUNDLE.md`](INSTALL-BUNDLE.md)
(the `/mnt/install_src` bundle), [`diagnostics.md`](diagnostics.md).
