#!/usr/bin/env bash
set -euo pipefail

python -m pip install --user aider-install
python -m aider_install

echo "Aider installation complete."
