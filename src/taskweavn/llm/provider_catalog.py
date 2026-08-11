"""Taskweavn projection of the external provider catalog.

Labels, credentials, default endpoints, and URL validation are sourced from
``llm_provider_adapter``.  Only product-owned environment-variable projection
and display ordering remain here.
"""

from __future__ import annotations

from llm_provider_adapter.catalog import (
    DEFAULT_CLAUDE_BASE_URL,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_OPENAI_BASE_URL,
    PROVIDER_CATALOG,
    ProviderName,
    provider_entry,
    validate_base_url,
)

LlmProviderName = ProviderName

# Preserve the existing Taskweavn Settings display order. Provider metadata is
# still read from the external catalog rather than duplicated here.
SUPPORTED_LLM_PROVIDERS: tuple[LlmProviderName, ...] = (
    "litellm",
    "deepseek",
    "openrouter",
    "openai",
    "claude",
)

PROVIDER_LABELS: dict[str, str] = {
    provider: provider_entry(provider).label for provider in SUPPORTED_LLM_PROVIDERS
}


def required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    normalized = provider.strip().lower()
    if normalized not in PROVIDER_CATALOG:
        return ("LLM_API_KEY",)
    return provider_entry(normalized).credential_env_vars


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
    if normalized not in PROVIDER_CATALOG or base_url_env_var(normalized) is None:
        return None
    return provider_entry(normalized).default_base_url


def validate_provider_base_url(provider: str, value: str | None) -> str | None:
    """Validate a Taskweavn-configurable endpoint via the package policy."""

    normalized_provider = provider.strip().lower()
    if normalized_provider not in PROVIDER_CATALOG:
        return None
    if base_url_env_var(normalized_provider) is None:
        return None
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(
            f"base URL is required for the {provider_entry(provider).label} provider"
        )
    return validate_base_url(normalized)


__all__ = [
    "DEFAULT_CLAUDE_BASE_URL",
    "DEFAULT_DEEPSEEK_BASE_URL",
    "DEFAULT_OPENAI_BASE_URL",
    "LlmProviderName",
    "PROVIDER_CATALOG",
    "PROVIDER_LABELS",
    "SUPPORTED_LLM_PROVIDERS",
    "base_url_env_var",
    "default_base_url",
    "preferred_api_key_env_var",
    "required_api_key_env_vars",
    "validate_provider_base_url",
]
