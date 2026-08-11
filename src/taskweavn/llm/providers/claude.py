"""Deprecated Taskweavn import path for the external Claude provider."""

from llm_provider_adapter.providers.claude import (
    DEFAULT_CLAUDE_MAX_TOKENS,
    ClaudeProvider,
)

__all__ = ["ClaudeProvider", "DEFAULT_CLAUDE_MAX_TOKENS"]
