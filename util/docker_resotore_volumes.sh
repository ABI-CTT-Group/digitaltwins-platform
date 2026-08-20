#!/bin/bash

BACKUP_DIR="/home/clin864/archive/staging/docker-volume-20260811"

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
