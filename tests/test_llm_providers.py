"""Concrete provider behavior tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from taskweavn.llm import (
    ChatRequest,
    ProviderRoutingConfig,
    ThinkingConfig,
)
from taskweavn.llm.errors import LLMCapabilityError
from taskweavn.llm.providers.deepseek import DeepSeekProvider
from taskweavn.llm.providers.litellm import LiteLLMProvider
from taskweavn.llm.providers.openai import OpenAIProvider
from taskweavn.llm.providers.openrouter import OpenRouterProvider


def _fake_response(
    *,
    content: str = "",
    reasoning_content: str | None = None,
    tool_calls: list[dict[str, str]] | None = None,
    usage: Any | None = None,
) -> Any:
    msg = MagicMock()
    msg.content = content
    if reasoning_content is not None:
        msg.reasoning_content = reasoning_content
    else:
        del msg.reasoning_content
    if tool_calls:
        parsed = []
        for tc in tool_calls:
            item = MagicMock()
            item.id = tc["id"]
            item.function.name = tc["name"]
            item.function.arguments = tc["arguments"]
            parsed.append(item)
        msg.tool_calls = parsed
    else:
        msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.id = "req-1"
    if usage is not None:
        response.usage = usage
    else:
        del response.usage
    return response


class _FakeDeepSeekClient:
    def __init__(self, response: Any) -> None:
        self.kwargs: dict[str, Any] | None = None
        self.chat = MagicMock()
        self.chat.completions.create = self._create
        self._response = response

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


def test_openai_provider_uses_configured_endpoint_and_chat_contract() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="ok"))
    factory = MagicMock(return_value=client)
    provider = OpenAIProvider(
        api_key="sk",
        base_url="https://gateway.example.test/v1/",
        client_factory=factory,
    )

    result = provider.chat(
        ChatRequest(
            model="gpt-test",
            messages=[
                {
                    "role": "assistant",
                    "content": "prior",
                    "reasoning_content": "private",
                },
                {"role": "user", "content": "continue"},
            ],
            tools=[{"type": "function"}],
            timeout_seconds=12.0,
        )
    )

    factory.assert_called_once_with(
        api_key="sk",
        base_url="https://gateway.example.test/v1",
        max_retries=0,
    )
    assert client.kwargs is not None
    assert client.kwargs["model"] == "gpt-test"
    assert client.kwargs["timeout"] == 12.0
    assert "reasoning_content" not in client.kwargs["messages"][0]
    assert result.content == "ok"
    assert result.provider_name == "openai"


def test_openai_provider_derives_total_and_parses_standard_cached_tokens() -> None:
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 12,
        "prompt_tokens_details": {"cached_tokens": 75},
    }
    client = _FakeDeepSeekClient(_fake_response(content="ok", usage=usage))
    provider = OpenAIProvider(api_key="sk", client=client)

    result = provider.chat(
        ChatRequest(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert result.usage is not None
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 12
    assert result.usage.total_tokens == 112
    assert result.usage.cached_tokens == 75
    assert result.usage.cache_hit_tokens == 75
    assert result.usage.cache_miss_tokens is None
    assert result.usage.cache_hit_ratio == 0.75


def test_deepseek_thinking_request_and_reasoning_tool_call_preserved() -> None:
    client = _FakeDeepSeekClient(
        _fake_response(
            reasoning_content="internal",
            tool_calls=[{"id": "c1", "name": "read_file", "arguments": "{}"}],
        )
    )
    provider = DeepSeekProvider(api_key="sk", client=client)
    result = provider.chat(
        ChatRequest(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "read"}],
            tools=[{"type": "function"}],
            thinking=ThinkingConfig(enabled=True, effort="high"),
        )
    )

    assert client.kwargs is not None
    assert client.kwargs["reasoning_effort"] == "high"
    assert client.kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert result.reasoning_content == "internal"
    assert result.raw_assistant_message["reasoning_content"] == "internal"
    assert result.raw_assistant_message["tool_calls"][0]["id"] == "c1"


def test_deepseek_usage_parses_prompt_cache_fields() -> None:
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 12
    usage.total_tokens = 112
    usage.prompt_cache_hit_tokens = 75
    usage.prompt_cache_miss_tokens = 25
    usage.completion_tokens_details.reasoning_tokens = 3
    client = _FakeDeepSeekClient(_fake_response(content="ok", usage=usage))
    provider = DeepSeekProvider(api_key="sk", client=client)

    result = provider.chat(
        ChatRequest(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert result.usage is not None
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 12
    assert result.usage.total_tokens == 112
    assert result.usage.reasoning_tokens == 3
    assert result.usage.cached_tokens == 75
    assert result.usage.cache_hit_tokens == 75
    assert result.usage.cache_miss_tokens == 25
    assert result.usage.cache_hit_ratio == 0.75


def test_deepseek_sends_request_timeout() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="ok"))
    provider = DeepSeekProvider(api_key="sk", client=client)

    provider.chat(
        ChatRequest(
            model="deepseek-chat",
            messages=[],
            timeout_seconds=12.0,
        )
    )

    assert client.kwargs is not None
    assert client.kwargs["timeout"] == 12.0


def test_deepseek_reasoner_rejects_tools_before_network_call() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="never"))
    provider = DeepSeekProvider(api_key="sk", client=client)
    with pytest.raises(LLMCapabilityError, match="does not support tool calls"):
        provider.chat(
            ChatRequest(
                model="deepseek-reasoner",
                messages=[],
                tools=[{"type": "function"}],
            )
        )
    assert client.kwargs is None


def test_deepseek_reasoner_strips_reasoning_content_from_input() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="ok", reasoning_content="r"))
    provider = DeepSeekProvider(api_key="sk", client=client)
    provider.chat(
        ChatRequest(
            model="deepseek-reasoner",
            messages=[
                {"role": "assistant", "content": "x", "reasoning_content": "old"},
            ],
        )
    )
    assert client.kwargs is not None
    assert "reasoning_content" not in client.kwargs["messages"][0]


def test_openrouter_provider_routing_is_sent() -> None:
    client = MagicMock()
    client.completion.return_value = _fake_response(content="ok")
    provider = OpenRouterProvider(
        api_key="sk",
        provider_routing=ProviderRoutingConfig(
            only=("deepinfra/turbo",),
            order=("deepinfra/turbo",),
            allow_fallbacks=False,
            require_parameters=True,
        ),
        client=client,
    )
    result = provider.chat(ChatRequest(model="deepseek/deepseek-r1", messages=[]))
    assert result.content == "ok"
    client.completion.assert_called_once_with(
        model="deepseek/deepseek-r1",
        api_key="sk",
        messages=[],
        tools=None,
        num_retries=0,
        extra_body={
            "provider": {
                "allow_fallbacks": False,
                "require_parameters": True,
                "order": ["deepinfra/turbo"],
                "only": ["deepinfra/turbo"],
            }
        },
    )


def test_litellm_sends_request_timeout() -> None:
    client = MagicMock()
    client.completion.return_value = _fake_response(content="ok")
    provider = LiteLLMProvider(api_key="sk", client=client)

    provider.chat(ChatRequest(model="m", messages=[], timeout_seconds=8.0))

    client.completion.assert_called_once_with(
        model="m",
        api_key="sk",
        messages=[],
        tools=None,
        num_retries=0,
        timeout=8.0,
    )


def test_openrouter_sends_request_timeout() -> None:
    client = MagicMock()
    client.completion.return_value = _fake_response(content="ok")
    provider = OpenRouterProvider(api_key="sk", client=client)

    provider.chat(ChatRequest(model="openrouter/model", messages=[], timeout_seconds=9.0))

    client.completion.assert_called_once_with(
        model="openrouter/model",
        api_key="sk",
        messages=[],
        tools=None,
        num_retries=0,
        timeout=9.0,
    )
