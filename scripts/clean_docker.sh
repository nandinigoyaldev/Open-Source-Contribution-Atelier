#!/bin/bash

set -e

echo "Cleaning unused Docker volumes..."
docker volume prune -f

echo ""
echo "Cleaning stopped containers..."
docker container prune -f

echo ""
read -p "Do you want to remove local database volumes too? (y/N): " CONFIRM

if [[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]]; then
    echo "Removing all docker volumes..."

    docker volume rm $(docker volume ls -q) 2>/dev/null || true

    echo "Database volumes removed."
else
    echo "Database volumes preserved."
fi

echo "Cleanup complete."