"""Configuration management for winkr projects."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import MODEL_TIERS

CONFIG_DIR_NAME = ".winkr"
CONFIG_FILE_NAME = "config.json"


@dataclass(frozen=True)
class WinkrConfig:
    orchestrator_command_name: str
    orchestrator_start_commands: tuple[str, ...]
    tier_reasoning: str
    tier_coding: str
    tier_fast: str


def config_path(cwd: Path | None = None) -> Path:
    if cwd is None:
        cwd = Path.cwd()
    return cwd / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def load_config(cwd: Path | None = None) -> WinkrConfig | None:
    path = config_path(cwd)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    return _deserialize(data)


def save_config(config: WinkrConfig, cwd: Path | None = None) -> Path:
    path = config_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(config))
    return path


def interactive_configure(cwd: Path | None = None) -> WinkrConfig:
    print("Configuring winkr for this project...", file=sys.stderr)

    cmd = _prompt("Orchestrator command name", default="cline")
    start_cmd = _prompt(
        "Orchestrator start command",
        default=f"npx {cmd} --tui --auto-condense",
    )

    def _resolve_tier_default(tier_name: str) -> str:
        env_val = os.environ.get(tier_name)
        if env_val:
            return env_val
        return MODEL_TIERS.get(tier_name, "")

    tier_reasoning = _prompt(
        "TIER_REASONING model",
        default=_resolve_tier_default("TIER_REASONING"),
    )
    tier_coding = _prompt(
        "TIER_CODING model",
        default=_resolve_tier_default("TIER_CODING"),
    )
    tier_fast = _prompt(
        "TIER_FAST model",
        default=_resolve_tier_default("TIER_FAST"),
    )

    config = WinkrConfig(
        orchestrator_command_name=cmd,
        orchestrator_start_commands=(start_cmd,),
        tier_reasoning=tier_reasoning,
        tier_coding=tier_coding,
        tier_fast=tier_fast,
    )

    saved_path = save_config(config, cwd)

    print(f"Configuration saved to {saved_path}", file=sys.stderr)
    print(f"  Orchestrator: {cmd} ({start_cmd})", file=sys.stderr)
    print(f"  TIER_REASONING: {tier_reasoning}", file=sys.stderr)
    print(f"  TIER_CODING: {tier_coding}", file=sys.stderr)
    print(f"  TIER_FAST: {tier_fast}", file=sys.stderr)

    return config


def _serialize(config: WinkrConfig) -> str:
    data: dict[str, Any] = {
        "orchestrator": {
            "command_name": config.orchestrator_command_name,
            "start_commands": list(config.orchestrator_start_commands),
        },
        "tiers": {
            "TIER_REASONING": config.tier_reasoning,
            "TIER_CODING": config.tier_coding,
            "TIER_FAST": config.tier_fast,
        },
    }
    return json.dumps(data, indent=2) + "\n"


def _deserialize(data: dict) -> WinkrConfig:
    try:
        orch = data["orchestrator"]
        tiers = data["tiers"]
        return WinkrConfig(
            orchestrator_command_name=orch["command_name"],
            orchestrator_start_commands=tuple(orch["start_commands"]),
            tier_reasoning=tiers["TIER_REASONING"],
            tier_coding=tiers["TIER_CODING"],
            tier_fast=tiers["TIER_FAST"],
        )
    except (KeyError, TypeError) as e:
        raise ValueError(f"Missing or invalid key in config: {e}") from e


def _prompt(label: str, default: str = "") -> str:
    if default:
        prompt_text = f"{label} [{default}]: "
    else:
        prompt_text = f"{label}: "
    value = input(prompt_text).strip()
    if not value:
        return default
    return value
