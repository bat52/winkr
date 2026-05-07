from __future__ import annotations

from pathlib import Path

import pytest

from llm_agent_toolkit.rules import load_base_rules, write_rules_file


def test_load_base_rules() -> None:
    text = load_base_rules()

    assert "winkr reusable Cline rules" in text
    assert "TIER_FAST" in text


def test_write_rules_refuses_existing_file(tmp_path: Path) -> None:
    target = tmp_path / ".clinerules"
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_rules_file(target)

    write_rules_file(target, force=True)
    assert "winkr reusable Cline rules" in target.read_text(encoding="utf-8")
