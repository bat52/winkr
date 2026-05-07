"""Aider command construction and execution."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_EDIT_MODEL, DEFAULT_QUERY_MODEL, resolve_model
from .credentials import ResolvedApiKey


@dataclass(frozen=True)
class AiderCommand:
    """A command line ready to be passed to subprocess."""

    argv: tuple[str, ...]

    def shell_string(self) -> str:
        """Return a shell-escaped representation for logging/debugging."""

        return " ".join(shlex.quote(part) for part in self.argv)


def build_query_command(
    prompt: str,
    api_key: ResolvedApiKey,
    model: str | None = None,
    extra_args: Sequence[str] = (),
) -> AiderCommand:
    """Build the Aider command for read-oriented queries."""

    selected_model = resolve_model(model or DEFAULT_QUERY_MODEL)
    argv = [
        "aider",
        "--api-key",
        api_key.for_aider(),
        "--model",
        selected_model,
        "--message",
        prompt,
    ]
    argv.extend(extra_args)
    return AiderCommand(tuple(argv))


def build_edit_command(
    prompt: str,
    api_key: ResolvedApiKey,
    model: str | None = None,
    files: Sequence[str] = (),
    extra_args: Sequence[str] = (),
) -> AiderCommand:
    """Build the Aider command for mutation-oriented edits."""

    selected_model = resolve_model(model or DEFAULT_EDIT_MODEL)
    argv = [
        "aider",
        "--api-key",
        api_key.for_aider(),
        "--model",
        selected_model,
        "--message",
        prompt,
    ]
    argv.extend(files)
    argv.extend(extra_args)
    return AiderCommand(tuple(argv))


def run_command(command: AiderCommand, cwd: Path | None = None) -> int:
    """Run an Aider command and return its process exit code."""

    completed = subprocess.run(command.argv, cwd=cwd, check=False)
    return completed.returncode


def validate_prompt(prompt: str) -> None:
    """Reject prompt fragments known to conflict with repo style."""

    if "# noqa" in prompt:
        raise ValueError("Do not request or add '# noqa' suppressions.")
