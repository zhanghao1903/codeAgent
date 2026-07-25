"""Shared metadata and validation for configured LLM providers."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

LlmProviderName = Literal["litellm", "deepseek", "openrouter", "openai", "claude"]

SUPPORTED_LLM_PROVIDERS: tuple[LlmProviderName, ...] = (
    "litellm",
    "deepseek",
    "openrouter",
    "openai",
    "claude",
)

PROVIDER_LABELS: dict[str, str] = {
    "litellm": "LiteLLM",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "claude": "Claude",
}

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CLAUDE_BASE_URL = "https://api.anthropic.com"


def required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    normalized = provider.strip().lower()
    if normalized == "deepseek":
        return ("DEEPSEEK_API_KEY", "LLM_API_KEY")
    if normalized == "openrouter":
        return ("OPENROUTER_API_KEY", "LLM_API_KEY")
    if normalized == "openai":
        return ("OPENAI_API_KEY", "LLM_API_KEY")
    if normalized == "claude":
        return ("ANTHROPIC_API_KEY", "LLM_API_KEY")
    return ("LLM_API_KEY",)


def preferred_api_key_env_var(provider: str) -> str:
    return required_api_key_env_vars(provider)[0]


def base_url_env_var(provider: str) -> str | None:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return "OPENAI_BASE_URL"
    if normalized == "claude":
        return "ANTHROPIC_BASE_URL"
    return None


def default_base_url(provider: str) -> str | None:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return DEFAULT_OPENAI_BASE_URL
    if normalized == "claude":
        return DEFAULT_CLAUDE_BASE_URL
    return None


def validate_provider_base_url(provider: str, value: str | None) -> str | None:
    """Return a normalized provider endpoint or raise a user-correctable error."""

    normalized_provider = provider.strip().lower()
    if base_url_env_var(normalized_provider) is None:
        return None
    normalized = (value or "").strip().rstrip("/")
    if not normalized:
        label = PROVIDER_LABELS.get(normalized_provider, normalized_provider)
        raise ValueError(f"base URL is required for the {label} provider")

    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("base URL must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not include a query or fragment")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("base URL contains an invalid port") from exc
    return normalized


__all__ = [
    "DEFAULT_CLAUDE_BASE_URL",
    "DEFAULT_OPENAI_BASE_URL",
    "LlmProviderName",
    "PROVIDER_LABELS",
    "SUPPORTED_LLM_PROVIDERS",
    "base_url_env_var",
    "default_base_url",
    "preferred_api_key_env_var",
    "required_api_key_env_vars",
    "validate_provider_base_url",
]
