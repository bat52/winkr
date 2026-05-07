from __future__ import annotations

from pathlib import Path

from llm_agent_toolkit.cli import main


def test_query_print_command(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")

    exit_code = main(
        [
            "query",
            "--print-command",
            "--no-log",
            "--model",
            "TIER_FAST",
            "hello",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "aider --api-key openrouter=secret" in output
    assert "--model openrouter/google/gemini-2.5-flash" in output
    assert "--message hello" in output


def test_write_rules(tmp_path: Path) -> None:
    target = tmp_path / ".clinerules"

    exit_code = main(["write-rules", str(target)])

    assert exit_code == 0
    assert target.exists()
    assert "winkr reusable Cline rules" in target.read_text(encoding="utf-8")


def test_cline_start_tui_print_command(capsys) -> None:
    exit_code = main(["cline-start", "--tui", "--print-command"])
    assert exit_code == 0
    output = capsys.readouterr().out.strip()
    assert output.endswith("scripts/cline.sh --tui --auto-condense")


def test_tiers(capsys) -> None:
    assert main(["tiers"]) == 0
    output = capsys.readouterr().out
    assert "TIER_FAST=" in output
