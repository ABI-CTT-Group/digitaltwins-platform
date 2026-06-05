# Update Antigravity IDE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check for the IDE updates and update the Antigravity IDE to the latest version (2.1.0-6066040229199872) locally for the current user, without requiring sudo permissions.

**Architecture:** Download the pre-built Linux x64 tarball for version 2.1.0 from the public Google Cloud Storage bucket, extract it to a user-writable directory (`~/opt/antigravity`), set up a local wrapper script in `~/.local/bin/antigravity` (which takes precedence in the user's `PATH`), and create local override desktop entries in `~/.local/share/applications/` to ensure the GUI application launches using the new version.

**Tech Stack:** Bash, Linux Desktop Specifications, curl, tar

---

### Task 1: Download and Extract the Latest Antigravity IDE Release

**Files:**
- Create: `/home/clin864/opt/antigravity/` (installation directory)

- [ ] **Step 1: Create the local target directories**
  Run: `mkdir -p /home/clin864/opt/antigravity`
  Expected: Command succeeds and directory is created.

- [ ] **Step 2: Download the 2.1.0 Linux x64 tarball from GCS**
  Run: `curl -L -o /tmp/Antigravity-2.1.0.tar.gz "https://storage.googleapis.com/antigravity-public/antigravity-hub/2.1.0-6066040229199872/linux-x64/Antigravity.tar.gz"`
  Expected: Download completes successfully with 200 OK.

- [ ] **Step 3: Extract the tarball**
  Run: `tar -xzf /tmp/Antigravity-2.1.0.tar.gz -C /home/clin864/opt/antigravity`
  Expected: Archive is extracted, creating `/home/clin864/opt/antigravity/Antigravity-x64/` containing the main `antigravity` binary.

- [ ] **Step 4: Verify the extracted binary version**
  Run: `/home/clin864/opt/antigravity/Antigravity-x64/antigravity --version` (or with `--no-sandbox` if needed)
  Expected: Outputs version starting with `2.1.0` or similar metadata.

- [ ] **Step 5: Clean up downloaded archive**
  Run: `rm /tmp/Antigravity-2.1.0.tar.gz`
  Expected: Temporary archive is deleted.

---

### Task 2: Configure Local wrapper Binary in PATH

**Files:**
- Create: `/home/clin864/.local/bin/antigravity` (local shell wrapper)

- [ ] **Step 1: Write the wrapper script**
  Write file contents to `/home/clin864/.local/bin/antigravity`:
  ```bash
  #!/usr/bin/env sh
  VSCODE_PATH="/home/clin864/opt/antigravity/Antigravity-x64"
  ELECTRON="$VSCODE_PATH/antigravity"
  CLI="$VSCODE_PATH/resources/app/out/cli.js"
  ELECTRON_RUN_AS_NODE=1 "$ELECTRON" "$CLI" "$@"
  ```

- [ ] **Step 2: Make wrapper script executable**
  Run: `chmod +x /home/clin864/.local/bin/antigravity`
  Expected: Executable bit is set on the wrapper script.

---

### Task 3: Override Desktop Entries Locally

**Files:**
- Create: `/home/clin864/.local/share/applications/antigravity.desktop`
- Create: `/home/clin864/.local/share/applications/antigravity-url-handler.desktop`

- [ ] **Step 1: Copy and edit the main desktop entry**
  Copy: `/usr/share/applications/antigravity.desktop` to `/home/clin864/.local/share/applications/antigravity.desktop`
  Edit line 5 in `/home/clin864/.local/share/applications/antigravity.desktop`:
  Change `Exec=/usr/share/antigravity/antigravity %F` to `Exec=/home/clin864/opt/antigravity/Antigravity-x64/antigravity %F`
  Edit line 27 in `/home/clin864/.local/share/applications/antigravity.desktop`:
  Change `Exec=/usr/share/antigravity/antigravity --new-window %F` to `Exec=/home/clin864/opt/antigravity/Antigravity-x64/antigravity --new-window %F`

- [ ] **Step 2: Copy and edit the URL handler desktop entry**
  Copy: `/usr/share/applications/antigravity-url-handler.desktop` to `/home/clin864/.local/share/applications/antigravity-url-handler.desktop`
  Edit line 5 in `/home/clin864/.local/share/applications/antigravity-url-handler.desktop`:
  Change `Exec=/usr/share/antigravity/antigravity --open-url %U` to `Exec=/home/clin864/opt/antigravity/Antigravity-x64/antigravity --open-url %U`

- [ ] **Step 3: Update local desktop database**
  Run: `update-desktop-database ~/.local/share/applications`
  Expected: Command runs successfully, registering the user override entries.

---

### Task 4: Final Verification of Update

**Files:** None

- [ ] **Step 1: Test path resolution of the local binary**
  Run: `which antigravity`
  Expected: `/home/clin864/.local/bin/antigravity`

- [ ] **Step 2: Test version output of the new CLI**
  Run: `antigravity --version`
  Expected: Outputs version starting with `2.1.0` (not the old 1.107.0).
