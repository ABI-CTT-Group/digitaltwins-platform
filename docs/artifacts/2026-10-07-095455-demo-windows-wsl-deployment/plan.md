# Plan — Windows (WSL2) deployment guide for the DigitalTWINS demo

## Context

The demo bundle in `my_workspace/archive/demo/` (gitignored; was `Projects/archive` at plan time) ships with
`DEPLOYMENT.md` (Ubuntu 24.04, `http://localhost`) and `DEPLOYMENT-DOMAIN.md` (Ubuntu +
domain/https). The user wants to run the same demo on a **Windows PC**, reached at
`http://localhost` on that PC, and asked for a **separate Windows instruction file**.

**Answer to "can it be deployed on Windows?": yes, inside WSL2 running Ubuntu 24.04, with
the shipped installer essentially unchanged.** Exploration of the bundle showed:

- All Linux assumptions live in the *host-setup* steps, not the containers: Ubuntu 24.04
  `.deb`s (`install_src/airgap/apt-debs`), static Docker 29.4 binaries started by a systemd
  `docker.service` (`util/airgap_build_step2.yml`), rsync via `ansible.posix.synchronize`,
  a `digitaltwins-platform.service` systemd unit for boot persistence, and the hard-coded
  `/mnt/install_src` path (`util/airgap_build_step3.yml:47`).
- Containers need a *native Linux* Docker engine semantics: `/var/run/docker.sock` mounts
  (portal-backend, jupyterhub), `host-gateway` (SEEK → gateway), Airflow `chown` by host
  UID on bind mounts. All behave like Ubuntu under a WSL-internal engine; Docker Desktop
  changes `host-gateway` resolution and would shadow the installer's `docker` binary.
- `install_src.zip` (7.4 GB) preserves Unix permissions (`unx`, exec bits on `*.sh`), has a
  single top-level `install_src/` folder, and the shipped airflow compose already has the
  NVIDIA GPU reservation commented out. So unzipping inside WSL and symlinking to
  `/mnt/install_src` reproduces the Ubuntu "folder already on the server" path exactly.
- Nothing in the installer touches sysctl, `/etc/hosts`, iptables or `/opt`; `airgap.sh`
  (ufw) is optional and not applicable on WSL.

**Decisions from the interview** (user answers):

| Question | Answer |
|---|---|
| Target machine | WSL already installed; specs to be stated in the guide |
| Internet | Normal internet available during setup |
| Docker | User undecided → **reviewed: plain Docker Engine inside WSL** (installer parity, docker.sock / host-gateway / UID semantics, no licence). Guide tells the reader to quit / disable Docker Desktop WSL integration if present |
| Install files | `install_src.zip` copied to the PC |
| Doc shape | **Self-contained** guide, like `DEPLOYMENT-DOMAIN.md` |
| Audience | Same beginner audience as `DEPLOYMENT.md` |
| Side edits | User asked for recommendation → **do both** one-line pointers |
| Testing | **Mark "not yet test-run on Windows"**; user tests on the PC and feeds back |

No ADR: this is a deployment-docs choice for the demo bundle (archive folder), not a
platform architecture change. The WSL-engine-vs-Docker-Desktop-vs-VM rationale is recorded
in the guide's collapsed admin notes and in the artifact plan.

---

## Deliverables

### 1. New file: `demo/DEPLOYMENT-WINDOWS.md` (archive repo)

Self-contained beginner guide in the exact voice/format of `DEPLOYMENT.md`: numbered steps,
one command box per step, "✅ Success:" line after each, durations, a troubleshooting table,
and a collapsed `<details>` "Technical notes (for administrators)" block. Where a step is
unchanged from Ubuntu, **copy the command box verbatim** from `DEPLOYMENT.md` (so the two
guides can be diffed later).

Top of file: a callout **"This guide has not yet been test-run on a Windows PC. If a step
does not match what you see, note it and tell the person who gave you the files."**

**Before you start**

- Windows 11, or Windows 10 22H2 (build 19045+), 64-bit, with virtualisation enabled.
- Memory: the platform needs 16 GB *inside* WSL, so the PC should have **32 GB** (24 GB
  minimum; WSL defaults to half the host RAM, fixed in step A2).
- Disk: **70 GB free on `C:`** (zip 7.5 + extracted 7.5 + ~30 GB images + data; the zip can
  be deleted after extraction).
- Local administrator account; internet access; `install_src.zip`.
- Same "keep the files safe — `install_src/data/secrets.env` is the only copy" warning.
- "Your sudo password" = the password chosen when Ubuntu was first launched in WSL.

