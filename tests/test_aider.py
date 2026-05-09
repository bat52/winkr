from __future__ import annotations

import pytest

from llm_agent_toolkit.aider import (
    build_architect_command,
    build_change_command,
    build_query_command,
    validate_prompt,
)
from llm_agent_toolkit.credentials import ResolvedApiKey


def test_build_query_command_resolves_tier() -> None:
    key = ResolvedApiKey("openrouter", "secret", "test")

    command = build_query_command("hello world", key, model="TIER_FAST")

    assert command.argv == (
        "aider",
        "--api-key",
        "openrouter=secret",
        "--model",
        "openrouter/google/gemini-2.5-flash",
        "--message",
        "hello world",
    )


def test_build_change_command_includes_files() -> None:
    key = ResolvedApiKey("deepseek", "secret", "test")

    command = build_change_command(
        "refactor",
        key,
        model="TIER_CODING",
        files=("src/foo.py",),
    )

    assert command.argv == (
        "aider",
        "--api-key",
        "deepseek=secret",
        "--model",
        "openrouter/deepseek/deepseek-chat",
        "--message",
        "refactor",
        "src/foo.py",
    )


def test_validate_prompt_rejects_noqa() -> None:
    with pytest.raises(ValueError):
        validate_prompt("please add # noqa everywhere")


def test_validate_prompt_accepts_normal_prompt() -> None:
    validate_prompt("please fix this")


def test_build_architect_command_vs_change() -> None:
    """Verify architect command differs structurally from change command."""
    key = ResolvedApiKey("openrouter", "secret", "test")

    change_cmd = build_change_command("refactor", key, model="TIER_CODING")
    arch_cmd = build_architect_command("refactor", key)

    # Both should have --api-key and --message
    assert "--api-key" in change_cmd.argv
    assert "--api-key" in arch_cmd.argv

    # Architect should have --architect and --editor-model
    assert "--architect" in arch_cmd.argv
    assert "--editor-model" in arch_cmd.argv

    # Change should NOT have --architect
    assert "--architect" not in change_cmd.argv
    assert "--editor-model" not in change_cmd.argv
