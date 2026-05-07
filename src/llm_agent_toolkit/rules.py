"""Packaged Cline rule templates."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def load_base_rules() -> str:
    """Return the bundled base Cline rules."""

    return (
        resources.files("llm_agent_toolkit")
        .joinpath("rules/clinerules.base.md")
        .read_text(encoding="utf-8")
    )


def write_rules_file(path: Path, *, force: bool = False) -> None:
    """Write bundled base rules to ``path``."""

    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists. Pass --force to overwrite it."
        )
    path.write_text(load_base_rules(), encoding="utf-8")
