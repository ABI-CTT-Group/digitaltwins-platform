#!/bin/bash
set -euo pipefail

sudo apt install clamav -y
sudo apt install clamav-daemon -y

echo "Create clamav scan script"
sudo cat <<'EOF' > "$HOME/clamav-scan.sh"
#!/usr/bin/env bash
set -u
set -o pipefail

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S-%3N")
HOSTNAME=$(hostname -f 2>/dev/null || hostname)

LOG_DIR="/var/log/clamav"
LOG_FILE="$LOG_DIR/scan_$TIMESTAMP.log"

MAIL_TO="ubuntu"
MAIL_SUBJECT="[ClamAV Alert] Infected files detected on ${HOSTNAME}"

TARGETS=(
  /home
  /var/lib
  /opt
  /srv
)

EXCLUDES=(
  --exclude-dir=^/proc
  --exclude-dir=^/sys
  --exclude-dir=^/dev
  --exclude-dir=^/tmp
  --exclude-dir=^/var/log
  --exclude-dir=^/var/cache
  --exclude-dir=^/var/lib/docker
  --exclude-dir=^/var/lib/containerd
  --exclude-dir=^/var/lib/kubelet
  --exclude-dir=^/var/lib/rancher
)

mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"

{
  echo "--- Scan started at $(date) ---"
  echo "Host: $HOSTNAME"
  echo "Targets: ${TARGETS[*]}"
  echo "---------------------------------------"
} > "$LOG_FILE"

SCAN_OUTPUT=$(nice -n 19 ionice -c 3 clamdscan --multiscan --infected --fdpass "${TARGETS[@]}" 2>&1)
SCAN_EXIT_CODE=$?

echo "$SCAN_OUTPUT" >> "$LOG_FILE"

{
  echo "---------------------------------------"
  echo "--- Scan finished at $(date) ---"
  echo "Exit code: $SCAN_EXIT_CODE"
} >> "$LOG_FILE"

INFECTED_COUNT=$(awk -F': ' '/Infected files:/ {print $2}' "$LOG_FILE" | tail -1)
INFECTED_COUNT=${INFECTED_COUNT:-0}

echo "Infected files found: $INFECTED_COUNT"
echo "Scan complete. Log saved to: $LOG_FILE"

if [ "$INFECTED_COUNT" -ge 1 ]; then
  if command -v mail >/dev/null 2>&1; then
    mail -s "$MAIL_SUBJECT" "$MAIL_TO" <<MAILEND
ClamAV detected more than 1 infected file.

Host: $HOSTNAME
Time: $(date)
Infected files: $INFECTED_COUNT
Log file: $LOG_FILE

Recent infected entries:
$(grep 'FOUND$' "$LOG_FILE" | tail -20)

Please review the full log on the server.
MAILEND
    echo "Alert email sent to $MAIL_TO"
  else
    echo "mail command not found; cannot send email alert." >> "$LOG_FILE"
    echo "mail command not found; alert not sent."
  fi
fi
EOF

sudo chmod +x "$HOME/clamav-scan.sh"

echo "Exclude file in /etc/clamav/clamd.conf"
sudo tee -a /etc/clamav/clamd.conf << 'EOF'
ExcludePath ^/var/lib/docker/
ExcludePath ^/var/lib/containerd/
ExcludePath ^/var/lib/kubelet/
ExcludePath ^/var/lib/rancher/
ExcludePath ^/proc/
ExcludePath ^/sys/
ExcludePath ^/dev/
EOF

CRON_JOB="0 4 * * * $HOME/clamav-scan.sh"

sudo crontab -l 2>/dev/null | grep -q "$CRON_JOB" || \
  ( sudo crontab -l 2>/dev/null; echo "$CRON_JOB" ) | sudo crontab -

echo "Cron job will start at 4:00 AM daily."