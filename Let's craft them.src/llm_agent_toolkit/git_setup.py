"""SSH key generation and Git remote setup."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _ssh_key_path() -> Path:
    """Return the default SSH key path."""
    return Path.home() / ".ssh" / "id_ed25519"


def _ssh_key_exists() -> bool:
    """Check if an SSH key already exists."""
    return _ssh_key_path().exists()


def _generate_ssh_key() -> bool:
    """Generate a new Ed25519 SSH key. Returns True on success."""
    key_path = _ssh_key_path()
    # Ensure .ssh directory exists with proper permissions
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", ""],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _get_public_key() -> str | None:
    """Read the public key content. Returns None if file doesn't exist."""
    pub_path = _ssh_key_path().with_suffix(".pub")
    if not pub_path.exists():
        return None
    return pub_path.read_text().strip()


def _detect_remote_url() -> str | None:
    """Detect the Git remote origin URL. Returns None if not found."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _test_ssh_connection(host: str = "github.com") -> bool:
    """Test SSH connection to the given host. Returns True if successful."""
    try:
        result = subprocess.run(
            ["ssh", "-T", f"git@{host}"],
            capture_output=True,
            text=True,
            check=False,
        )
        # SSH returns non-zero even on success for some hosts (GitHub returns 1 with success message)
        # Check for success message in stderr
        return "successfully authenticated" in result.stderr.lower() or result.returncode == 0
    except FileNotFoundError:
        return False


def _host_from_remote(remote_url: str) -> str | None:
    """Extract hostname from a Git remote URL."""
    # Handle git@github.com:user/repo.git
    if remote_url.startswith("git@"):
        return remote_url.split("@")[1].split(":")[0]
    # Handle https://github.com/user/repo.git
    if remote_url.startswith("https://"):
        return remote_url.split("https://")[1].split("/")[0]
    return None


def setup_git_ssh() -> int:
    """Main entry point for the git-setup command."""
    print("🔑 Git SSH Setup\n")

    # Step 1: Check/Create SSH key
    if _ssh_key_exists():
        print("✅ SSH key already exists.")
    else:
        print("🔨 Generating new Ed25519 SSH key...")
        if _generate_ssh_key():
            print("✅ SSH key generated successfully.")
        else:
            print("❌ Failed to generate SSH key.", file=sys.stderr)
            return 1

    # Step 2: Display public key
    pub_key = _get_public_key()
    if pub_key is None:
        print("❌ Could not read public key.", file=sys.stderr)
        return 1

    print(f"\n📋 Your public SSH key:\n")
    print(f"   {pub_key}")
    print()

    # Step 3: Detect remote and give instructions
    remote_url = _detect_remote_url()
    if remote_url:
        host = _host_from_remote(remote_url)
        if host:
            print(f"🌐 Detected remote: {remote_url}")
            print(f"   Host: {host}")
            print()
            if "github" in host:
                print("   ➡️  Add this key to GitHub: https://github.com/settings/ssh/new")
            elif "gitlab" in host:
                print("   ➡️  Add this key to GitLab: https://gitlab.com/-/profile/keys")
            else:
                print(f"   ➡️  Add this key to your Git provider ({host}).")
        else:
            print(f"🌐 Detected remote: {remote_url}")
            print("   ➡️  Add this key to your Git provider.")
    else:
        print("🌐 No Git remote 'origin' detected.")
        print("   ➡️  Add this key to your Git provider (GitHub/GitLab/etc.).")

    print()
    input("⏸️  Press Enter after you've added the key to your Git provider...")

    # Step 4: Test SSH connection
    if remote_url:
        host = _host_from_remote(remote_url)
        if host:
            print(f"\n🔍 Testing SSH connection to {host}...")
            if _test_ssh_connection(host):
                print(f"✅ SSH connection to {host} successful!")
                print("   You can now use 'git push' without friction.")
                return 0
            else:
                print(f"❌ SSH connection to {host} failed.", file=sys.stderr)
                print("   Please check that you added the key correctly.", file=sys.stderr)
                return 1

    # If we couldn't detect host, try common ones
    for host in ["github.com", "gitlab.com"]:
        print(f"\n🔍 Testing SSH connection to {host}...")
        if _test_ssh_connection(host):
            print(f"✅ SSH connection to {host} successful!")
            print("   You can now use 'git push' without friction.")
            return 0

    print("\n⚠️  Could not verify SSH connection automatically.")
    print("   Try running: ssh -T git@github.com")
    return 0
