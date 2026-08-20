#!/bin/bash

BACKUP_DIR="/home/clin864/archive/docker_volumes-20260813"
mkdir -p "$BACKUP_DIR"

for vol in $(docker volume ls -q -f "name=^digitaltwins-platform"); do
    echo "Backing up: $vol"
    docker run --rm \
        -v "$vol":/source:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar -czf /backup/"$vol".tar.gz -C /source .
done

echo "All digitaltwins_ volumes backed up successfully!"