#!/bin/bash

# ==============================================================================
# Script: docker_archive_volumes.sh
# Description: Backs up all Docker volumes prefixed with 'digitaltwins-platform'.
#              Each volume is compressed into a .tar.gz archive and saved to the
#              specified backup directory.
#
# Usage: ./docker_archive_volumes.sh <backup_directory>
# Example: ./docker_archive_volumes.sh /home/clin864/archive/docker_volumes-20260813
# ==============================================================================

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 /path/to/backup_dir"
    exit 1
fi

BACKUP_DIR="$1"
mkdir -p "$BACKUP_DIR"

for vol in $(docker volume ls -q -f "name=^digitaltwins-platform"); do
    echo "Backing up: $vol"
    docker run --rm \
        -v "$vol":/source:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar -czf /backup/"$vol".tar.gz -C /source .
done

echo "All digitaltwins_ volumes backed up successfully!"