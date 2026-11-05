# Windows 11 VM test of the WSL deployment guide — plan

> **For agentic workers:** use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> **Status:** draft, awaiting approval. Nothing below has been executed.

**Goal:** run `demo/DEPLOYMENT-WINDOWS.md` end to end, verbatim, on a real Windows 11
install, and record every mismatch, so the guide's "not yet test-run" callout can be
removed or the guide fixed.

**Approach:** a Windows 11 Enterprise evaluation VM under QEMU/KVM on the Linux dev box,
with nested virtualization so WSL2 runs inside it. The human tester drives the VM console
and follows the guide as a first-time user would. The agent prepares the host, the VM
scripts and the file transfer, and keeps the test log.

**Spec:** `docs/artifacts/2026-10-07-095455-demo-windows-wsl-deployment/walkthrough.md`,
section "Not verified (needs the Windows PC)". Guide under test:
`my_workspace/archive/demo/DEPLOYMENT-WINDOWS.md` (gitignored folder).

**Tech:** QEMU 8.2 + KVM (nested=Y), OVMF Secure Boot firmware, swtpm (TPM 2.0),
Windows 11 Enterprise 90-day evaluation ISO, WSL2 + Ubuntu 24.04.

## Host facts (checked 2026-10-07)

| Item | Value | Consequence |
|---|---|---|
| CPU | Intel Core Ultra 7 265H, 16 threads, VT-x, `kvm_intel nested=Y` | WSL2 can run inside the VM |
| `/dev/kvm` | user has rw via device ACL | no `kvm` group change needed |
| QEMU / OVMF | 8.2.2 / OVMF_CODE_4M.ms.fd + OVMF_VARS_4M.ms.fd present | Secure Boot available |
| swtpm | **not installed** | `sudo apt install swtpm swtpm-tools` needed |
| RAM | 30 GiB + 31 GiB swap | VM gets 24 GB; tests the guide's 24 GB "minimum" row |
| `/home` free | 77 GB | not enough alone; see disk budget |
| Docker data | under `~/docker` (on `/home`): images 58 GB (51 GB reclaimable), volumes 17 GB | image prune frees ~51 GB on the right disk |
| Install zips | `install_src.zip` (Oct 6 18:59) and `install_src-2.zip` (Oct 7 15:07), both 7.0 GB | need to pick one (open question 1) |

## Global constraints

- Follow the guide **verbatim**. Do not fix things silently inside the VM; every
  deviation is logged first, then worked around.
- VM files live outside the repo, in `~/vms/win11-wsl-test/`. Nothing from the VM or the
  zip is copied into the repo.
- The zip contains `install_src/data/secrets.env`. It is served to the VM on
  `127.0.0.1` only, and no secret values go into the test log (use `<REDACTED>`).
- Docker **volumes are not pruned** (they may hold local dev data).
- No `/home/<user>/...` paths in artifacts; use `~` or repo-relative paths.

## Disk budget (thin qcow2, real usage)

| Consumer | Size |
|---|---|
| Windows ISO | 6 GB |
| Windows 11 install + updates | ~25 GB |
| Zip in the VM's Downloads | 7 GB |
| WSL vhdx: unzipped bundle 7.3 GB + loaded images + restored data (guide says 70 GB free on C:) | ~45–55 GB |
| qcow2 internal snapshots (copy-on-write growth) | ~5–10 GB |
| **Total** | **~90–105 GB** |

Free after an image + build-cache prune: ~77 + 51 = ~128 GB. Enough, with ~25 GB headroom.
VM disk is created at 120 GB virtual so `C:` shows >70 GB free at the guide's prerequisite check.

## What a VM cannot prove

Record these as caveats in the final report, not as passes:

- BIOS/UEFI virtualization toggle on a real PC (the VM always has it on).
- Install durations (AHCI on qcow2 on NVMe differs from a real PC disk).
- Real laptop sleep/lid behaviour (guide step A6 and the "sleep breaks localhost" note).
- Corporate-managed PCs (group policy, antivirus scanning the WSL vhdx).

## Open questions (defaults used unless told otherwise)

1. **Which zip?** Default: `install_src-2.zip`, the newer one, served under the name
   `install_src.zip` so the guide's paths match.
2. **Docker prune scope?** Default: `docker image prune -a` + `docker builder prune -a`
   (~51 GB, images re-pullable/rebuildable). Volumes kept.
