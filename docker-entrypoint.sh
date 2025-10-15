#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "[entrypoint] Rebuilding Cython extensions..."
# Clean previous build artifacts to force rebuild
rm -rf build/ mlat/*.c modes_cython/*.c mlat/*.so modes_cython/*.so 2>/dev/null || true

# Rebuild extensions
python setup.py build_ext --inplace

echo "[entrypoint] Starting mlat-server..."
exec python ./mlat-server "$@"
