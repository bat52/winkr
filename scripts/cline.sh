#!/usr/bin/env bash
# Wrapper: launch Cline with a per-repository CLINE_HOME.
#
# Usage:
#   ./scripts/cline.sh [cline-args...]
#
# Sets CLINE_HOME to $(pwd)/.cline so each repository gets its own
# isolated Cline data directory.  The directory is removed on exit.

set -euo pipefail

export CLINE_HOME="$(pwd)/.cline"
mkdir -p "$CLINE_HOME"

cleanup() {
  rm -rf "$CLINE_HOME"
}

trap cleanup EXIT

npx cline "$@"
