"""OpenAI Chat Completions provider with configurable endpoint support."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ProviderCapabilities,
    RetryPolicy,
)
from taskweavn.llm.logging import log_llm_request, log_llm_response
from taskweavn.llm.provider_catalog import (
    DEFAULT_OPENAI_BASE_URL,
    validate_provider_base_url,
)
from taskweavn.llm.providers._openai_compat import parse_openai_compatible_response
from taskweavn.llm.retry import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI SDK transport for OpenAI and compatible configured endpoints."""

    name = "openai"
    capabilities = ProviderCapabilities(
        chat=True,
        tool_calls=True,
        thinking=True,
        reasoning_content_output=True,
    )

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._api_key = api_key
        self._base_url = validate_provider_base_url("openai", base_url)
        self._client = client
        self._client_factory = client_factory

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        thinking_enabled = bool(request.thinking and request.thinking.enabled)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": [_normalize_message(message) for message in request.messages],
            "tools": request.tools,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.timeout_seconds is not None:
            kwargs["timeout"] = request.timeout_seconds
        if thinking_enabled:
            assert request.thinking is not None
            kwargs["reasoning_effort"] = request.thinking.effort
        elif request.temperature is not None:
            kwargs["temperature"] = request.temperature

        log_llm_request(
            self.name,
            request,
            extra={
                "base_url": self._base_url,
                "thinking_enabled": thinking_enabled,
            },
        )
        response = self._client_for_call().chat.completions.create(**kwargs)
        parsed = parse_openai_compatible_response(response, provider_name=self.name)
        log_llm_response(parsed, request=request, provider=self.name)
        return parsed

    def _client_for_call(self) -> Any:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory(
                api_key=self._api_key,
                base_url=self._base_url,
                max_retries=0,
            )
            return self._client

        from openai import OpenAI

        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=0,
        )
        return self._client


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(message)
    normalized.pop("reasoning_content", None)
    return normalized


__all__ = ["OpenAIProvider"]
