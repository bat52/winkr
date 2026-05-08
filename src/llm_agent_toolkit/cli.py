"""Command-line interface for winkr."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .aider import build_change_command, build_query_command, run_command, validate_prompt
from .commands import run_browser, run_editor
from .config import MODEL_TIERS
from .credentials import resolve_api_key
from .enforcer import check_commits, check_pending_changes, check_worktree_block
from .git_safety import ensure_clean_worktree
from .init_command import handle_init  # Import the new handler
from .logging_utils import log_prompt
from .rules import write_rules_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="winkr",
        description="Reusable LLM agent workflow toolkit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    query = subparsers.add_parser(
        "query",
        help="Ask Aider a read-oriented question about the repository.",
    )
    add_common_aider_args(query)
    query.add_argument("prompt", help="Prompt/question to send to Aider.")
    query.set_defaults(func=handle_query)

    change = subparsers.add_parser(
        "change",
        help="Ask Aider to mutate files.",
    )
    add_common_aider_args(change)
    change.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow changes when the Git worktree is dirty.",
    )
    change.add_argument("prompt", help="Instruction to send to Aider.")
    change.add_argument(
        "files",
        nargs="*",
        help="Optional file paths to pass to Aider.",
    )
    change.set_defaults(func=handle_change)

    write_rules = subparsers.add_parser(
        "write-rules",
        help="Write the packaged reusable Cline rules to a file.",
    )
    write_rules.add_argument(
        "path",
        nargs="?",
        default=".clinerules",
        help="Output path. Defaults to .clinerules.",
    )
    write_rules.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    write_rules.set_defaults(func=handle_write_rules)

    # Add the new 'init' subcommand
    init = subparsers.add_parser(
        "init",
        help="Initialize winkr project environment.",
    )
    # No specific arguments for init command yet, but could be added later
    init.set_defaults(func=handle_init)

    # Add new 'edit' subcommand
    edit = subparsers.add_parser(
        "edit",
        help="Open a file in your default editor.",
    )
    edit.add_argument("file", help="Path to the file to edit.")
    edit.set_defaults(func=handle_edit)

    # Add new 'browse' subcommand
    browse = subparsers.add_parser(
        "browse",
        help="Open a file browser (ranger) at the given path.",
    )
    browse.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to open in the file browser. Defaults to current directory.",
    )
    browse.set_defaults(func=handle_browse)

    start = subparsers.add_parser(
        "start",
        help="Start Cline using npx.",
    )
    start.add_argument(
        "--tui",
        action="store_true",
        help="Start Cline in TUI mode with --tui --auto-condense.",
    )
    start.add_argument(
        "--print-command",
        action="store_true",
        help="Print the command instead of running it.",
    )
    start.add_argument(
        "--remote",
        action="store_true",
        help="Enable remote access for tmux session.",
    )
    start.add_argument(
        "--split",
        action="store_true",
        help="Enable dual-pane tmux session.",
    )
    start.set_defaults(func=handle_start)

    tmux = subparsers.add_parser(
        "tmux",
        help="Start or attach to a two-pane tmux agent session.",
    )
    tmux.add_argument(
        "--print-command",
        action="store_true",
        help="Print tmux commands instead of running them.",
    )
    tmux.add_argument(
        "--remote",
        action="store_true",
        help="Enable remote access for tmux session.",
    )
    tmux.add_argument(
        "--split",
        action="store_true",
        help="Enable dual-pane tmux session.",
    )
    tmux.set_defaults(func=handle_tmux)

    # Add 'enforcer' subcommand
    enforcer = subparsers.add_parser(
        "enforcer",
        help="Enforce the winkr mutation policy (pre-commit checks).",
    )
    enforcer_sub = enforcer.add_subparsers(dest="enforcer_command", required=True)

    enforcer_check = enforcer_sub.add_parser(
        "check",
        help="Check staged changes or a commit range for policy compliance.",
    )
    enforcer_check.add_argument(
        "--range",
        default=None,
        help="Git revision range to check (e.g., HEAD~5..HEAD). Default: auto.",
    )
    enforcer_check.set_defaults(func=handle_enforcer_check)

    enforcer_block = enforcer_sub.add_parser(
        "block",
        help="Blocking pre-mutation check. Exits non-zero if policy violations exist.",
    )
    enforcer_block.set_defaults(func=handle_enforcer_block)

    enforcer_install = enforcer_sub.add_parser(
        "install-hooks",
        help="Install the pre-commit hook into .git/hooks/.",
    )
    enforcer_install.set_defaults(func=handle_enforcer_install_hooks)

    tiers = subparsers.add_parser(
        "tiers",
        help="Print configured model tiers.",
    )
    tiers.set_defaults(func=handle_tiers)

    return parser


def add_common_aider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-key",
        "-k",
        default=None,
        help="API key or provider-prefixed key, e.g. openrouter=KEY.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model name or tier alias such as TIER_FAST.",
    )
    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print the Aider command instead of running it.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not write prompt metadata to .ai_logs.",
    )
    parser.add_argument(
        "--extra-aider-arg",
        action="append",
        default=[],
        help="Additional raw argument to append to the Aider invocation.",
    )


def handle_query(args: argparse.Namespace) -> int:
    validate_prompt(args.prompt)
    api_key = resolve_api_key(args.api_key)
    if api_key is None:
        print("ERROR: no API key found.", file=sys.stderr)
        return 2

    command = build_query_command(
        prompt=args.prompt,
        api_key=api_key,
        model=args.model,
        extra_args=args.extra_aider_arg,
    )

    if not args.no_log:
        log_prompt("query", args.prompt, command.shell_string())

    if args.print_command:
        print(command.shell_string())
        return 0

    return run_command(command)


def handle_change(args: argparse.Namespace) -> int:
    validate_prompt(args.prompt)
    if not args.allow_dirty:
        ensure_clean_worktree(Path.cwd())

    api_key = resolve_api_key(args.api_key)
    if api_key is None:
        print("ERROR: no API key found.", file=sys.stderr)
        return 2

    command = build_change_command(
        prompt=args.prompt,
        api_key=api_key,
        model=args.model,
        files=args.files,
        extra_args=args.extra_aider_arg,
    )

    if not args.no_log:
        log_prompt("change", args.prompt, command.shell_string())

    if args.print_command:
        print(command.shell_string())
        return 0

    print("[WINKR-CHANGE] Delegating mutation to Aider...", file=sys.stderr)
    return run_command(command)


def handle_write_rules(args: argparse.Namespace) -> int:
    path = Path(args.path)
    write_rules_file(path, force=args.force)
    print(f"Wrote {path}")
    return 0


def handle_edit(args: argparse.Namespace) -> int:
    """Handles the 'edit' command."""
    return run_editor(args.file)


def handle_browse(args: argparse.Namespace) -> int:
    """Handles the 'browse' command."""
    return run_browser(args.path)


def handle_start(args: argparse.Namespace) -> int:
    # If --tui and --remote are present, launch in tmux unless already in tmux
    if args.tui and args.remote and os.environ.get("TMUX") is None:
        return handle_tmux(args)

    # Depwire MCP server and docs are handled by scripts/cline.sh,
    # which is the canonical entry point. We avoid duplicating that
    # work here to prevent resource contention (two MCP servers).

    # Launch Cline via the wrapper script
    cline_script = Path(__file__).resolve().parents[2] / "scripts" / "cline.sh"
    command = [str(cline_script)]
    if args.tui:
        command.extend(["--tui", "--auto-condense"])

    # Note: --remote and --split are handled by handle_tmux if applicable,
    # but we pass them to cline.sh just in case it needs them.
    if args.remote:
        command.append("--remote")
    if args.split:
        command.append("--split")

    cmd_tuple = tuple(command)
    if args.print_command:
        print(" ".join(cmd_tuple))
        return 0

    completed_cline = subprocess.run(cmd_tuple, check=False)
    return completed_cline.returncode


def handle_tmux(args: argparse.Namespace) -> int:
    session = f"agent-{Path.cwd().name}-{_short_hostname()}"

    # Base command to run inside tmux
    inner_cmd = "winkr start"
    if args.tui:
        inner_cmd += " --tui"
    # We don't pass --remote to the inner command to avoid recursion
    if args.split:
        inner_cmd += " --split"

    commands = [
        ("tmux", "has-session", "-t", session),
        ("tmux", "new-session", "-d", "-s", session),
        ("tmux", "rename-window", "-t", session, "main"),
    ]

    # Add commands for the first pane
    commands.append(("tmux", "send-keys", "-t", f"{session}:0.0", inner_cmd, "C-m"))

    if args.split:
        # Add split window command
        commands.append(("tmux", "split-window", "-v", "-t", session))
        # Add command for the second pane
        commands.append(("tmux", "send-keys", "-t", f"{session}:0.1", _shell(), "C-m"))
        # Select the first pane
        commands.append(("tmux", "select-pane", "-t", f"{session}:0.0"))

    # The attach command is always last.
    commands.append(("tmux", "attach", "-t", session))

    if args.print_command:
        for command in commands:
            print(" ".join(command))
        return 0

    has_session = subprocess.run(
        commands[0],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if has_session.returncode == 0:
        return subprocess.run(("tmux", "attach", "-t", session), check=False).returncode

    for command in commands[1:]:
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def handle_enforcer_check(args: argparse.Namespace) -> int:
    """Handle ``winkr enforcer check``."""
    if args.range:
        results = check_commits(commit_range=args.range)
        for r in results:
            status = "PASS" if r.passed else "WARN"
            print(f"[{status}] {r.reason}")
        return 0 if all(r.passed for r in results) else 1

    result = check_pending_changes()
    if result.passed:
        print(f"[PASS] {result.reason}")
        return 0
    print(f"[WARN] {result.reason}")
    return 1


def handle_enforcer_block(args: argparse.Namespace) -> int:
    """Handle ``winkr enforcer block`` — hard pre-mutation gate."""
    result = check_worktree_block()
    if result.passed:
        print(f"[PASS] {result.reason}")
        return 0
    print(f"[BLOCK] {result.reason}", file=sys.stderr)
    return 1


def handle_enforcer_install_hooks(args: argparse.Namespace) -> int:
    """Handle ``winkr enforcer install-hooks``."""
    hook_script = (
        Path(__file__).resolve().parents[2] / "scripts" / "install_hooks.sh"
    )
    if not hook_script.exists():
        print(f"Error: hook installer not found at {hook_script}", file=sys.stderr)
        return 1
    completed = subprocess.run([str(hook_script)], check=False)
    return completed.returncode


def handle_tiers(args: argparse.Namespace) -> int:
    for name, model in MODEL_TIERS.items():
        print(f"{name}={model}")
    return 0


def _short_hostname() -> str:
    return os.uname().nodename.split(".", 1)[0]


def _shell() -> str:
    return os.environ.get("SHELL", "bash")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())