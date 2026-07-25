"""Anthropic Messages API provider for Claude models."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    ProviderCapabilities,
    RetryPolicy,
)
from taskweavn.llm.errors import LLMCapabilityError, LLMRequestError
from taskweavn.llm.logging import log_llm_request, log_llm_response
from taskweavn.llm.provider_catalog import (
    DEFAULT_CLAUDE_BASE_URL,
    validate_provider_base_url,
)
from taskweavn.llm.providers._anthropic_compat import (
    AnthropicCompatError,
    AnthropicUnsupportedContentError,
    parse_anthropic_response,
    to_anthropic_messages,
    to_anthropic_tools,
)
from taskweavn.llm.retry import BaseLLMProvider

DEFAULT_CLAUDE_MAX_TOKENS = 4096


class ClaudeProvider(BaseLLMProvider):
    """Official Anthropic SDK transport with OpenAI-shaped loop compatibility."""

    name = "claude"
    capabilities = ProviderCapabilities(
        chat=True,
        tool_calls=True,
    )

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_CLAUDE_BASE_URL,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._api_key = api_key
        self._base_url = validate_provider_base_url("claude", base_url)
        self._client = client
        self._client_factory = client_factory

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        if request.thinking is not None and request.thinking.enabled:
            raise LLMCapabilityError(
                "Claude provider does not support provider-neutral thinking configuration",
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_CAPABILITY,
            )

        try:
            system, messages = to_anthropic_messages(request.messages)
            tools = to_anthropic_tools(request.tools) if request.tools else None
        except AnthropicUnsupportedContentError as exc:
            raise LLMCapabilityError(
                str(exc),
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_CAPABILITY,
            ) from exc
        except AnthropicCompatError as exc:
            raise LLMRequestError(
                str(exc),
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_REQUEST,
            ) from exc

        kwargs: dict[str, Any] = {
            "max_tokens": request.max_tokens or DEFAULT_CLAUDE_MAX_TOKENS,
            "messages": messages,
            "model": request.model,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.timeout_seconds is not None:
            kwargs["timeout"] = request.timeout_seconds

        log_llm_request(
            self.name,
            request,
            extra={"base_url": self._base_url},
        )
        response = self._client_for_call().messages.create(**kwargs)
        try:
            parsed = parse_anthropic_response(response)
        except AnthropicUnsupportedContentError as exc:
            raise LLMCapabilityError(
                str(exc),
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_CAPABILITY,
            ) from exc
        except AnthropicCompatError as exc:
            raise LLMRequestError(
                str(exc),
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_REQUEST,
            ) from exc
        log_llm_response(parsed, request=request, provider=self.name)
        return parsed

    def classify_error(self, exc: BaseException) -> ErrorClassification:
        if getattr(exc, "status_code", None) == 529:
            return ErrorClassification.RETRYABLE
        return super().classify_error(exc)

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

        from anthropic import Anthropic

        self._client = Anthropic(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=0,
        )
        return self._client


__all__ = ["ClaudeProvider", "DEFAULT_CLAUDE_MAX_TOKENS"]