3. **Optional scenarios** (Task 7): default runs the restart and port-80/IIS scenarios;
   skips installing Docker Desktop (licence + large download) unless asked.

---

### Task 1: Prepare the host

Needs approval at execution time: both steps change system state.

- [ ] **Step 1: Install the TPM emulator**
```bash
sudo apt install -y swtpm swtpm-tools
swtpm --version
```
Expected: a `TPM emulator version 0.x` line.

- [ ] **Step 2: Free disk (images and build cache only)**
```bash
docker image prune -a -f
docker builder prune -a -f
df -h /home
```
Expected: `/home` Avail ≥ 120 GB.

- [ ] **Step 3: Create the VM folder**
```bash
mkdir -p ~/vms/win11-wsl-test/{tpm,share}
```

### Task 2: Get the Windows ISO (tester, in a browser)

The Microsoft Evaluation Center requires a short registration form, so this is manual.

- [ ] **Step 1:** download "Windows 11 Enterprise" ISO, 64-bit, English (or the tester's
  language) from the Microsoft Evaluation Center. Save it as
  `~/vms/win11-wsl-test/win11-eval.iso`.
- [ ] **Step 2: Verify it**
```bash
sha256sum ~/vms/win11-wsl-test/win11-eval.iso
```
Expected: matches the SHA-256 shown on the download page.

Enterprise evaluation is chosen because its setup allows a **local account** without a
Microsoft account ("Sign-in options → Domain join instead").

### Task 3: VM scripts, Windows install, clean snapshot

