"""Pre-commit enforcement for the winkr mutation policy.

Detects whether commits or staged changes originated from Aider
(``winkr change``) or from direct file editing (Cline built-in tools).
Provides soft-enforcement warnings via the ``winkr enforcer`` CLI.
"""

from __future__ import annotations

import enum
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


class CommitOrigin(enum.StrEnum):
    """Inferred origin of a commit based on message and diff heuristics."""

    AIDER = "aider"
    """Commit message or diff patterns match Aider's signature."""

    CLINE_DIRECT = "cline_direct"
    """Commit appears to use Cline's built-in write tools directly."""

    MANUAL = "manual"
    """Hand-edited (no Aider or Cline signature detected)."""

    UNKNOWN = "unknown"
    """Cannot determine the origin."""


@dataclass(frozen=True)
class EnforcerResult:
    """Result of a single enforcer check."""

    passed: bool
    """Whether the check succeeded (no policy violations)."""

    commit_author: CommitOrigin | None = None
    """Inferred origin of the commit, if applicable."""

    reason: str = ""
    """Human-readable explanation when ``passed`` is False."""

    stats: dict[str, int] = field(default_factory=dict)
    """Number of files touched, by operation type."""


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

_AIDER_MESSAGE_PREFIXES = ("aider: ", "aider> ", "feat(aider)", "fix(aider)")
"""Commit message prefixes that indicate Aider authored the commit."""

_AIDER_DIFF_PATTERNS = ("aider", "--- a/", "+++ b/")
"""Diff line patterns commonly associated with Aider-generated commits."""

