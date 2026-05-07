#!/usr/bin/env bash
# Wrapper: launch Cline with a per-repository home directory.
#
# Usage:
#   ./scripts/cline.sh [cline-args...]
#
# Sets CLINE_DIR and CLINE_DATA_DIR to $(pwd)/.cline so each repository
# gets its own isolated config and data directories (sessions, tasks,
# state, settings, etc.).  Both directories are removed on exit.

set -euo pipefail

export CLINE_DIR="$(pwd)/.cline"
export CLINE_DATA_DIR="$(pwd)/.cline/data"

mkdir -p "$CLINE_DATA_DIR"

cleanup() {
  rm -rf "$CLINE_DIR"
}

trap cleanup EXIT

npx cline "$@"
