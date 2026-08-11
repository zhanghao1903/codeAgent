"""Compatibility exports for safe errors owned by llm-provider-adapter."""

from llm_provider_adapter.errors import (
    LLMAuthError,
    LLMCapabilityError,
    LLMConfigurationError,
    LLMContextLimitError,
    LLMError,
    LLMProviderError,
    LLMRequestError,
    LLMRetryExhaustedError,
    LLMTransportError,
    MissingProviderExtraError,
    UnsupportedCapabilityError,
)

__all__ = [
    "LLMAuthError",
    "LLMCapabilityError",
    "LLMConfigurationError",
    "LLMContextLimitError",
    "LLMError",
    "LLMProviderError",
    "LLMRequestError",
    "LLMRetryExhaustedError",
    "LLMTransportError",
    "MissingProviderExtraError",
    "UnsupportedCapabilityError",
]