_WINKR_MANAGED_FILES = frozenset({
    ".clinerules",
    "implementation_plan.md",
    ".ai_logs",
})
"""Files that should only be modified via ``winkr change``."""


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_commit_origin(
    commit_hash: str,
    cwd: Path | None = None,
) -> CommitOrigin:
    """Infer the origin of a single commit.

    Reads the commit message and diff stat to classify the commit as
    Aider-authored, Cline-direct, manual, or unknown.

    Parameters
    ----------
    commit_hash:
        Full or abbreviated Git commit hash.
    cwd:
        Working directory for Git commands (default: current directory).

    Returns
    -------
    CommitOrigin
        The inferred origin.
    """
    workdir = cwd or Path.cwd()

    # Read commit message
    msg_result = subprocess.run(
        ("git", "log", "--format=%B", "-n1", commit_hash),
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    message = msg_result.stdout.strip()

    # Read diff stat
    diff_result = subprocess.run(
        ("git", "diff", "--stat", f"{commit_hash}^..{commit_hash}"),
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    diff_stat = diff_result.stdout

    # Heuristic 1: Aider-style commit message
    for prefix in _AIDER_MESSAGE_PREFIXES:
        if message.startswith(prefix):
            return CommitOrigin.AIDER

    # Heuristic 2: Aider-style diff patterns in message
    for pattern in _AIDER_DIFF_PATTERNS:
        if pattern in message:
            return CommitOrigin.AIDER

    # Heuristic 3: Check if any touched files are winkr-managed
    touched_files = _parse_touched_files(diff_stat)
    if touched_files & _WINKR_MANAGED_FILES:
        return CommitOrigin.CLINE_DIRECT

    # Heuristic 4: If message is very short and touches many files,
    # it's likely a Cline bulk edit
    word_count = len(message.split())
    if word_count < 5 and len(touched_files) > 2:
        return CommitOrigin.CLINE_DIRECT

    # Heuristic 5: Manual commits usually have descriptive messages
    if word_count >= 5:
        return CommitOrigin.MANUAL

    return CommitOrigin.UNKNOWN


def check_commits(
    commit_range: str | None = None,
    cwd: Path | None = None,
    warn_only: bool = True,
) -> list[EnforcerResult]:
    """Check a range of commits for policy compliance.

    Parameters
    ----------
    commit_range:
        Git revision range (e.g., ``HEAD~5..HEAD``).  Defaults to
        ``HEAD`` vs. merge-base with ``main`` or ``master``.
    cwd:
        Working directory for Git commands.
    warn_only:
        If True, log warnings instead of raising on violations.

    Returns
    -------
    list[EnforcerResult]
        One result per commit in the range.
    """
    workdir = cwd or Path.cwd()

    if commit_range is None:
        # Determine default range: HEAD vs. merge-base with main/master
        for branch in ("main", "master"):
            merge_base = subprocess.run(
                ("git", "merge-base", branch, "HEAD"),
                cwd=workdir,
                text=True,
                capture_output=True,
                check=False,
            )
            if merge_base.returncode == 0:
                commit_range = f"{merge_base.stdout.strip()}..HEAD"
                break
        if commit_range is None:
            commit_range = "HEAD~5..HEAD"

    # Get list of commits in range
    log_result = subprocess.run(
        ("git", "log", "--format=%H", commit_range),
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    if log_result.returncode != 0:
        return [
            EnforcerResult(
                passed=True,
                reason=f"Could not read commit range: {log_result.stderr.strip()}",
            )
        ]

    hashes = log_result.stdout.strip().splitlines()
    if not hashes:
        return [EnforcerResult(passed=True, reason="No commits in range.")]

    results: list[EnforcerResult] = []
    for h in hashes:
        origin = detect_commit_origin(h, cwd=workdir)
        if origin == CommitOrigin.CLINE_DIRECT:
            results.append(
                EnforcerResult(
                    passed=False,
                    commit_author=origin,
                    reason=f"Commit {h[:8]} appears to use direct file editing (not winkr change).",
                )
            )
        else:
            results.append(
                EnforcerResult(
                    passed=True,
                    commit_author=origin,
                    reason=f"Commit {h[:8]} origin: {origin.value}.",
                )
            )

    return results


def check_pending_changes(cwd: Path | None = None) -> EnforcerResult:
    """Check staged (cached) changes for policy compliance.

    Examines ``git diff --cached --stat`` to see if any staged files
    are winkr-managed files that should only be modified via
    ``winkr change``.

    Parameters
    ----------
    cwd:
        Working directory for Git commands.

    Returns
    -------
    EnforcerResult
        Check result with warnings if violations are detected.
    """
    workdir = cwd or Path.cwd()

    diff_result = subprocess.run(
        ("git", "diff", "--cached", "--stat"),
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    diff_stat = diff_result.stdout.strip()

    if not diff_stat:
        return EnforcerResult(passed=True, reason="No staged changes.")

    touched_files = _parse_touched_files(diff_stat)
    violations = touched_files & _WINKR_MANAGED_FILES

    if violations:
        return EnforcerResult(
            passed=False,
            reason=(
                "Direct edit detected on winkr-managed files: "
                f"{', '.join(sorted(violations))}. "
                "Use `winkr change` for repository mutations."
            ),
            stats={"violations": len(violations), "total_files": len(touched_files)},
        )

    return EnforcerResult(
        passed=True,
        reason=f"{len(touched_files)} file(s) staged — no policy violations.",
        stats={"total_files": len(touched_files)},
    )


def check_worktree_block(cwd: Path | None = None) -> EnforcerResult:
    """Blocking check: exit non-zero if the worktree has policy violations.

    This is the **hard enforcement** variant of ``check_pending_changes``.
    It checks both staged and unstaged changes for winkr-managed file
    violations. Cline MUST run this before every mutation.

    Unlike ``check_pending_changes``, this function:
    - Checks both staged AND unstaged changes (``git diff HEAD``)
    - Returns ``passed=False`` with a non-zero exit code for violations
    - Is designed to be used as a pre-mutation gate

    Parameters
    ----------
    cwd:
        Working directory for Git commands.

    Returns
    -------
    EnforcerResult
        ``passed=False`` if any policy violations are detected.
    """
    workdir = cwd or Path.cwd()

    # Check staged changes
    staged_result = check_pending_changes(cwd=workdir)
    if not staged_result.passed:
        return staged_result

    # Check unstaged changes (working tree vs HEAD)
    diff_result = subprocess.run(
        ("git", "diff", "HEAD", "--stat"),
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    diff_stat = diff_result.stdout.strip()

    if not diff_stat:
        return EnforcerResult(passed=True, reason="No changes detected — worktree is clean.")

    touched_files = _parse_touched_files(diff_stat)
    violations = touched_files & _WINKR_MANAGED_FILES

    if violations:
        return EnforcerResult(
            passed=False,
            reason=(
                "BLOCKED: Direct edit detected on winkr-managed files: "
                f"{', '.join(sorted(violations))}. "
                "Use `winkr change` for repository mutations."
            ),
            stats={"violations": len(violations), "total_files": len(touched_files)},
        )

    return EnforcerResult(
        passed=True,
        reason=f"{len(touched_files)} file(s) changed — no policy violations.",
        stats={"total_files": len(touched_files)},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_touched_files(diff_stat: str) -> set[str]:
    """Extract file paths from a ``git diff --stat`` output."""
    files: set[str] = set()
    for line in diff_stat.splitlines():
        # Typical format: " src/foo.py | 2 +-"
        line = line.strip()
        if " | " in line:
            path = line.split(" | ", 1)[0].strip()
            if path:
                files.add(path)
    return files
