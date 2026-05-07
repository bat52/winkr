"""Command-line interface for winkr."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .aider import build_edit_command, build_query_command, run_command, validate_prompt
from .config import MODEL_TIERS
from .credentials import resolve_api_key
from .git_safety import ensure_clean_worktree
from .logging_utils import log_prompt
from .rules import write_rules_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="winkr-agent",
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

    edit = subparsers.add_parser(
        "edit",
        help="Ask Aider to mutate files.",
    )
    add_common_aider_args(edit)
    edit.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow edits when the Git worktree is dirty.",
    )
    edit.add_argument("prompt", help="Instruction to send to Aider.")
    edit.add_argument(
        "files",
        nargs="*",
        help="Optional file paths to pass to Aider.",
    )
    edit.set_defaults(func=handle_edit)

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

    cline_start = subparsers.add_parser(
        "cline-start",
        help="Start Cline using npx.",
    )
    cline_start.add_argument(
        "--tui",
        action="store_true",
        help="Start Cline in TUI mode with --tui --auto-condense.",
    )
    cline_start.add_argument(
        "--print-command",
        action="store_true",
        help="Print the command instead of running it.",
    )
    cline_start.set_defaults(func=handle_cline_start)

    tmux = subparsers.add_parser(
        "tmux",
        help="Start or attach to a two-pane tmux agent session.",
    )
    tmux.add_argument(
        "--print-command",
        action="store_true",
        help="Print tmux commands instead of running them.",
    )
    tmux.set_defaults(func=handle_tmux)

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


def handle_edit(args: argparse.Namespace) -> int:
    validate_prompt(args.prompt)
    if not args.allow_dirty:
        ensure_clean_worktree(Path.cwd())

    api_key = resolve_api_key(args.api_key)
    if api_key is None:
        print("ERROR: no API key found.", file=sys.stderr)
        return 2

    command = build_edit_command(
        prompt=args.prompt,
        api_key=api_key,
        model=args.model,
        files=args.files,
        extra_args=args.extra_aider_arg,
    )

    if not args.no_log:
        log_prompt("edit", args.prompt, command.shell_string())

    if args.print_command:
        print(command.shell_string())
        return 0

    return run_command(command)


def handle_write_rules(args: argparse.Namespace) -> int:
    path = Path(args.path)
    write_rules_file(path, force=args.force)
    print(f"Wrote {path}")
    return 0


def handle_cline_start(args: argparse.Namespace) -> int:
    cline_script = Path(__file__).resolve().parents[2] / "scripts" / "cline.sh"
    command = [str(cline_script)]
    if args.tui:
        command.extend(["--tui", "--auto-condense"])
    cmd_tuple = tuple(command)
    if args.print_command:
        print(" ".join(cmd_tuple))
        return 0
    completed = subprocess.run(cmd_tuple, check=False)
    return completed.returncode


def handle_tmux(args: argparse.Namespace) -> int:
    session = f"agent-{Path.cwd().name}-{_short_hostname()}"
    commands = [
        ("tmux", "has-session", "-t", session),
        ("tmux", "new-session", "-d", "-s", session),
        ("tmux", "rename-window", "-t", session, "main"),
        ("tmux", "split-window", "-v", "-t", session),
        ("tmux", "send-keys", "-t", f"{session}:0.0", "winkr-agent cline-start", "C-m"),
        ("tmux", "send-keys", "-t", f"{session}:0.1", _shell(), "C-m"),
        ("tmux", "select-pane", "-t", f"{session}:0.0"),
        ("tmux", "attach", "-t", session),
    ]

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


def query_main(argv: Sequence[str] | None = None) -> int:
    return main(["query", *(argv if argv is not None else sys.argv[1:])])


def edit_main(argv: Sequence[str] | None = None) -> int:
    return main(["edit", *(argv if argv is not None else sys.argv[1:])])


if __name__ == "__main__":
    raise SystemExit(main())
