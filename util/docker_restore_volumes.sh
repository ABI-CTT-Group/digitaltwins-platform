#!/bin/bash

# ==============================================================================
# Script: docker_restore_volumes.sh
# Description: Restores Docker volumes from .tar.gz archives located in a
#              specified backup directory. Volumes are automatically created if
#              they don't already exist.
#
# Usage: ./docker_restore_volumes.sh <backup_directory>
# Example: ./docker_restore_volumes.sh /home/clin864/archive/staging/docker-volume-20260811
# ==============================================================================

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 /path/to/backup_dir"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup directory '$BACKUP_DIR' does not exist."
    exit 1
fi
# Loop through all tar.gz files in the backup directory
for filepath in "$BACKUP_DIR"/*.tar.gz; do

    # 1. Get just the filename (e.g., "digitaltwins_data.tar.gz")
    filename=$(basename "$filepath")

    # 2. Chop off ".tar.gz" to get the exact volume name (e.g., "digitaltwins_data")
    vol="${filename%.tar.gz}"

    echo "Restoring file '$filename' to volume '$vol'..."

    # 3. Create the volume (Docker does nothing if it already exists)
    docker volume create "$vol" > /dev/null

    # 4. Extract the backup directly into the volume
    docker run --rm \
        -v "$vol":/target \
        -v "$BACKUP_DIR":/backup \
        alpine tar -xzf "/backup/$filename" -C /target

done

echo "All volumes restored successfully!"
