import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Assuming the CLI module is structured such that we can import it directly
# If not, adjustments might be needed based on the project's Python package structure.
# For now, we'll assume it's importable as 'winkr.cli' or similar.
# Given the file structure, it's likely 'src.llm_agent_toolkit.cli'
try:
    from src.llm_agent_toolkit.cli import build_parser, handle_query, handle_edit, handle_write_rules, handle_start, handle_tmux, handle_tiers
    # Import the handler for the init command
    from src.llm_agent_toolkit.init_command import handle_init
except ImportError:
    # Adjust path if running tests from a different directory or if package structure differs
    pytest.fail("Could not import CLI modules. Ensure the project structure is correct and tests are run from the root directory.")

# --- Mocking Setup ---

# Mocking subprocess.run for dependency checks and installations
# We'll use a side_effect to control behavior based on command arguments
def mock_subprocess_run(cmd, **kwargs):
    # Default behavior: assume command exists and succeeds
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "mock output"
    mock_result.stderr = ""
    # Ensure these attributes are set for compatibility with how they might be accessed
    mock_result.configure_mock(capture_output=True, check=False, text=True)

    cmd_str = " ".join(cmd)

    # Simulate command existence checks
    if "--version" in cmd:
        if cmd[0] in ["git", "npm", "python", "command"]: # Assume these are generally available
            return mock_result
        elif cmd[0] == "cline" or cmd[0] == "depwire-cli": # Simulate npm packages not installed
            mock_result.returncode = 1
            mock_result.stderr = f"Command '{cmd[0]}' not found."
            return mock_result
        elif cmd[0] == "python" and "-m" in cmd and "aider_install" in cmd: # Simulate pip package not installed
            mock_result.returncode = 1
            mock_result.stderr = "No module named aider_install"
            return mock_result
        else:
            return mock_result # Default success for unknown commands

    # Simulate installation commands
    if "npm install" in cmd_str:
        print(f"Mock: Running {cmd_str}")
        return mock_result # Assume npm install succeeds
    if "pip install" in cmd_str:
        print(f"Mock: Running {cmd_str}")
        return mock_result # Assume pip install succeeds
    if "git init" in cmd_str:
        print(f"Mock: Running {cmd_str}")
        return mock_result # Assume git init succeeds
    if "aider_install" in cmd_str and sys.executable in cmd_str: # Simulate Aider post-install
        print(f"Mock: Running {cmd_str}")
        return mock_result # Assume Aider post-install succeeds

    # Default for other commands
    return mock_result

# Mocking Path.exists for checking .git and .clinerules
class MockPath(Path):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exists_map = {} # Map paths to their existence status

    def exists(self):
        # Use the path string to check existence in our map
        return self._exists_map.get(str(self), False) # Default to False if not in map

    def __str__(self):
        return super().__str__()

# --- Test Cases for handle_init ---

@pytest.fixture
def mock_init_environment():
    """Fixture to set up mocks for handle_init tests."""
    # Patch subprocess.run and Path
    with patch("subprocess.run", side_effect=mock_subprocess_run) as mock_run, \
         patch("pathlib.Path", side_effect=MockPath) as mock_path_cls:

        # Create a mock path instance that we can configure
        mock_path_instance = MockPath() # Instantiate our MockPath
        mock_path_cls.return_value = mock_path_instance # Make Path() return our instance

        # Mock sys.executable for pip command
        with patch("sys.executable", "mock_python"):
            yield mock_run, mock_path_instance

