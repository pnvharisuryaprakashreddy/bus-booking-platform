#!/bin/sh
# Runs the assessment checks against the Compose stack and writes docs/evidence/latest-acceptance.log
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
    echo "Copy .env.example to .env before running the demo." >&2
    exit 1
fi
exec python3 ops/acceptance.py
