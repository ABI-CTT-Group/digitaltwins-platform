# Walkthrough — Windows (WSL2) deployment guide for the DigitalTWINS demo

Date: 2026-10-07. Plan: `plan.md` in this folder. Files live in the gitignored `my_workspace/archive` folder (moved there from `Projects/archive` on 2026-10-07)
(`my_workspace/archive/demo/` in this working repo, not tracked);
these artifacts are the audit record per AGENTS.md.

## What was produced

| File | Change |
|---|---|
| `demo/DEPLOYMENT-WINDOWS.md` | **New.** Self-contained beginner guide: Part A (WSL setup on Windows, steps A1–A6), Part B (platform install inside Ubuntu, steps B1–B7), day-to-day use, troubleshooting table, collapsed admin notes. Carries a "not yet test-run on a Windows PC" callout. |
| `demo/DEPLOYMENT.md` | One callout line added at the top pointing Windows readers to the new guide. |
| `demo/PREPARATION.md` | "Copy to the drive" list now names `DEPLOYMENT.md`, `DEPLOYMENT-DOMAIN.md` and `DEPLOYMENT-WINDOWS.md`. (`DEPLOYMENT-DOMAIN.md` was missing from the list although `DEPLOYMENT.md` refers to it — small deviation from the plan, flagged to the user.) |

## Design decision (recorded here and in the guide's admin notes; no ADR)

Docker **Engine inside the WSL2 Ubuntu 24.04 distro**, installed by the shipped
`airgap_build_step2.yml`, rather than Docker Desktop or a Hyper-V/VirtualBox VM. Reasons:
installer parity (static binaries + systemd `docker.service`), `/var/run/docker.sock` mounts
(portal-backend, jupyterhub), SEEK's `host-gateway`, Airflow UID `chown` on bind mounts, no
licence. Docker Desktop would require bypassing steps B2–B3 and shadows the installer's
`docker` CLI; a VM is heavier and needs port forwarding.

## What differs from the Ubuntu guide

- Step 1 (drive) → B1: `unzip` into the WSL home (ext4), `ln -sfn ~/install_src /mnt/install_src`.
  Preceded by an online top-up: `unzip rsync gettext-base iptables` (unzip is needed before
  the offline apt repo is reachable; `envsubst` and `iptables` are assumed by `gen-env.sh`
  and `dockerd` and are not guaranteed in the WSL image).
- "Log out and log back in" → close window + `wsl --terminate Ubuntu-24.04`.
- New Windows prerequisites: WSL 2.x, Ubuntu-24.04 distro, `.wslconfig` memory (default is
  half of host RAM), `systemd=true` in `/etc/wsl.conf`, port 80 free on Windows, Docker
  Desktop quit / WSL integration off, sleep disabled during install.
- Step 6: no SSH tunnel; browser on the PC opens `http://localhost` (WSL localhost forwarding).
- Day-to-day: WSL does not auto-start at Windows login; sleep can break localhost forwarding.

## Verification done here (Linux dev box)

- Explored the bundle: all Linux assumptions are in host setup; no sysctl, `/etc/hosts`,
  iptables or `/opt` use; `airgap.sh` optional. Shipped airflow compose has the NVIDIA GPU
  reservation commented out (checked inside `install_src.zip`).
- `install_src.zip`: Unix permissions preserved (exec bits on `*.sh`), single top-level
  `install_src/` folder, 7 432 357 600 bytes (`ls -lh` → `7.0G`, as stated in B1).
- Every `install_src/...` path named in the guide exists in the zip (8/8).
- The five step boxes marked as unchanged (B2, B3, B4, B5, B6 password grep) are
  byte-identical to `DEPLOYMENT.md`'s bash blocks.
- `bash -n` on all 12 bash blocks: OK.
- One-shot helper service names (`airflow-init`, `minio-init`, `minio-logs-init`) checked
  against the compose files.
- gitleaks on this artifact folder and on the new guide: see final summary.

## Not verified (needs the Windows PC)

The guide has **not been executed on Windows**. Specific assumptions to confirm during the
test run:

1. Ubuntu-24.04 WSL image: whether `iptables`/`gettext-base` were already present (the
   top-up is harmless either way).
2. `systemctl is-system-running` prints `running`/`degraded` after `systemd=true`.
3. A new Ubuntu window after `wsl --terminate` picks up the `docker` group and `~/.local/bin`.
4. `dockerd` 29.4 static binary starts under the WSL2 kernel via the installer's unit.
5. `http://localhost` from a Windows browser reaches the nginx gateway on port 80.
6. The distro keeps running after the Ubuntu window is closed (systemd keeps it alive).
7. Durations (B1 unzip, B4 install) on the PC's disk.

Observation (not changed): `DEPLOYMENT.md` links to `#your-sudo-password` but has no such
section; `DEPLOYMENT-DOMAIN.md` and the new Windows guide do.
