"""Configuration defaults for model tiers."""

from __future__ import annotations

MODEL_TIERS: dict[str, str] = {
    "TIER_REASONING": "deepseek/deepseek-coder", # "openrouter/google/gemini-2.5-flash",
    "TIER_ARCHITECT": "deepseek/deepseek-coder", # "openrouter/google/gemini-2.5-flash",
    "TIER_CODING"   : "deepseek/deepseek-chat",  # "openrouter/deepseek/deepseek-chat",
    "TIER_FAST"     : "deepseek/deepseek-chat",
}

DEFAULT_QUERY_MODEL = "TIER_FAST"
DEFAULT_CHANGE_MODEL = "TIER_CODING"


def resolve_model(model: str) -> str:
    """Resolve a model-tier alias to a concrete provider/model string."""

    return MODEL_TIERS.get(model, model)


def provider_from_model(model: str) -> str | None:
    """Return a known provider prefix for a model string, if present."""

    if model.startswith("openrouter/"):
        return "openrouter"
    if model.startswith("deepseek/"):
        return "deepseek"
    return None
