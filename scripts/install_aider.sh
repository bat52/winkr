#!/usr/bin/env bash
set -euo pipefail

# Function to check if a command exists
check_command_exists() {
    command -v "$1" >/dev/null 2>&1
}

PACKAGE_NAME="aider-install"

echo "Attempting to install ${PACKAGE_NAME}..."

INSTALL_CMD=""

# Detect if running in a virtual environment
# VIRTUAL_ENV is the standard environment variable for virtual environments.
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Detected virtual environment. Using 'pip install'."
    # Use 'python -m pip' to ensure we use the pip associated with the current python interpreter
    INSTALL_CMD="python -m pip install ${PACKAGE_NAME}"
elif check_command_exists "pipx"; then
    echo "Found pipx. Using 'pipx install'."
    INSTALL_CMD="pipx install ${PACKAGE_NAME}"
elif check_command_exists "pipenv"; then
    echo "Found pipenv. Using 'pipenv install'."
    # pipenv install will create a virtualenv if one doesn't exist for the package.
    # This is a reasonable fallback for installing CLI tools.
    INSTALL_CMD="pipenv install ${PACKAGE_NAME}"
else
    echo "pipx and pipenv not found. Falling back to 'pip install --user'."
    INSTALL_CMD="python -m pip install --user ${PACKAGE_NAME}"
fi

# Execute the determined installation command
eval "${INSTALL_CMD}"

echo "${PACKAGE_NAME} installed successfully."

# Run the post-installation step
echo "Running Aider post-installation step..."
if check_command_exists "aider-install"; then
    aider-install
else
    # Fallback to module execution
    python -m aider_install.main
fi
echo "Aider post-installation complete."