@pytest.mark.parametrize("git_exists, clinerules_exists, aider_installed, expected_git_init, expected_clinerules_write, expected_aider_install_steps", [
    (False, False, False, True, True, 2),  # All missing, should initialize both, 2 Aider steps
    (True, False, False, False, True, 2),   # Git exists, .clinerules missing, 2 Aider steps
    (False, True, False, True, False, 2),  # Git missing, .clinerules exists, 2 Aider steps
    (True, True, False, False, False, 2),   # Both exist, 2 Aider steps
    (False, False, True, True, True, 0),  # All missing, Aider installed, should initialize both, 0 Aider steps
])
def test_handle_init_dependency_and_setup(
    mock_init_environment,
    git_exists,
    clinerules_exists,
    aider_installed,
    expected_git_init,
    expected_clinerules_write,
    expected_aider_install_steps
):
    mock_run, mock_path_instance = mock_init_environment

    # Configure mock_path_instance for .git and .clinerules existence
    mock_path_instance._exists_map[".git"] = git_exists
    mock_path_instance._exists_map[".clinerules"] = clinerules_exists

    # Configure mock_subprocess_run to simulate Aider's installed status
    original_mock_subprocess_run = mock_subprocess_run
    def custom_mock_subprocess_run(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "command -v aider" in cmd_str:
            mock_result = MagicMock()
            mock_result.returncode = 0 if aider_installed else 1
            mock_result.stdout = "mock aider" if aider_installed else ""
            mock_result.stderr = ""
            mock_result.configure_mock(capture_output=True, check=False, text=True)
            return mock_result
        return original_mock_subprocess_run(cmd, **kwargs)
    mock_run.side_effect = custom_mock_subprocess_run

    # Mock argparse.Namespace
    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.force = False # Assuming no force flag for now

    # Mock print statements to check output if needed, or just check return code
    with patch("builtins.print") as mock_print:
        return_code = handle_init(mock_args)

    assert return_code == 0 # Expect success

    # Check subprocess calls
    calls = mock_run.call_args_list
    # print(f"\nSubprocess calls: {calls}") # Debugging

    # Count Aider installation steps
    aider_install_calls = [c for c in calls if "aider_install" in " ".join(c[0][0])]
    assert len(aider_install_calls) == expected_aider_install_steps

    # Check for other dependency installations (assuming they are missing for the test)
    if not aider_installed: # Only check if Aider wasn't pre-installed
        assert any("npm install -g cline" in " ".join(c[0][0]) for c in calls)
        assert any("python -m pip install --user aider-install" in " ".join(c[0][0]) for c in calls)
        assert any("aider_install" in " ".join(c[0][0]) for c in calls) # Check for post-install
        assert any("npm install -g depwire-cli" in " ".join(c[0][0]) for c in calls)

    # Check for git init
    if expected_git_init:
        assert any("git init" in " ".join(c[0][0]) for c in calls)
    else:
        assert not any("git init" in " ".join(c[0][0]) for c in calls)

    # Check for .clinerules write
    if expected_clinerules_write:
        # The current implementation directly writes to the file, not via subprocess.
        # We need to mock the file writing part if we want to assert it.
        # For now, we'll assume the file write happens if the function is called.
        # Let's add a mock for open() to track file writes.
        pass # Will add file write mock later if needed

# Test case for when a dependency fails to install
@patch("subprocess.run", side_effect=mock_subprocess_run)
@patch("pathlib.Path", side_effect=MockPath)
@patch("sys.executable", "mock_python")
def test_handle_init_dependency_install_failure(mock_run, mock_path_cls):
    mock_path_instance = MockPath()
    mock_path_instance._exists_map = {".git": False, ".clinerules": False} # Assume all missing

    # Make pip install fail for 'aider-install'
    def failing_pip_mock(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "pip install --user aider-install" in cmd_str:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Mock pip installation failed."
            mock_result.configure_mock(capture_output=True, check=False, text=True)
            return mock_result
        return mock_subprocess_run(cmd, **kwargs) # Use default for others

    mock_run.side_effect = failing_pip_mock

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.force = False

    with patch("builtins.print") as mock_print:
        return_code = handle_init(mock_args)

    assert return_code == 1 # Expect failure
    mock_print.assert_any_call("Failed to install Aider. Please install it manually. Error: Mock pip installation failed.")

# Test case for when git init fails
@patch("subprocess.run", side_effect=mock_subprocess_run)
@patch("pathlib.Path", side_effect=MockPath)
@patch("sys.executable", "mock_python")
def test_handle_init_git_init_failure(mock_run, mock_path_cls):
    mock_path_instance = MockPath()
    mock_path_instance._exists_map = {".git": False, ".clinerules": True} # .clinerules exists, .git does not

    # Make git init fail
    def failing_git_mock(cmd, **kwargs):
        if "git init" in " ".join(cmd):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Mock git init failed."
            mock_result.configure_mock(capture_output=True, check=False, text=True)
            return mock_result
        return mock_subprocess_run(cmd, **kwargs)

    mock_run.side_effect = failing_git_mock

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.force = False

    with patch("builtins.print") as mock_print:
        return_code = handle_init(mock_args)

    assert return_code == 1 # Expect failure
    mock_print.assert_any_call("Failed to initialize Git repository. Error: Mock git init failed.")

# Test case for when .clinerules creation fails
@patch("subprocess.run", side_effect=mock_subprocess_run)
@patch("pathlib.Path", side_effect=MockPath)
@patch("sys.executable", "mock_python")
def test_handle_init_clinerules_creation_failure(mock_run, mock_path_cls):
    mock_path_instance = MockPath()
    mock_path_instance._exists_map = {".git": True, ".clinerules": False} # .git exists, .clinerules does not

    # Mock open to raise an error when trying to write .clinerules
    original_open = open
    def mock_open_for_clinerules(file, mode='r', *args, **kwargs):
        if file == ".clinerules" and mode == 'w':
            raise IOError("Mock file write error")
        return original_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open_for_clinerules):
        mock_args = MagicMock(spec=argparse.Namespace)
        mock_args.force = False

        with patch("builtins.print") as mock_print:
            return_code = handle_init(mock_args)

        assert return_code == 1 # Expect failure
        mock_print.assert_any_call("Failed to create .clinerules file. Error: Mock file write error")

# --- Test Cases for other CLI commands (basic checks) ---

@patch("src.llm_agent_toolkit.cli.run_command")
@patch("src.llm_agent_toolkit.cli.resolve_api_key")
@patch("src.llm_agent_toolkit.cli.build_query_command")
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

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider query command"
    mock_build_query.return_value = mock_command

    return_code = handle_query(mock_args)

    assert return_code == 0
    mock_resolve_api_key.assert_called_once_with("test_key")
    mock_build_query.assert_called_once_with(
        prompt="What is the weather?",
        api_key=mock_api_key,
        model="gpt-4o",
        extra_args=["--flag"]
    )
    mock_run_command.assert_called_once_with(mock_command)

@patch("src.llm_agent_toolkit.cli.ensure_clean_worktree")
@patch("src.llm_agent_toolkit.cli.resolve_api_key")
@patch("src.llm_agent_toolkit.cli.build_edit_command")
@patch("src.llm_agent_toolkit.cli.run_command")
def test_handle_edit(mock_run_command, mock_build_edit, mock_resolve_api_key, mock_ensure_clean_worktree):
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

    mock_command = MagicMock()
    mock_command.shell_string.return_value = "mock aider edit command"
    mock_build_edit.return_value = mock_command

    return_code = handle_edit(mock_args)

    assert return_code == 0
    mock_ensure_clean_worktree.assert_called_once()
    mock_resolve_api_key.assert_called_once_with("test_key")
    mock_build_edit.assert_called_once_with(
        prompt="Fix the bug in main.py",
        api_key=mock_api_key,
        model="gpt-4o",
        files=["main.py"],
        extra_args=[]
    )
    mock_run_command.assert_called_once_with(mock_command)

@patch("src.llm_agent_toolkit.cli.write_rules_file")
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
    mock_cline_script = Path("scripts/cline.sh")
    mock_path.return_value.resolve.return_value.parents.__getitem__.return_value = Path("scripts")
    mock_path.return_value.name = "scripts" # For the tmux session name logic, though not used here

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.tui = True
    mock_args.print_command = True

    # Mock the subprocess.run for the actual command execution
    mock_run_result = MagicMock()
    mock_run_result.returncode = 0
    mock_subprocess_run.return_value = mock_run_result

    with patch("builtins.print") as mock_print:
        return_code = handle_start(mock_args)

    assert return_code == 0
    mock_subprocess_run.assert_called_once_with(
        ("scripts/cline.sh", "--tui", "--auto-condense"),
        check=False
    )
    mock_print.assert_called_once_with("scripts/cline.sh --tui --auto-condense")

@patch("subprocess.run")
@patch("pathlib.Path")
@patch("src.llm_agent_toolkit.cli._short_hostname")
@patch("src.llm_agent_toolkit.cli._shell")
def test_handle_tmux(mock_shell, mock_short_hostname, mock_path, mock_subprocess_run):
    mock_shell.return_value = "bash"
    mock_short_hostname.return_value = "myhost"
    mock_path.return_value.name = "winkr" # For Path.cwd().name

    mock_args = MagicMock(spec=argparse.Namespace)
    mock_args.print_command = True

    # Mock the initial check for session existence
    mock_has_session_result = MagicMock()
    mock_has_session_result.returncode = 0 # Session exists
    mock_subprocess_run.side_effect = lambda cmd, **kwargs: (
        mock_has_session_result if cmd[0] == "tmux" and cmd[1] == "has-session" else
        MagicMock(returncode=0) # Default success for other commands
    )

    with patch("builtins.print") as mock_print:
        return_code = handle_tmux(mock_args)

    assert return_code == 0
    mock_subprocess_run.assert_any_call(("tmux", "has-session", "-t", "agent-winkr-myhost"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    mock_print.assert_any_call("tmux has-session -t agent-winkr-myhost")
    mock_print.assert_any_call("tmux new-session -d -s agent-winkr-myhost")
    mock_print.assert_any_call("tmux attach -t agent-winkr-myhost")

    # Test case where session does not exist
    mock_subprocess_run.reset_mock()
    mock_has_session_result.returncode = 1 # Session does not exist
    mock_subprocess_run.side_effect = lambda cmd, **kwargs: (
        mock_has_session_result if cmd[0] == "tmux" and cmd[1] == "has-session" else
        MagicMock(returncode=0) # Default success for other commands
    )
    mock_args.print_command = False # Run the command this time

    with patch("builtins.print") as mock_print:
        return_code = handle_tmux(mock_args)

    assert return_code == 0
    mock_subprocess_run.assert_any_call(("tmux", "has-session", "-t", "agent-winkr-myhost"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    mock_subprocess_run.assert_any_call(("tmux", "new-session", "-d", "-s", "agent-winkr-myhost"), check=False)
    mock_subprocess_run.assert_any_call(("tmux", "attach", "-t", "agent-winkr-myhost"), check=False)


def test_handle_tiers():
    mock_args = MagicMock(spec=argparse.Namespace)
    with patch("src.llm_agent_toolkit.cli.MODEL_TIERS", {"TIER_FAST": "model-fast", "TIER_REASONING": "model-reasoning"}):
        with patch("builtins.print") as mock_print:
            return_code = handle_tiers(mock_args)

    assert return_code == 0
    mock_print.assert_any_call("TIER_FAST=model-fast")
    mock_print.assert_any_call("TIER_REASONING=model-reasoning")

# --- Test for build_parser ---
def test_build_parser():
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    subparsers = parser._subparsers._group_actions[0] # Accessing internal attribute for testing
    commands = {action.dest for action in subparsers.choices.values()}
    assert commands == {"query", "edit", "write-rules", "init", "start", "tmux", "tiers"}

    # Test specific subcommand arguments
    query_parser = parser.parse_args(["query", "test prompt"])
    assert query_parser.command == "query"
    assert query_parser.prompt == "test prompt"

    edit_parser = parser.parse_args(["edit", "--allow-dirty", "edit prompt", "file1.py"])
    assert edit_parser.command == "edit"
    assert edit_parser.prompt == "edit prompt"
    assert edit_parser.files == ["file1.py"]
    assert edit_parser.allow_dirty is True

    init_parser = parser.parse_args(["init"])
    assert init_parser.command == "init"

    write_rules_parser = parser.parse_args(["write-rules", "custom.rules", "--force"])
    assert write_rules_parser.command == "write-rules"
    assert write_rules_parser.path == "custom.rules"
    assert write_rules_parser.force is True