**Part A — on Windows (PowerShell "Run as administrator")**

| Step | Content | Success check |
|---|---|---|
| A1 Check WSL and install Ubuntu 24.04 | `wsl --version` (WSL 2.x; `wsl --update` if older), `wsl -l -v`, `wsl --install -d Ubuntu-24.04`; first launch creates the Linux username/password | `wsl -l -v` shows `Ubuntu-24.04` with `VERSION 2` |
| A2 Give WSL enough memory | Create `%UserProfile%\.wslconfig` with `[wsl2]` `memory=20GB` `swap=8GB` (table of values for 24/32/64 GB hosts), then `wsl --shutdown` | inside Ubuntu `free -g` shows ≥ 20 total |
| A3 Turn on systemd in Ubuntu | inside Ubuntu: write `/etc/wsl.conf` with `[boot]` `systemd=true`; from PowerShell `wsl --shutdown`; reopen | `systemctl is-system-running` prints `running` or `degraded` |
| A4 Make sure port 80 is free on Windows | `Get-NetTCPConnection -LocalPort 80 -State Listen` expect nothing; if IIS owns it: `Stop-Service W3SVC; Set-Service W3SVC -StartupType Disabled`; also mention 443 and 8000–8018 | command prints nothing |
| A5 Docker Desktop check | If Docker Desktop is installed: quit it and turn off *Settings → Resources → WSL integration* for `Ubuntu-24.04` (or uninstall). Inside Ubuntu `which docker` must print nothing before Part B step 3 | `which docker` prints nothing |
| A6 Stop the PC sleeping during install | Settings → System → Power → Screen and sleep → Never (install takes ~1 h) | — |

**Part B — inside Ubuntu (the WSL terminal)**

| Step | Content | Notes |
|---|---|---|
| B1 Copy the install files (≈ 15 min) | `sudo apt-get update && sudo apt-get install -y unzip rsync gettext-base iptables` (online top-up: tools the Ubuntu *server* image has but the WSL image may lack — `unzip` is needed *before* step B2 can run the offline installer; `envsubst`/`iptables` are assumed by `gen-env.sh` and `dockerd`); explain `C:\Users\you\Downloads` → `/mnt/c/Users/you/Downloads`; `unzip -q /mnt/c/Users/<you>/Downloads/install_src.zip -d ~` (extract onto the Linux disk, **not** `/mnt/c`: speed + permissions); `sudo ln -sfn ~/install_src /mnt/install_src`; `ls /mnt/install_src` | ✅ listing shows `clean_src data demo-setup.sh digitaltwins-images-all.tar.gz …` (same as Ubuntu step 1) |
| B2 Install the basic tools (≈ 2 min) | verbatim Ubuntu step 2 box | "log out and back in" becomes: close the Ubuntu window, in PowerShell `wsl --terminate Ubuntu-24.04`, reopen Ubuntu. Explain this is the WSL equivalent of logging out |
| B3 Install Docker (≈ 2 min) | verbatim Ubuntu step 3 box | then restart the distro again (docker group); ✅ `docker ps` prints an empty table and `systemctl is-active docker` prints `active` |
| B4 Install the platform (≈ 30–45 min) | verbatim Ubuntu step 4 box | same "same terminal session" warning; add "don't close the laptop lid" |
| B5 Load the demo data (≈ 5 min) | verbatim Ubuntu step 5 box | — |
| B6 Open the platform | password `grep` box verbatim; **open `http://localhost` in a Windows browser** — no SSH tunnel; WSL forwards localhost automatically | note: IP address will not work (Keycloak) |
| B7 Try the three demo assays | verbatim Ubuntu step 7 table | — |

**Day-to-day use** (new section, Windows-specific)

- After a Windows restart WSL does **not** start by itself: open the Ubuntu terminal
  (or run `wsl -d Ubuntu-24.04`), wait 2–3 min; systemd starts Docker and the platform.
- Closing the Ubuntu window is fine (systemd keeps the distro running);
  `wsl --shutdown` stops everything.
- After sleep/hibernate `http://localhost` may stop answering → `wsl --shutdown`, reopen
  Ubuntu, wait 2–3 min.
- `cd ~/digitaltwins-platform && docker compose ps` to see service state.

**If something goes wrong** — table with Windows rows first, then the still-relevant Ubuntu
rows copied verbatim:

