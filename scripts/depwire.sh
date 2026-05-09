#!/usr/bin/env bash
# Wrapper: launch depwire MCP server.
#
# Usage:
#   ./scripts/depwire.sh [depwire-args...]

set -euo pipefail

# Start Depwire MCP server in background
npx -y depwire-cli mcp > /dev/null 2>&1 &

# Run depwire docs
npx -y depwire-cli docs
