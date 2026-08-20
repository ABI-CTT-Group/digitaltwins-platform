#!/bin/bash

# Find all volumes starting with "digitaltwins-platform"
if ! VOLUMES=$(docker volume ls -q -f "name=^digitaltwins-platform"); then
    echo "Failed to list Docker volumes." >&2
    exit 1
fi

# Check if any volumes were actually found
if [ -z "$VOLUMES" ]; then
    echo "No volumes found starting with 'digitaltwins-platform'."
    exit 0
fi

echo "Deleting the following volumes:"
echo "$VOLUMES"

if ! echo "$VOLUMES" | xargs -r docker volume rm; then
    echo "Failed to delete one or more Docker volumes." >&2
    exit 1
fi

echo "Done."
