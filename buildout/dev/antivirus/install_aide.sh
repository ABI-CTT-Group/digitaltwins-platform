#!/bin/bash
set -euo pipefail

sudo apt update

export DEBIAN_FRONTEND=noninteractive
echo "postfix postfix/main_mailer_type select Local only" | sudo debconf-set-selections
echo "postfix postfix/mailname string $(hostname -f)" | sudo debconf-set-selections

sudo apt install -y aide cron
sudo systemctl enable cron
sudo systemctl start cron

sudo tee -a /etc/aide/aide.conf << 'EOF'
# ── Exclude noisy / irrelevant paths ──────────────────────────
!/proc
!/sys
!/dev
!/run
!/tmp
!/var/tmp
!/var/cache
!/var/log
!/var/lib/apt
!/var/lib/dpkg
!/var/lib/systemd
!/home/.*/.cache
!/snap
!/var/snap
!/var/lib/docker
!/var/lib/lxd
# Full check for critical binaries
CONTENTEX = sha256+ftype+p+u+g+n+i+S
# Lighter check for large dirs (skip mtime/ctime which change often)
LIGHTCHECK = sha256+ftype+p+u+g
#/usr/lib    LIGHT
/usr/share  LIGHTCHECK
# ── Only scan what matters ────────────────────────────────────
/etc        CONTENTEX
/bin        CONTENTEX
/sbin       CONTENTEX
/usr/bin    CONTENTEX
/usr/sbin   CONTENTEX
/usr/lib    CONTENTEX
/boot       CONTENTEX
/root       CONTENTEX
EOF

sudo aide --config=/etc/aide/aide.conf --config-check

sudo aide --config=/etc/aide/aide.conf --init

sudo mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db

echo "modify /etc/crontab to change the cron.daily cronjob start time to 2:00 AM"