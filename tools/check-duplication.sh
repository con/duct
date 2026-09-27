#!/bin/bash
# Code duplication detection.
# Run via: tox -e duplication
# Requires: npx (Node.js)

set -eu

if ! command -v npx >/dev/null 2>&1; then
    echo "ERROR: npx not found. Install Node.js to run duplication checks."
    exit 1
fi

echo "=== Code duplication check ==="
echo

# jscpd reads .jscpd.json for config (threshold, ignores, etc.)
npx --yes jscpd@latest .
