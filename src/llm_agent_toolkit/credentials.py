"""API-key discovery for Aider-backed commands."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedApiKey:
    """An API key tagged with its source/provider."""

    provider: str
    value: str
    source: str

    def for_aider(self) -> str:
        """Return the provider-prefixed value expected by Aider."""

        if self.provider == "explicit":
            return self.value
        return f"{self.provider}={self.value}"


def resolve_api_key(
    explicit: str | None = None,
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> ResolvedApiKey | None:
    """Resolve an API key using the compatibility precedence rules.

    Precedence:

    1. Explicit command-line value.
    2. ``OPENROUTER_API_KEY``.
    3. ``AIDER_API_KEY`` as legacy DeepSeek.
    4. Cline ``~/.cline/data/secrets.json`` ``deepSeekApiKey``.
    """

    env = environ if environ is not None else os.environ
    base_home = home if home is not None else Path.home()

    if explicit:
        provider, value = _split_explicit_key(explicit)
        return ResolvedApiKey(provider=provider, value=value, source="explicit")

    openrouter_key = env.get("OPENROUTER_API_KEY")
    if openrouter_key:
        return ResolvedApiKey(
            provider="openrouter",
            value=openrouter_key,
            source="OPENROUTER_API_KEY",
        )

    aider_key = env.get("AIDER_API_KEY")
    if aider_key:
        return ResolvedApiKey(
            provider="deepseek",
            value=aider_key,
            source="AIDER_API_KEY",
        )

    cline_key = _read_cline_deepseek_key(base_home)
    if cline_key:
        return ResolvedApiKey(
            provider="deepseek",
            value=cline_key,
            source="cline_secrets",
        )

    return None


def _split_explicit_key(value: str) -> tuple[str, str]:
    for separator in ("=", ":"):
        if separator in value:
            provider, key = value.split(separator, 1)
            if provider and key:
                return provider, key
    return "explicit", value


def _read_cline_deepseek_key(home: Path) -> str | None:
    secrets_file = home / ".cline" / "data" / "secrets.json"
    if not secrets_file.exists():
        return None
    data = json.loads(secrets_file.read_text(encoding="utf-8"))
    value = data.get("deepSeekApiKey")
    return str(value) if value else None
