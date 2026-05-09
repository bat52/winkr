from __future__ import annotations

import argparse
import subprocess
import sys
import os
from pathlib import Path
import importlib.resources
import shutil

# Import the write_rules_file function from the rules module
from .rules import write_rules_file

from .config_manager import WinkrConfig, load_config

# Placeholder for logging utilities
# from .logging_utils import setup_logger

def check_command_exists(command: str) -> bool:
    """Checks if a command exists in the system's PATH."""
    # Use shutil.which for cross-platform reliability
    return shutil.which(command) is not None

def install_npm_package(package_name: str):
    """Installs an npm package, trying global then local installs."""
    print(f"Attempting to install {package_name} globally...")
    global_cmd = ["npm", "install", "-g", package_name]
    try:
        subprocess.run(global_cmd, check=True, capture_output=True, text=True, shell=True)
        print(f"{package_name} installed successfully globally.")
        return
    except subprocess.CalledProcessError as e:
        print(f"Global installation of {package_name} failed: {e.stderr}")
        print(f"Attempting local installation of {package_name}...")
        local_cmd = ["npm", "install", package_name]
        try:
            subprocess.run(local_cmd, check=True, capture_output=True, text=True, shell=True)
            print(f"{package_name} installed successfully locally.")
            return
        except subprocess.CalledProcessError as e_local:
            print(f"Local installation of {package_name} also failed: {e_local.stderr}")
            # Provide a more informative error message
            error_message = (
                f"Failed to install {package_name} globally and locally.\n"
                "Please try installing it manually:\n"
                f"  sudo npm install -g {package_name}  (for global install)\n"
                f"  npm install {package_name}          (for local install)\n"
                f"Error details:\n{e_local.stderr}"
            )
            raise RuntimeError(error_message) from e_local

def install_pip_package(package_name: str):
    """Installs a pip package with environment-aware logic."""
    print(f"Attempting to install {package_name}...")

    # Detect if running in a virtual environment
    is_virtualenv = sys.prefix != sys.base_prefix or os.environ.get("VIRTUAL_ENV")
    cmd = []

    if is_virtualenv:
        print("Detected virtual environment. Using 'pip install'.")
        cmd = [sys.executable, "-m", "pip", "install", package_name]
    else:
        print("Not in a virtual environment. Checking for pipx and pipenv.")
        if check_command_exists("pipx"):
            print("Found pipx. Using 'pipx install'.")
            cmd = ["pipx", "install", package_name]
        elif check_command_exists("pipenv"):
            print("Found pipenv. Using 'pipenv install'.")
            cmd = ["pipenv", "install", package_name]
        else:
            print("pipx and pipenv not found. Falling back to 'pip install --user'.")
            cmd = [sys.executable, "-m", "pip", "install", "--user", package_name]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"{package_name} installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package_name}: {e.stderr}")
        raise

def run_aider_post_install():
    """Runs the post-installation step for Aider."""
    print("Running Aider post-installation step...")
    # Check if aider-install is available as a command first (for pipx/pipenv/user installs)
    if check_command_exists("aider-install"):
        cmd = ["aider-install"]
    else:
        # Fallback to module execution
        # Note: aider-install package provides aider_install.main module
        cmd = [sys.executable, "-m", "aider_install.main"]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Aider post-installation complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Aider post-installation: {e.stderr}")
        raise

def initialize_git_repo():
    """Initializes a Git repository if one does not exist."""
    if not Path(".git").exists():
        print("Initializing new Git repository...")
        try:
            # git init works fine without shell=True
            subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
            print("Git repository initialized.")
        except subprocess.CalledProcessError as e:
            print(f"Error initializing Git repository: {e.stderr}")
            raise
    else:
        print("Git repository already exists.")

