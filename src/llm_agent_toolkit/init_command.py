import argparse
import subprocess
import sys
import os
from pathlib import Path
import importlib.resources

# Import the write_rules_file function from the rules module
from .rules import write_rules_file

# Placeholder for potential future configuration loading
# from .config import Config

# Placeholder for logging utilities
# from .logging_utils import setup_logger

def check_command_exists(command: str) -> bool:
    """Checks if a command exists in the system's PATH."""
    try:
        # Use 'command -v' which is standard and safer without shell=True
        # Check if the command exists and returns 0
        result = subprocess.run(["command", "-v", command], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        # 'command' itself not found, highly unlikely on most systems
        return False

def install_npm_package(package_name: str, global_install: bool = True):
    """Installs an npm package."""
    print(f"Attempting to install {package_name}...")
    cmd = ["npm", "install"]
    if global_install:
        cmd.append("-g")
    cmd.append(package_name)
    try:
        # Use shell=True for npm to ensure it finds the correct executable in PATH
        subprocess.run(cmd, check=True, capture_output=True, text=True, shell=True)
        print(f"{package_name} installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package_name}: {e.stderr}")
        raise

def install_pip_package(package_name: str):
    """Installs a pip package."""
    print(f"Attempting to install {package_name}...")
    # Using --user to avoid needing sudo for global installs
    # Ensure we use the python interpreter associated with the current environment
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
    cmd = [sys.executable, "-m", "aider_install"]
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
        write_rules_file(".clinerules", force=True)
        print(".clinerules file created/updated successfully.")
    except Exception as e:
        print(f"Error creating .clinerules file: {e}", file=sys.stderr)
        raise

def handle_init(args: argparse.Namespace) -> int:
    """
    Handles the 'winkr init' command.
    Checks for and installs dependencies, initializes Git, and creates .clinerules.
    """
    print("Initializing winkr project environment...")

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
    other_dependencies = {
        "cline": (install_npm_package, "cline"),
        "depwire-cli": (install_npm_package, "depwire-cli"),
        "git": (None, None) # Git is checked differently
    }

    for dep_name, (install_func, package_name) in other_dependencies.items():
        if dep_name == "git":
            if not check_command_exists("git"):
                print("Git is not found. Please install Git to initialize the repository.")
                # Depending on requirements, we might exit or prompt user to install git
                # For now, we'll just warn and proceed, assuming git init will fail if not present.
                # A more robust solution would be to guide the user on how to install git.
                pass # Proceeding, git init will likely fail if not installed
        elif not check_command_exists(dep_name):
            print(f"{dep_name} not found.")
            if install_func and package_name:
                try:
                    install_func(package_name)
                except Exception as e:
                    print(f"Failed to install {dep_name}. Please install it manually. Error: {e}")
                    return 1 # Indicate failure
            else:
                print(f"Please install {dep_name} manually.")
                return 1 # Indicate failure
        else:
            print(f"{dep_name} is already installed.")

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

    # Simulate running the command
    exit_code = handle_init(mock_args)
    sys.exit(exit_code)