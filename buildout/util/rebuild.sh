#!/bin/bash
# Rebuild script for rebuilding from scratch, possibly preserving data??
#


export TZ=Pacific/Auckland
LOG_DIR=${LOG_DIR:=~/logs}

[[ -d ~/logs ]] || {
    mkdir ~/logs || exit 1
}
now=$(date +%Y%m%d%H%M%S)

LOG_FILE=$LOG_DIR/rebuild_$now.log

exec > $LOG_FILE 2>&1

date
echo Rebuilding...
echo

cd digitaltwins-platform

docker compose down
docker compose up -d
