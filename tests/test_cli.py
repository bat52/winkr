import argparse
import subprocess
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Import the modules to test
try:
    from llm_agent_toolkit.cli import build_parser, handle_query, handle_change, handle_write_rules, handle_start, handle_tmux, handle_tiers
    from llm_agent_toolkit.init_command import handle_init, install_pip_package
except ImportError:
    pytest.fail("Could not import CLI modules. Ensure PYTHONPATH includes 'src'.")

# --- Mocking Setup ---

def mock_subprocess_run(cmd, **kwargs):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "mock output"
    mock_result.stderr = ""
    mock_result.configure_mock(capture_output=True, check=False, text=True)
    return mock_result

class MockPath(Path):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exists_map = {}

    def exists(self):
        return self._exists_map.get(str(self), False)

    def __str__(self):
        return super().__str__()

@pytest.fixture
def mock_init_environment_for_install_tests():
    """Fixture to set up mocks for handle_init installation logic tests."""
    with patch("subprocess.run", side_effect=mock_subprocess_run) as mock_run:
        mock_path_instance = MockPath(".")
        with patch("pathlib.Path", return_value=mock_path_instance):
            mock_sys_executable = "mock_python"
            with patch("sys.executable", mock_sys_executable):
                mock_os_environ_dict = {}
                with patch.dict("os.environ", mock_os_environ_dict, clear=True):
                    with patch("llm_agent_toolkit.init_command.check_command_exists") as mock_check_cmd_exists:
                        mock_check_cmd_exists.side_effect = lambda cmd: False
                        yield mock_run, mock_path_instance, mock_sys_executable, mock_os_environ_dict, mock_check_cmd_exists

@pytest.mark.parametrize(
    "is_virtualenv, has_pipx, has_pipenv, expected_install_cmd_part",
    [
        (True, False, False, "mock_python -m pip install"),
        (True, True, False, "mock_python -m pip install"),
        (True, False, True, "mock_python -m pip install"),
        (False, True, False, "pipx install"),
        (False, True, True, "pipx install"),
        (False, False, True, "pipenv install"),
        (False, False, False, "mock_python -m pip install --user"),
    ]
)
def test_install_pip_package_logic(
    mock_init_environment_for_install_tests,
    is_virtualenv, has_pipx, has_pipenv,
    expected_install_cmd_part
):
    mock_run, mock_path_instance, mock_sys_executable, mock_os_environ_dict, mock_check_cmd_exists = mock_init_environment_for_install_tests

    # Configure virtualenv detection
    if is_virtualenv:
        prefix_patch = patch("sys.prefix", "/path/to/venv")
        base_prefix_patch = patch("sys.base_prefix", "/path/to/system")
        mock_os_environ_dict["VIRTUAL_ENV"] = "/path/to/venv"
    else:
        prefix_patch = patch("sys.prefix", "/path/to/system")
        base_prefix_patch = patch("sys.base_prefix", "/path/to/system")
        if "VIRTUAL_ENV" in mock_os_environ_dict:
            del mock_os_environ_dict["VIRTUAL_ENV"]

    with prefix_patch, base_prefix_patch:
        mock_check_cmd_exists.side_effect = lambda cmd: {
            "pipx": has_pipx,
            "pipenv": has_pipenv,
            "aider": True,
            "git": True,
            "npm": True,
            "cline": True,
            "depwire-cli": True,
        }.get(cmd, False)

        called_install_cmd = None
        def capture_install_cmd_mock(cmd, **kwargs):
            nonlocal called_install_cmd
            if "aider-install" in cmd and "install" in cmd:
                called_install_cmd = " ".join(cmd)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "mock output"
            mock_result.stderr = ""
            mock_result.configure_mock(capture_output=True, check=False, text=True)
            return mock_result
        mock_run.side_effect = capture_install_cmd_mock

        # Manually call install_pip_package to test its logic directly
        with patch("builtins.print"):
            install_pip_package("aider-install")

        assert called_install_cmd is not None
        assert expected_install_cmd_part in called_install_cmd

# --- Test Cases for other CLI commands (basic checks) ---

