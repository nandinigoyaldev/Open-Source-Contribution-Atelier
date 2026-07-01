#!/usr/bin/env sh
set -eu

echo "Bootstrapping Open Source Contribution Atelier"
cp -n backend/.env.example backend/.env || true
cp -n frontend/.env.example frontend/.env || true
echo "Environment templates copied where missing."