**Files** (outside the repo; copies go to this artifact folder's `scripts/` for audit):
- `~/vms/win11-wsl-test/create.sh`
- `~/vms/win11-wsl-test/run.sh`
- `~/vms/win11-wsl-test/snap.sh`

- [ ] **Step 1: Write `create.sh`**
```bash
#!/usr/bin/env bash
# One-off: blank 120 GB disk and a private copy of the Secure Boot variable store.
set -euo pipefail
VM=~/vms/win11-wsl-test
cp /usr/share/OVMF/OVMF_VARS_4M.ms.fd "$VM/OVMF_VARS.fd"
qemu-img create -f qcow2 "$VM/disk.qcow2" 120G
```

- [ ] **Step 2: Write `run.sh`**

Inbox Windows drivers only (AHCI disk, e1000e NIC, std VGA), so no virtio driver ISO is
needed. `-cpu host` passes VT-x through for WSL2.
```bash
#!/usr/bin/env bash
# Start the Windows 11 test VM. ISO=path/to.iso ./run.sh attaches the installer.
set -euo pipefail
VM=~/vms/win11-wsl-test

swtpm socket --tpm2 --tpmstate dir="$VM/tpm" \
  --ctrl type=unixio,path="$VM/tpm/sock" --daemon --terminate

CD=()
if [[ -n "${ISO:-}" ]]; then
  CD=(-drive "id=cd0,if=none,media=cdrom,readonly=on,file=$ISO"
      -device ide-cd,drive=cd0,bus=ahci.1)
fi

exec qemu-system-x86_64 \
  -name win11-wsl-test -enable-kvm \
  -machine q35,smm=on -global driver=cfi.pflash01,property=secure,value=on \
  -cpu host -smp 12,sockets=1,cores=12 -m 24G \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.ms.fd \
  -drive if=pflash,format=raw,file="$VM/OVMF_VARS.fd" \
  -chardev socket,id=chrtpm,path="$VM/tpm/sock" \
  -tpmdev emulator,id=tpm0,chardev=chrtpm -device tpm-tis,tpmdev=tpm0 \
  -device ahci,id=ahci \
  -drive id=disk0,if=none,file="$VM/disk.qcow2",format=qcow2,cache=none,aio=native,discard=unmap \
  -device ide-hd,drive=disk0,bus=ahci.0 \
  "${CD[@]}" \
  -netdev user,id=n0 -device e1000e,netdev=n0 \
  -device qemu-xhci -device usb-tablet \
  -vga std -display gtk \
  -monitor unix:"$VM/monitor.sock",server,nowait
```

- [ ] **Step 3: Write `snap.sh`** (VM must be powered off; TPM state and UEFI vars are
  saved alongside the disk snapshot, or BitLocker/Secure Boot state can mismatch on restore)
```bash
#!/usr/bin/env bash
# ./snap.sh save NAME | ./snap.sh restore NAME | ./snap.sh list
set -euo pipefail
VM=~/vms/win11-wsl-test
case "$1" in
  save)    qemu-img snapshot -c "$2" "$VM/disk.qcow2"
           cp "$VM/OVMF_VARS.fd" "$VM/OVMF_VARS.$2.fd"
           rm -rf "$VM/tpm.$2"; cp -a "$VM/tpm" "$VM/tpm.$2" ;;
  restore) qemu-img snapshot -a "$2" "$VM/disk.qcow2"
           cp "$VM/OVMF_VARS.$2.fd" "$VM/OVMF_VARS.fd"
           rm -rf "$VM/tpm"; cp -a "$VM/tpm.$2" "$VM/tpm" ;;
  list)    qemu-img snapshot -l "$VM/disk.qcow2" ;;
esac
```

- [ ] **Step 4: Check the scripts**
```bash
cd ~/vms/win11-wsl-test && chmod +x *.sh && bash -n create.sh run.sh snap.sh && shellcheck *.sh
```
Expected: no output.

- [ ] **Step 5: Create the disk and boot the installer**
```bash
cd ~/vms/win11-wsl-test && ./create.sh && ISO=$PWD/win11-eval.iso ./run.sh
```
Tester: press a key at "Press any key to boot from CD", install to the blank disk, create
a **local administrator** account. Skip all optional Microsoft sign-ins.

- [ ] **Step 6: Confirm Windows sees hardware virtualization** (PowerShell in the VM)
```powershell
(Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled
Get-Tpm | Select-Object TpmPresent, TpmReady
```
Expected: `True`, and `TpmPresent True`. If the first prints `False`, see Risk 1.

- [ ] **Step 7:** run Windows Update once to completion (the guide assumes a current
  Windows 11), shut down, then `./snap.sh save win-clean`.

### Task 4: Put the install files on the VM, as a real user would have them

- [ ] **Step 1: Serve the zip and the guide on loopback only**
```bash
cd ~/vms/win11-wsl-test/share
ln -sf "$REPO/my_workspace/archive/demo/install_src-2.zip" install_src.zip   # open question 1
ln -sf "$REPO/my_workspace/archive/demo/DEPLOYMENT-WINDOWS.md" .
sha256sum -L install_src.zip
python3 -m http.server 8765 --bind 127.0.0.1 --directory .
```
`$REPO` is the repo root. QEMU user networking maps the guest's `10.0.2.2` to the host's
`127.0.0.1`, so nothing is exposed on the LAN.

- [ ] **Step 2:** in the VM's Edge, open `http://10.0.2.2:8765/`, save `install_src.zip`
  to *Downloads*, and open `DEPLOYMENT-WINDOWS.md` in a tab. The plain QEMU display has no
  clipboard sharing, so the tester copies commands from this tab, just as a real user
  would copy from the guide on their PC.

- [ ] **Step 3: Verify the transfer** (PowerShell in the VM)
```powershell
Get-FileHash "$env:USERPROFILE\Downloads\install_src.zip" -Algorithm SHA256
```
Expected: same hash as Step 1 (case-insensitive).

- [ ] **Step 4:** stop the HTTP server, shut down the VM, `./snap.sh save win-ready`.
  This is the starting state for every guide run.

### Task 5: Run guide Part A (steps A1–A6)

- [ ] **Step 1:** boot (`./run.sh`), follow A1–A6 verbatim. Log each step in
  `test-log.md` (format below). For A2 use the **24 GB** row, `memory=18GB`.
- [ ] **Step 2:** record walkthrough assumption **2**: output of
  `systemctl is-system-running` and `free -g` after A3.
- [ ] **Step 3:** shut down the VM, `./snap.sh save part-a-done`.

### Task 6: Run guide Part B (steps B1–B7)

- [ ] **Step 1:** boot, follow B1–B7 verbatim, logging each step with wall-clock start and
  end times.
- [ ] **Step 2:** record walkthrough assumptions while passing through:
  - **1** (B1/B2): before the top-up, run `dpkg -s iptables gettext-base 2>&1 | grep -E '^(Package|Status)'`.
  - **3** (after B2/B3 restarts): `id -nG | grep -w docker` and `echo $PATH | tr : '\n' | grep .local/bin`.
  - **4** (B3/B4): `systemctl is-active docker` and `docker version --format '{{.Server.Version}}'`.
  - **5** (B6): `http://localhost` loads the platform login page in **Edge on Windows**.
  - **7**: B1 unzip and B4 install durations (VM caveat applies).
- [ ] **Step 3:** B7: all three demo assays complete in the Windows browser. Note that
  one notebook needs internet; the VM has it via QEMU user networking.
- [ ] **Step 4:** shut down, `./snap.sh save part-b-done`.

### Task 7: Day-to-day section and failure paths

Each scenario starts from `part-b-done` (restore before each), except where stated.

- [ ] **Assumption 6:** close every Ubuntu window, wait 2 min, then in PowerShell
  `wsl -l -v` shows `Ubuntu-24.04  Running`, and `http://localhost` still loads.
- [ ] **Restart:** reboot Windows, then follow the guide's "After the PC restarts"
  instructions exactly. Expected: platform back at `http://localhost`.
- [ ] **`wsl --shutdown`:** follow the guide's stop/start instructions. Same expectation.
- [ ] **Port 80 taken (step A4 remedy):** restore `win-ready` (Part A not yet run), enable IIS
  (`Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole -All`), then run
  step A4 and confirm its check prints a table and its remedy clears it.
- [ ] **Sleep (best effort):** Start → Sleep, resume from the QEMU window. Log whether
  `localhost` survives; mark the result as VM-only evidence.
- [ ] **Docker Desktop (A5):** skipped by default (open question 3).

### Task 8: Report and follow-up

- [ ] **Step 1:** finish `test-log.md` in this artifact folder; add `walkthrough.md`
  summarising results per walkthrough assumption (1–7) and the VM caveats.
- [ ] **Step 2:** run `gitleaks detect --source docs/artifacts/2026-10-07-154420-windows-vm-guide-test --no-git`.
  Expected: no leaks.
- [ ] **Step 3:** propose guide edits from the findings (separate approval before editing
  `DEPLOYMENT-WINDOWS.md`). Remove the "not yet test-run" callout only on a clean pass,
  and reword it to "tested in a Windows 11 VM" rather than "tested on a PC".
- [ ] **Step 4:** update the `demo-windows-wsl-guide-untested` memory with the outcome.
- [ ] **Step 5:** ask whether to keep the VM (snapshot `win-ready` is useful for
  re-testing guide revisions; ~90 GB) or delete `~/vms/win11-wsl-test/`.
- [ ] **Step 6:** copy the three scripts into `scripts/` here; commit artifacts only when
  asked.

## Test log format (`test-log.md`)

```markdown
| Step | Result | Time | What the guide said | What actually happened |
|---|---|---|---|---|
| A1 | PASS | 09:12–09:21 | `wsl --version` first line `WSL version: 2.x` | as stated |
| A3 | DEVIATION | ... | prints `running` or `degraded` | printed `starting`; ok after 30 s |
```
Result is one of PASS, DEVIATION (worked, but not as written), FAIL (blocked), VM-ONLY.

## Risks and fallbacks

1. **WSL2 fails in the nested VM** (`0x80370102`, or "Virtual Machine Platform" error at A1).
   First check `cat /sys/module/kvm_intel/parameters/nested` is `Y`. Then try adding
   Hyper-V enlightenments: `-cpu host,hv_relaxed,hv_vapic,hv_spinlocks=0x1fff,hv_time`.
   If it still fails, the test stops at A1 and only the Ubuntu-VM fallback (Option 2) remains.
2. **Host memory pressure.** 24 GB for the VM leaves ~6 GB for the desktop. Close other
   heavy apps and keep host containers stopped. If the host swaps hard, drop to
   `-m 22G` and note that this is below the guide's minimum.
3. **Slow disk on AHCI.** Install timings will not match a real PC; recorded as VM-ONLY.
4. **Evaluation expiry.** 90 days from install. Enough for this test and a few re-runs
   from `win-ready`.
5. **Snapshot restore with TPM/vars mismatch.** Always use `snap.sh`, never
   `qemu-img snapshot -a` alone.

## Estimated effort

| Phase | Wall clock | Tester at console |
|---|---|---|
| Tasks 1–3 (incl. ISO download + Windows install + updates) | ~1.5 h | ~20 min |
| Task 4 | ~15 min | ~10 min |
| Tasks 5–6 (the guide itself) | ~1.5–2 h | throughout, mostly waiting |
| Task 7 | ~45 min | throughout |
| Task 8 | ~30 min | review only |

ADR: not needed. No architecture decision is made; this is a test harness outside the repo.
