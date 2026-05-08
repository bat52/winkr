#!/usr/bin/env bash
# Pre-commit hook: soft-enforcement for winkr mutation policy.
#
# Warns when staged changes appear to have been made outside of
# `winkr change` (i.e., via direct file editing).  Does NOT block
# the commit — this is a soft-enforcement layer.
#
# Installed by: scripts/install_hooks.sh
# Invoked by:   Git pre-commit hook

set -euo pipefail

# Only run if winkr is installed
if ! command -v winkr &>/dev/null; then
    exit 0
fi

# Run the enforcer check on staged changes
output=$(winkr enforcer check 2>&1) || true

if echo "$output" | grep -qi "warning\|direct edit\|bypass"; then
    echo ""
    echo "⚠️  [winkr enforcer] Policy warning — pre-commit check detected:"
    echo ""
    echo "$output" | while IFS= read -r line; do
        echo "   $line"
    done
    echo ""
    echo "   This is a soft warning. The commit will proceed."
    echo "   To suppress this warning, use \`winkr change\` for mutations."
    echo "   To bypass entirely: git commit --no-verify"
    echo ""
fi

exit 0