@patch("llm_agent_toolkit.cli.run_command")
@patch("llm_agent_toolkit.cli.resolve_api_key")
@patch("llm_agent_toolkit.cli.build_query_command")
def test_handle_query(mock_build_query, mock_resolve_api_key, mock_run_command):
    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.prompt = "What is the weather?"
    mock_args.api_key = "test_key"
    mock_args.model = "gpt-4o"
    mock_args.extra_aider_arg = ["--flag"]
    mock_args.no_log = False
    mock_args.print_command = False

    mock_api_key = "resolved_key"
    mock_resolve_api_key.return_value = mock_api_key
    mock_run_command.return_value = 0

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider query command"
    mock_build_query.return_value = mock_command

    return_code = handle_query(mock_args)

    assert return_code == 0

@patch("llm_agent_toolkit.cli.ensure_clean_worktree")
@patch("llm_agent_toolkit.cli.resolve_api_key")
@patch("llm_agent_toolkit.cli.build_change_command")
@patch("llm_agent_toolkit.cli.run_command")
def test_handle_change(mock_run_command, mock_build_change, mock_resolve_api_key, mock_ensure_clean_worktree):
    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.prompt = "Fix the bug in main.py"
    mock_args.files = ["main.py"]
    mock_args.allow_dirty = False
    mock_args.api_key = "test_key"
    mock_args.model = "gpt-4o"
    mock_args.extra_aider_arg = []
    mock_args.no_log = False
    mock_args.print_command = False

    mock_api_key = "resolved_key"
    mock_resolve_api_key.return_value = mock_api_key
    mock_run_command.return_value = 0

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider change command"
    mock_build_change.return_value = mock_command

    return_code = handle_change(mock_args)

    assert return_code == 0

@patch("llm_agent_toolkit.cli.write_rules_file")
def test_handle_write_rules(mock_write_rules_file):
    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.path = "my_rules.md"
    mock_args.force = True

    return_code = handle_write_rules(mock_args)

    assert return_code == 0
    mock_write_rules_file.assert_called_once_with(Path("my_rules.md"), force=True)

@patch("subprocess.run")
@patch("pathlib.Path")
def test_handle_start(mock_path, mock_subprocess_run):
    mock_path.return_value.resolve.return_value.parents.__getitem__.return_value = Path("scripts")
    mock_path.return_value.name = "scripts"

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.tui = True
    mock_args.remote = False
    mock_args.split = False
    mock_args.print_command = True

    mock_run_result = MagicMock()
    mock_run_result.returncode = 0
    mock_subprocess_run.return_value = mock_run_result

    with patch("builtins.print"):
        return_code = handle_start(mock_args)

    assert return_code == 0

@patch("subprocess.run")
@patch("pathlib.Path")
@patch("llm_agent_toolkit.cli._short_hostname")
@patch("llm_agent_toolkit.cli._shell")
def test_handle_tmux(mock_shell, mock_short_hostname, mock_path, mock_subprocess_run):
    mock_shell.return_value = "bash"
    mock_short_hostname.return_value = "myhost"
    mock_path.return_value.name = "winkr"

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.tui = False
    mock_args.split = False
    mock_args.print_command = True

    mock_subprocess_run.return_value = MagicMock(returncode=0)

    with patch("builtins.print"):
        return_code = handle_tmux(mock_args)

    assert return_code == 0

def test_build_parser():
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_build_parser_has_architect_subcommand():
    """Verify the architect subcommand is registered in the parser."""
    parser = build_parser()
    # Parse a minimal architect invocation to confirm the subcommand exists
    args = parser.parse_args(["architect", "plan this"])
    assert args.command == "architect"
    assert args.prompt == "plan this"
    assert args.files == []
    assert args.allow_dirty is False
    assert args.print_command is False
    assert args.no_log is False
    assert args.extra_aider_arg == []


def test_build_parser_architect_with_files():
    """Verify architect subcommand accepts files."""
    parser = build_parser()
    args = parser.parse_args(["architect", "plan this", "src/foo.py", "src/bar.py"])
    assert args.command == "architect"
    assert args.prompt == "plan this"
    assert args.files == ["src/foo.py", "src/bar.py"]


def test_build_parser_architect_with_flags():
    """Verify architect subcommand accepts flags."""
    parser = build_parser()
    args = parser.parse_args([
        "architect",
        "--allow-dirty",
        "--print-command",
        "--no-log",
        "--model", "gpt-4o",
        "plan this",
    ])
    assert args.command == "architect"
    assert args.allow_dirty is True
    assert args.print_command is True
    assert args.no_log is True
    assert args.model == "gpt-4o"
    assert args.prompt == "plan this"
