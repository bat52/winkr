from __future__ import annotations

from pathlib import Path

from llm_agent_toolkit.credentials import resolve_api_key


def test_explicit_key_wins() -> None:
    resolved = resolve_api_key(
        "openrouter=explicit",
        environ={"OPENROUTER_API_KEY": "env"},
        home=Path("/tmp/does-not-exist"),
    )

    assert resolved is not None
    assert resolved.provider == "openrouter"
    assert resolved.value == "explicit"
    assert resolved.source == "explicit"
    assert resolved.for_aider() == "openrouter=explicit"


def test_openrouter_env_precedes_aider_env() -> None:
    resolved = resolve_api_key(
        None,
        environ={
            "OPENROUTER_API_KEY": "openrouter-key",
            "AIDER_API_KEY": "aider-key",
        },
        home=Path("/tmp/does-not-exist"),
    )

    assert resolved is not None
    assert resolved.provider == "openrouter"
    assert resolved.value == "openrouter-key"
    assert resolved.source == "OPENROUTER_API_KEY"


def test_aider_env_is_legacy_deepseek() -> None:
    resolved = resolve_api_key(
        None,
        environ={"AIDER_API_KEY": "aider-key"},
        home=Path("/tmp/does-not-exist"),
    )

    assert resolved is not None
    assert resolved.provider == "deepseek"
    assert resolved.value == "aider-key"
    assert resolved.for_aider() == "deepseek=aider-key"


def test_cline_secret_fallback(tmp_path: Path) -> None:
    secrets = tmp_path / ".cline" / "data" / "secrets.json"
    secrets.parent.mkdir(parents=True)
    secrets.write_text('{"deepSeekApiKey": "cline-key"}', encoding="utf-8")

    resolved = resolve_api_key(None, environ={}, home=tmp_path)

    assert resolved is not None
    assert resolved.provider == "deepseek"
    assert resolved.value == "cline-key"
    assert resolved.source == "cline_secrets"


def test_no_key_returns_none(tmp_path: Path) -> None:
    assert resolve_api_key(None, environ={}, home=tmp_path) is None
