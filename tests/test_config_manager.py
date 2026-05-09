"""Tests for the winkr config_manager module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_agent_toolkit.cli import build_parser, handle_winkr_init
from llm_agent_toolkit.config import MODEL_TIERS
from llm_agent_toolkit.config_manager import (
    WinkrConfig,
    _deserialize,
    _serialize,
    config_path,
    interactive_configure,
    load_config,
    save_config,
)


# ---------------------------------------------------------------------------
# config_path
# ---------------------------------------------------------------------------


class TestConfigPath:
    def test_defaults_to_cwd_dot_winkr_config_json(self) -> None:
        with patch.object(Path, "cwd", return_value=Path("/home/test/project")):
            result = config_path()
        assert result == Path("/home/test/project/.winkr/config.json")

    def test_accepts_explicit_cwd(self) -> None:
        result = config_path(Path("/custom/path"))
        assert result == Path("/custom/path/.winkr/config.json")


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_none_when_file_does_not_exist(self, tmp_path: Path) -> None:
        result = load_config(cwd=tmp_path)
        assert result is None

    def test_returns_winkr_config_when_valid_json_exists(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".winkr"
        config_dir.mkdir()
        data = {
            "orchestrator": {
                "command_name": "cline",
                "start_commands": ["npx cline --tui --auto-condense"],
            },
            "tiers": {
                "TIER_REASONING": "openrouter/google/gemini-2.5-flash",
                "TIER_CODING": "openrouter/deepseek/deepseek-chat",
                "TIER_FAST": "openrouter/google/gemini-2.5-flash",
            },
        }
        (config_dir / "config.json").write_text(json.dumps(data))
        result = load_config(cwd=tmp_path)
        assert result is not None
        assert result.orchestrator_command_name == "cline"
        assert result.orchestrator_start_commands == (
            "npx cline --tui --auto-condense",
        )
        assert result.tier_reasoning == "openrouter/google/gemini-2.5-flash"
        assert result.tier_coding == "openrouter/deepseek/deepseek-chat"
        assert result.tier_fast == "openrouter/google/gemini-2.5-flash"

    def test_raises_value_error_on_malformed_json(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".winkr"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{not valid json}")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(cwd=tmp_path)

    def test_raises_value_error_when_missing_keys(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".winkr"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({"orchestrator": {}}))
        with pytest.raises(ValueError, match="Missing or invalid key"):
            load_config(cwd=tmp_path)


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------


class TestSaveConfig:
    def test_creates_dot_winkr_directory(self, tmp_path: Path) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("npx cline --tui",),
            tier_reasoning="r",
            tier_coding="c",
            tier_fast="f",
        )
        saved_path = save_config(config, cwd=tmp_path)
        assert saved_path.parent.exists()
        assert saved_path.parent == tmp_path / ".winkr"

    def test_writes_valid_json_with_expected_keys(self, tmp_path: Path) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("npx cline --tui",),
            tier_reasoning="openrouter/r",
            tier_coding="openrouter/c",
            tier_fast="openrouter/f",
        )
        saved_path = save_config(config, cwd=tmp_path)
        data = json.loads(saved_path.read_text())
        assert data["orchestrator"]["command_name"] == "cline"
        assert data["orchestrator"]["start_commands"] == ["npx cline --tui"]
        assert data["tiers"]["TIER_REASONING"] == "openrouter/r"
        assert data["tiers"]["TIER_CODING"] == "openrouter/c"
        assert data["tiers"]["TIER_FAST"] == "openrouter/f"

    def test_returns_path_to_saved_file(self, tmp_path: Path) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("start",),
            tier_reasoning="r",
            tier_coding="c",
            tier_fast="f",
        )
        saved_path = save_config(config, cwd=tmp_path)
        assert saved_path == tmp_path / ".winkr" / "config.json"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        config1 = WinkrConfig(
            orchestrator_command_name="first",
            orchestrator_start_commands=("cmd1",),
            tier_reasoning="r1",
            tier_coding="c1",
            tier_fast="f1",
        )
        save_config(config1, cwd=tmp_path)
        config2 = WinkrConfig(
            orchestrator_command_name="second",
            orchestrator_start_commands=("cmd2",),
            tier_reasoning="r2",
            tier_coding="c2",
            tier_fast="f2",
        )
        save_config(config2, cwd=tmp_path)
        data = json.loads((tmp_path / ".winkr" / "config.json").read_text())
        assert data["orchestrator"]["command_name"] == "second"
        assert data["tiers"]["TIER_REASONING"] == "r2"


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerializeRoundTrip:
    def test_serialize_produces_parsable_json(self) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("npx cline --tui",),
            tier_reasoning="r",
            tier_coding="c",
            tier_fast="f",
        )
        raw = _serialize(config)
        data = json.loads(raw)
        assert data["orchestrator"]["command_name"] == "cline"

    def test_deserialize_of_parsed_json_returns_identical_config(self) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("npx cline --tui",),
            tier_reasoning="r",
            tier_coding="c",
            tier_fast="f",
        )
        raw = _serialize(config)
        data = json.loads(raw)
        restored = _deserialize(data)
        assert restored == config

    def test_full_round_trip(self, tmp_path: Path) -> None:
        config = WinkrConfig(
            orchestrator_command_name="cline",
            orchestrator_start_commands=("npx cline --tui --auto-condense",),
            tier_reasoning="openrouter/google/gemini-2.5-flash",
            tier_coding="openrouter/deepseek/deepseek-chat",
            tier_fast="openrouter/google/gemini-2.5-flash",
        )
        save_config(config, cwd=tmp_path)
        loaded = load_config(cwd=tmp_path)
        assert loaded == config


# ---------------------------------------------------------------------------
# interactive_configure
# ---------------------------------------------------------------------------


class TestInteractiveConfigure:
    def test_env_var_values_used_as_defaults(self, tmp_path: Path) -> None:
        env = {
            "TIER_REASONING": "env-reasoning",
            "TIER_CODING": "env-coding",
            "TIER_FAST": "env-fast",
        }
        with patch.dict("os.environ", env), patch(
            "builtins.input", side_effect=["", "", "", "", ""]
        ):
            result = interactive_configure(cwd=tmp_path)
        assert result.orchestrator_command_name == "cline"
        assert result.orchestrator_start_commands == (
            "npx cline --tui --auto-condense",
        )
        assert result.tier_reasoning == "env-reasoning"
        assert result.tier_coding == "env-coding"
        assert result.tier_fast == "env-fast"

    def test_model_tiers_used_as_defaults_when_no_env_vars(
        self, tmp_path: Path
    ) -> None:
        env = {"TIER_REASONING": "", "TIER_CODING": "", "TIER_FAST": ""}
        with patch.dict("os.environ", env), patch(
            "builtins.input", side_effect=["", "", "", "", ""]
        ):
            result = interactive_configure(cwd=tmp_path)
        assert result.tier_reasoning == MODEL_TIERS["TIER_REASONING"]
        assert result.tier_coding == MODEL_TIERS["TIER_CODING"]
        assert result.tier_fast == MODEL_TIERS["TIER_FAST"]

    def test_custom_input_values_are_used(self, tmp_path: Path) -> None:
        env = {"TIER_REASONING": "", "TIER_CODING": "", "TIER_FAST": ""}
        with patch.dict("os.environ", env), patch(
            "builtins.input",
            side_effect=["my-cmd", "my-start", "my-r", "my-c", "my-f"],
        ):
            result = interactive_configure(cwd=tmp_path)
        assert result.orchestrator_command_name == "my-cmd"
        assert result.orchestrator_start_commands == ("my-start",)
        assert result.tier_reasoning == "my-r"
        assert result.tier_coding == "my-c"
        assert result.tier_fast == "my-f"

    def test_saves_config_file(self, tmp_path: Path) -> None:
        env = {"TIER_REASONING": "", "TIER_CODING": "", "TIER_FAST": ""}
        with patch.dict("os.environ", env), patch(
            "builtins.input", side_effect=["", "", "", "", ""]
        ):
            interactive_configure(cwd=tmp_path)
        assert (tmp_path / ".winkr" / "config.json").exists()


# ---------------------------------------------------------------------------
# CLI configure subcommand registration
# ---------------------------------------------------------------------------


class TestConfigureViaCli:
    def test_configure_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["configure"])
        assert args.command == "configure"

    def test_handler_is_callable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["configure"])
        assert callable(args.func)


# ---------------------------------------------------------------------------
# handle_winkr_init wrapper
# ---------------------------------------------------------------------------


class TestHandleInitWrapper:
    def test_calls_load_config_and_passes_to_handle_init(self) -> None:
        args = MagicMock()
        mock_config = MagicMock(spec=WinkrConfig)
        with patch(
            "llm_agent_toolkit.cli.load_config", return_value=mock_config
        ) as mock_load, patch(
            "llm_agent_toolkit.cli.handle_init", return_value=0
        ) as mock_handle:
            result = handle_winkr_init(args)
        mock_load.assert_called_once_with()
        mock_handle.assert_called_once_with(args, mock_config)
        assert result == 0

    def test_passes_none_when_no_config(self) -> None:
        args = MagicMock()
        with patch(
            "llm_agent_toolkit.cli.load_config", return_value=None
        ) as mock_load, patch(
            "llm_agent_toolkit.cli.handle_init", return_value=1
        ) as mock_handle:
            result = handle_winkr_init(args)
        mock_load.assert_called_once_with()
        mock_handle.assert_called_once_with(args, None)
        assert result == 1