def create_clinerules_file():
    """Creates or overwrites the .clinerules file using the internal write_rules_file function."""
    print("Creating/updating .clinerules file...")
    try:
        # Use the internal write_rules_file function.
        # The 'force=True' is implied by the plan's requirement to overwrite.
        write_rules_file(Path(".clinerules"), force=True)
        print(".clinerules file created/updated successfully.")
    except Exception as e:
        print(f"Error creating .clinerules file: {e}", file=sys.stderr)
        raise

def handle_init(args: argparse.Namespace, config: WinkrConfig | None = None) -> int:
    """
    Handles the 'winkr init' command.
    Checks for and installs dependencies, initializes Git, and creates .clinerules.
    """
    print("Initializing winkr project environment...")

    # Load project config if available
    if config is None:
        config = load_config()
    if config is not None:
        print(f"  Loaded configuration from .winkr/config.json")
        print(f"  Orchestrator: {config.orchestrator_command_name}")
        print(f"  Tiers: REASONING={config.tier_reasoning}, CODING={config.tier_coding}, FAST={config.tier_fast}")
    else:
        print("  No .winkr/config.json found — using defaults.")

    # 1. Dependency Checks and Installations
    # Handle Aider separately due to its two-step installation process.
    if not check_command_exists("aider"):
        print("Aider not found.")
        try:
            install_pip_package("aider-install")
            run_aider_post_install()
        except Exception as e:
            print(f"Failed to install Aider. Please install it manually. Error: {e}")
            return 1
    else:
        print("Aider is already installed.")

    # Handle other dependencies
    # Map dependency name to its installation function.
    # For npm packages, the function is install_npm_package, and the package name is the same as dep_name.
    # Git is handled separately.
    # Map command name to its installation package name.
    dependency_packages = {
        "cline": "cline",
        "depwire": "depwire-cli",
    }

    # Check and install npm dependencies
    for cmd_name, package_name in dependency_packages.items():
        if not check_command_exists(cmd_name):
            print(f"{cmd_name} not found.")
            try:
                install_npm_package(package_name)
            except Exception as e:
                print(f"Failed to install {cmd_name}. Please install it manually. Error: {e}")
                return 1 # Indicate failure
        else:
            print(f"{cmd_name} is already installed.")

    # Handle Git separately
    if not check_command_exists("git"):
        print("Git is not found. Please install Git to initialize the repository.")
        # Depending on requirements, we might exit or prompt user to install git
        # For now, we'll just warn and proceed, assuming git init will fail if not present.
        # A more robust solution would be to guide the user on how to install git.
        pass # Proceeding, git init will likely fail if not installed

    # 2. Git Repository Initialization
    try:
        initialize_git_repo()
    except Exception as e:
        print(f"Failed to initialize Git repository. Error: {e}")
        return 1

    # 3. Create .clinerules file
    try:
        create_clinerules_file()
    except Exception as e:
        print(f"Failed to create .clinerules file. Error: {e}")
        return 1

    # 4. Install enforcer pre-commit hooks
    print("Installing enforcer pre-commit hooks...")
    hook_installer = Path(__file__).resolve().parents[2] / "scripts" / "install_hooks.sh"
    if hook_installer.exists():
        try:
            subprocess.run([str(hook_installer)], check=True, capture_output=True, text=True)
            print("Enforcer pre-commit hook installed.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: could not install pre-commit hook: {e.stderr.strip()}")
        except Exception as e:
            print(f"Warning: could not install pre-commit hook: {e}")
    else:
        print(f"Warning: hook installer not found at {hook_installer}")

    print("\nWinkr project initialization complete!")
    print("You can now start developing your project.")
    return 0 # Indicate success

if __name__ == "__main__":
    # This is a basic setup for testing the script directly.
    # In the actual CLI, this would be handled by the main parser.
    parser = argparse.ArgumentParser(description="Initialize winkr project.")
    # Add arguments here if needed for init command, e.g., --force
    # parser.add_argument('--force', action='store_true', help='Force re-initialization')

    # Mock arguments for testing
    mock_args = argparse.Namespace()
    # mock_args.force = False # Example of setting an argument

    exit_code = handle_init(mock_args)
    sys.exit(exit_code)