#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required for Cline."
  echo "Install Node.js LTS using your platform's recommended method, then rerun."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for Cline."
  exit 1
fi

npm install -g cline

echo "Cline installation complete."
