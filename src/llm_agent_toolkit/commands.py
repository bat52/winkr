"""Logic for executing external commands like editor and browser."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def run_editor(file_path: str | Path) -> int:
    """Find and run the configured editor for the given file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1

    # Determine editor: use EDITOR env var, or default to common ones
    editor = os.environ.get("EDITOR")
    if not editor:
        # Try to find a common editor, fallback to nano
        if Path("/usr/bin/code").exists():  # VS Code
            editor = "code"
        elif Path("/usr/bin/nano").exists():  # Nano
            editor = "nano"
        else:
            editor = "nano"  # Default fallback

    try:
        # Use subprocess.run to open the editor
        subprocess.run([editor, str(path)], check=True)
        print(f"Opened {path} in {editor}")
        return 0
    except FileNotFoundError:
        print(
            f"Error: Editor '{editor}' not found. Please install it or set the EDITOR environment variable.",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Error opening file in editor: {e}", file=sys.stderr)
        return e.returncode


def run_browser(path: str | Path = ".") -> int:
    """Open a file browser (ranger) at the given path."""
    target_path = Path(path)
    if not target_path.exists():
        print(f"Error: Path not found: {target_path}", file=sys.stderr)
        return 1

    # Determine file browser: use RANGER_PATH env var, or default to ranger
    browser = os.environ.get("WINKR_BROWSER", "ranger")

    try:
        # Use subprocess.run to open the file browser
        subprocess.run([browser, str(target_path)], check=True)
        print(f"Opened {target_path} in {browser}")
        return 0
    except FileNotFoundError:
        print(
            f"Error: File browser '{browser}' not found. Please install it or set the WINKR_BROWSER environment variable.",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Error opening file browser: {e}", file=sys.stderr)
        return e.returncode
