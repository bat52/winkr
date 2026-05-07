"""Git safety helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_clean_worktree(cwd: Path) -> None:
    """Raise ``RuntimeError`` if cwd is a dirty Git worktree."""

    if not is_git_worktree(cwd):
        return

    completed = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    if completed.stdout.strip():
        raise RuntimeError(
            "Refusing to run change on a dirty Git worktree. "
            "Commit/stash changes or pass --allow-dirty."
        )


def is_git_worktree(cwd: Path) -> bool:
    completed = subprocess.run(
        ("git", "rev-parse", "--is-inside-work-tree"),
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0
