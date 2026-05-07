"""Simple prompt logging utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def log_prompt(kind: str, prompt: str, command: str, root: Path | None = None) -> Path:
    """Append a prompt record under ``.ai_logs`` and return the log path."""

    base = root if root is not None else Path.cwd()
    log_dir = base / ".ai_logs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = log_dir / f"{stamp}-{kind}.md"
    path.write_text(
        "\n".join(
            [
                f"# {kind} prompt",
                "",
                f"- timestamp: {stamp}",
                "",
                "## Command",
                "",
                "```bash",
                command,
                "```",
                "",
                "## Prompt",
                "",
                prompt,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
