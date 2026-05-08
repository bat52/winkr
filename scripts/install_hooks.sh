#!/usr/bin/env bash
# Install the winkr enforcer pre-commit hook into the current repo.
#
# Usage:
#   ./scripts/install_hooks.sh
#
# Detects the repository root, backs up any existing pre-commit hook,
# and symlinks/copies scripts/enforcer-hook.sh into .git/hooks/pre-commit.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: not inside a Git repository." >&2
    exit 1
}

HOOK_SRC="${REPO_ROOT}/scripts/enforcer-hook.sh"
HOOK_DST="${REPO_ROOT}/.git/hooks/pre-commit"

if [ ! -f "$HOOK_SRC" ]; then
    echo "Error: enforcer hook source not found at ${HOOK_SRC}" >&2
    exit 1
fi

# Backup existing hook if present
if [ -f "$HOOK_DST" ] && [ ! -L "$HOOK_DST" ]; then
    BACKUP="${HOOK_DST}.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing pre-commit hook to ${BACKUP}"
    cp "$HOOK_DST" "$BACKUP"
fi

# Install the hook
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "✅ winkr enforcer pre-commit hook installed at ${HOOK_DST}"
echo "   (soft-enforcement: warns on direct edits, does not block commits)"
