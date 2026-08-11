"""Taskweavn compatibility exports for the external chat contract.

Provider-neutral chat types are defined by :mod:`llm_provider_adapter`.
Taskweavn retains only the OpenHands completion/token-counting placeholders
that are product compatibility concerns rather than provider transports.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from llm_provider_adapter.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    LLMProvider,
    LLMUsage,
    ProviderCapabilities,
    ProviderRoutingConfig,
    RetryPolicy,
    RetryRecord,
    ThinkingConfig,
    ToolCall,
)
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover
    from openhands.sdk.llm import LLMResponse, Message
else:
    LLMResponse = Any
    Message = Any


class CompletionRequest(BaseModel):
    """Taskweavn-owned placeholder for legacy OpenHands completion calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: list[Message]
    tools: Sequence[Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenCountRequest(BaseModel):
    """Taskweavn-owned placeholder for OpenHands token counting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: list[Message]


CompletionResponse = LLMResponse

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "CompletionRequest",
    "CompletionResponse",
    "ErrorClassification",
    "LLMProvider",
    "LLMUsage",
    "ProviderCapabilities",
    "ProviderRoutingConfig",
    "RetryPolicy",
    "RetryRecord",
    "ThinkingConfig",
    "TokenCountRequest",
    "ToolCall",
]