| Problem | What to do |
|---|---|
| `wsl --install` complains about virtualisation / "Virtual Machine Platform" | Enable virtualisation in BIOS/UEFI; `Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform`; reboot |
| `System has not been booted with systemd` | `/etc/wsl.conf` not applied — `wsl --shutdown` from PowerShell, reopen |
| `docker: command not found` after B3, or `which docker` shows `/mnt/wsl/docker-desktop/…` | Docker Desktop WSL integration is on — step A5 |
| Docker fails to start with `iptables` in the error | `sudo apt-get install -y iptables && sudo systemctl restart docker` |
| Browser: `localhost refused to connect` | Port 80 taken on Windows (A4), or WSL forwarding broke after sleep → `wsl --shutdown`, reopen |
| Containers killed / "out of memory" / very slow | `.wslconfig` memory too low (A2) |
| `No space left on device` | `C:` too full — free space; the WSL disk grows into it |
| Platform down after a Windows restart | Open the Ubuntu terminal; WSL doesn't auto-start |
| `ansible-playbook: command not found` / `permission denied … docker.sock` | you didn't restart the distro (`wsl --terminate …`) after B2 / B3 |
| `FATAL: required environment variable … is unset`, login loop, assay 41/42 rows, "anything else" | verbatim from `DEPLOYMENT.md` |

**Technical notes (collapsed)**

- Why Docker Engine inside WSL rather than Docker Desktop or a VM (parity with the shipped
  installer; docker.sock, host-gateway, UID semantics; no licence; VM = heavier, needs port
  forwarding).
- The WSL distro *is* the "server": platform in `~/digitaltwins-platform`, data in the WSL
  virtual disk; `wsl --export Ubuntu-24.04 backup.tar` to back up; `wsl --unregister
  Ubuntu-24.04` to wipe completely.
- `airgap.sh` (ufw) and `set-domain.sh` are not applicable here.
- Optional auto-start at Windows login: Task Scheduler running `wsl -d Ubuntu-24.04 --exec
  /bin/true` (one line, untested).
- Same Keycloak demo users / MinIO coupling / fixed DB passwords notes as `DEPLOYMENT.md`.

### 2. Side edits (one line each, archive repo)

- `demo/DEPLOYMENT.md:7-9` — extend the existing callout: *"Installing on a Windows PC? Use
  `DEPLOYMENT-WINDOWS.md`."*
- `demo/PREPARATION.md:7` — "Copy to the drive: `install_src/`, `DEPLOYMENT.md` and
  `DEPLOYMENT-WINDOWS.md` only."

### 3. Artifacts (working repo, per AGENTS.md)

First action after approval: create
`docs/artifacts/2026-10-07-<HHMMSS>-demo-windows-wsl-deployment/` in
this working repo and copy this plan there as `plan.md`;
after the guide is written, add `walkthrough.md` (what was verified, what remains to be
test-run on Windows). Re-sync on every update. Run `gitleaks detect --source docs/artifacts/
--no-git` before finishing. No secrets appear in any of these files (only the `grep
PLATFORM_ADMIN_PASSWORD` command, as in `DEPLOYMENT.md`).

---

## Steps

1. Create the artifact folder and sync this plan → verify: folder exists with `plan.md`.
2. Write `demo/DEPLOYMENT-WINDOWS.md` per the outline above → verify: every bash block that
   is "verbatim" matches `DEPLOYMENT.md` (`diff` of extracted blocks); every
   `install_src/...` path named in the guide exists in `install_src.zip`
   (`unzip -Z1 install_src.zip | grep`); `bash -n` on extracted bash blocks.
3. Make the two side edits → verify: `grep -n WINDOWS demo/DEPLOYMENT.md demo/PREPARATION.md`.
4. Write `walkthrough.md`, sync artifacts, `gitleaks detect` on `docs/artifacts/` and on the
   new guide → verify: no leaks.
5. Hand over: the user runs the guide on the Windows PC and reports mismatches; fix the guide
   and re-sync.

## Verification

- Not possible here: executing the guide on Windows. The guide carries the "not yet
  test-run" callout; the user tests.
- Possible here: path existence in the zip, verbatim-block diff against `DEPLOYMENT.md`,
  `bash -n` on bash blocks, markdown renders (headings/tables), gitleaks clean.

## Out of scope

- Changing anything in `install_src/` (installer, compose, scripts). The whole point is
  that the shipped bundle runs unchanged under WSL.
- Docker Desktop or Hyper-V/VirtualBox variants; a domain/https variant on Windows.
- Committing: nothing is committed unless asked (the demo folder is in the archive repo;
  artifacts go to the working repo per AGENTS.md).
