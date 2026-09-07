# Cleanup Dev Environment Deployment

This plan will clean up the production-like deployment that was accidentally installed by the `airgap_build_step3.yml` script, and return your dev laptop to a clean state.

## Addressing Your Question: Should you use `airgap_build_step3.yml` for Dev?

**No, you should not use this playbook for your daily development workflow.** Here is why:

1. **It creates a disconnected copy:** The playbook is designed to deploy a clean release to a production VM. It copies code from an install drive into `~/digitaltwins-platform`. If you edit files in your actual `Projects/digitaltwins-platform` workspace, the containers won't see those changes because they are running from the `~/digitaltwins-platform` copy.
2. **It forces auto-restart on boot:** As you experienced, it installs a systemd service designed for server persistence, which isn't ideal for a laptop.
3. **It runs heavy production bootstrap steps:** It runs production-specific asset precompilation and user bootstrapping that are slow and generally unnecessary to run every time you just want to spin up your dev stack.

**The Recommended Dev Workflow:**
Going forward, you should manage your dev containers directly using standard Docker Compose commands from inside your `Projects/digitaltwins-platform` directory:
- **Start:** `docker compose up -d`
- **Stop:** `docker compose down`
- **View Logs:** `docker compose logs -f`

This ensures your containers use your live code and only run exactly when you want them to.

## Proposed Changes

We will execute the following steps via shell commands to clean up the existing errant deployment:

1. **Stop the systemd service:** This will trigger the service's `ExecStop` which runs `docker compose down` in the duplicate repo, cleanly shutting down all those containers.
   ```bash
   sudo systemctl stop digitaltwins-platform.service
   ```
2. **Disable and remove the systemd unit:** Prevent it from starting again and delete the unit file so it's fully uninstalled.
   ```bash
   sudo systemctl disable digitaltwins-platform.service
   sudo rm /etc/systemd/system/digitaltwins-platform.service
   sudo systemctl daemon-reload
   ```
3. **Delete the duplicate repository:** Remove the copied codebase in your home directory that the systemd service was running from.
   ```bash
   rm -rf /home/clin864/digitaltwins-platform
   ```

## Verification Plan

### Manual Verification
- We will verify that running `docker ps` shows no `digitaltwins-platform` containers currently running.
- We will verify the `~/digitaltwins-platform` directory no longer exists.
- Going forward, you can safely run `docker compose up -d` directly from your correct dev directory (`/home/clin864/Projects/digitaltwins-platform`) without interference from the system service.
