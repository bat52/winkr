"""Tests for the architect command builder and CLI handler."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from llm_agent_toolkit.aider import build_architect_command
from llm_agent_toolkit.credentials import ResolvedApiKey


def test_build_architect_command_includes_architect_flag() -> None:
    """Verify --architect flag appears in the argv."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command("plan this", key)
    assert "--architect" in command.argv


def test_build_architect_command_default_model() -> None:
    """Verify default model resolves to TIER_REASONING."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command("plan this", key)
    # Default model should be the TIER_REASONING mapping
    assert "openrouter/google/gemini-2.5-flash" in command.argv
    # The model arg should appear before --architect
    model_idx = command.argv.index("--model")
    assert command.argv[model_idx + 1] == "openrouter/google/gemini-2.5-flash"


def test_build_architect_command_editor_model() -> None:
    """Verify --editor-model is set to TIER_CODING."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command("plan this", key)
    assert "--editor-model" in command.argv
    editor_idx = command.argv.index("--editor-model")
    assert command.argv[editor_idx + 1] == "openrouter/deepseek/deepseek-chat"


def test_build_architect_command_includes_files() -> None:
    """Verify files are appended after the aider args."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command(
        "plan this",
        key,
        files=("src/foo.py", "src/bar.py"),
    )
    assert "src/foo.py" in command.argv
    assert "src/bar.py" in command.argv
    # Files should come after --editor-model value
    editor_idx = command.argv.index("--editor-model")
    file_idx = command.argv.index("src/foo.py")
    assert file_idx > editor_idx


def test_build_architect_command_custom_model() -> None:
    """Verify a custom model overrides the default."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command("plan this", key, model="gpt-4o")
    model_idx = command.argv.index("--model")
    assert command.argv[model_idx + 1] == "gpt-4o"


def test_build_architect_command_extra_args() -> None:
    """Verify extra args are appended at the end."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command(
        "plan this",
        key,
        extra_args=("--yes", "--no-suggest-shell-commands"),
    )
    assert "--yes" in command.argv
    assert "--no-suggest-shell-commands" in command.argv


def test_build_architect_command_full_argv_structure() -> None:
    """Verify the full argv structure matches expectations."""
    key = ResolvedApiKey("openrouter", "secret", "test")
    command = build_architect_command(
        "refactor auth module",
        key,
        model="TIER_REASONING",
        files=("auth.py",),
        extra_args=("--yes",),
    )
    assert command.argv == (
        "aider",
        "--api-key",
        "openrouter=secret",
        "--model",
        "openrouter/google/gemini-2.5-flash",
        "--message",
        "refactor auth module",
        "--architect",
        "--editor-model",
        "openrouter/deepseek/deepseek-chat",
        "auth.py",
        "--yes",
    )


@patch("llm_agent_toolkit.cli.ensure_clean_worktree")
@patch("llm_agent_toolkit.cli.run_command")
@patch("llm_agent_toolkit.cli.resolve_api_key")
@patch("llm_agent_toolkit.cli.build_architect_command")
def test_handle_architect(
    mock_build_architect,
    mock_resolve_api_key,
    mock_run_command,
    mock_ensure_clean_worktree,
) -> None:
    """Verify handle_architect calls build_architect_command and run_command."""
    from llm_agent_toolkit.cli import handle_architect

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.prompt = "Plan the refactor"
    mock_args.files = ["src/foo.py"]
    mock_args.allow_dirty = False
    mock_args.api_key = "test_key"
    mock_args.model = "TIER_REASONING"
    mock_args.extra_aider_arg = []
    mock_args.no_log = False
    mock_args.print_command = False

    mock_api_key = MagicMock()
    mock_resolve_api_key.return_value = mock_api_key
    mock_run_command.return_value = 0

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider architect command"
    mock_build_architect.return_value = mock_command

    return_code = handle_architect(mock_args)

    assert return_code == 0
    mock_build_architect.assert_called_once_with(
        prompt="Plan the refactor",
        api_key=mock_api_key,
        model="TIER_REASONING",
        files=["src/foo.py"],
        extra_args=[],
    )
    mock_run_command.assert_called_once_with(mock_command)


@patch("llm_agent_toolkit.cli.ensure_clean_worktree")
@patch("llm_agent_toolkit.cli.run_command")
@patch("llm_agent_toolkit.cli.resolve_api_key")
@patch("llm_agent_toolkit.cli.build_architect_command")
def test_handle_architect_print_command(
    mock_build_architect,
    mock_resolve_api_key,
    mock_run_command,
    mock_ensure_clean_worktree,
) -> None:
    """Verify --print-command prints the command and returns 0 without running."""
    from llm_agent_toolkit.cli import handle_architect

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.prompt = "Plan the refactor"
    mock_args.files = []
    mock_args.allow_dirty = False
    mock_args.api_key = "test_key"
    mock_args.model = None
    mock_args.extra_aider_arg = []
    mock_args.no_log = False
    mock_args.print_command = True

    mock_api_key = MagicMock()
    mock_resolve_api_key.return_value = mock_api_key

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider architect command"
    mock_build_architect.return_value = mock_command

    with patch("builtins.print"):
        return_code = handle_architect(mock_args)

    assert return_code == 0
    mock_run_command.assert_not_called()


@patch("llm_agent_toolkit.cli.ensure_clean_worktree")
@patch("llm_agent_toolkit.cli.resolve_api_key")
def test_handle_architect_no_api_key(mock_resolve_api_key, mock_ensure_clean_worktree) -> None:
    """Verify handle_architect returns 2 when no API key is found."""
    from llm_agent_toolkit.cli import handle_architect

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.prompt = "Plan the refactor"
    mock_args.files = []
    mock_args.allow_dirty = False
    mock_args.api_key = None
    mock_args.model = None
    mock_args.extra_aider_arg = []
    mock_args.no_log = False
    mock_args.print_command = False

    mock_resolve_api_key.return_value = None

    return_code = handle_architect(mock_args)
    assert return_code == 2
