"""Claude provider protocol, retry, and usage tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from taskweavn.llm import ChatRequest, RetryPolicy, ThinkingConfig
from taskweavn.llm.contracts import ErrorClassification
from taskweavn.llm.errors import LLMCapabilityError, LLMRequestError
from taskweavn.llm.providers.claude import (
    DEFAULT_CLAUDE_MAX_TOKENS,
    ClaudeProvider,
)


class _FakeClaudeClient:
    def __init__(self, *responses: Any) -> None:
        self.messages = MagicMock()
        self.messages.create = MagicMock(side_effect=responses)


def _response(
    *,
    content: list[Any],
    usage: Any | None = None,
    response_id: str = "msg-1",
) -> Any:
    return SimpleNamespace(
        content=content,
        id=response_id,
        model="claude-test",
        stop_reason="end_turn",
        stop_sequence=None,
        usage=usage,
    )


def test_claude_provider_converts_tool_round_trip_and_usage() -> None:
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=30,
        cache_read_input_tokens=80,
        cache_creation_input_tokens=25,
    )
    client = _FakeClaudeClient(
        _response(content=[SimpleNamespace(type="text", text="done")], usage=usage)
    )
    provider = ClaudeProvider(api_key="sk", client=client)

    result = provider.chat(
        ChatRequest(
            model="claude-test",
            messages=[
                {"role": "system", "content": "system one"},
                {"role": "developer", "content": "system two"},
                {"role": "user", "content": "inspect"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path":"a.txt"}',
                            },
                        },
                        {
                            "id": "call-2",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path":"b.txt"}',
                            },
                        },
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "content": "A"},
                {"role": "tool", "tool_call_id": "call-2", "content": "B"},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "Read one file.",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"],
                        },
                    },
                }
            ],
        )
    )

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["system"] == "system one\n\nsystem two"
    assert kwargs["max_tokens"] == DEFAULT_CLAUDE_MAX_TOKENS
    assert kwargs["tools"][0]["input_schema"]["required"] == ["path"]
    assert kwargs["messages"][1]["content"][0] == {
        "type": "tool_use",
        "id": "call-1",
        "name": "read_file",
        "input": {"path": "a.txt"},
    }
    assert kwargs["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "call-1", "content": "A"},
        {"type": "tool_result", "tool_use_id": "call-2", "content": "B"},
    ]
    assert result.content == "done"
    assert result.provider_name == "claude"
    assert result.provider_request_id == "msg-1"
    assert result.usage is not None
    assert result.usage.input_tokens == 225
    assert result.usage.output_tokens == 30
    assert result.usage.total_tokens == 255
    assert result.usage.cached_tokens == 80
    assert result.usage.cache_hit_tokens == 80
    assert result.usage.cache_miss_tokens is None
    assert result.usage.cache_hit_ratio == pytest.approx(80 / 225)
    assert result.raw_response_metadata["provider_input_tokens"] == 120
    assert result.raw_response_metadata["cache_creation_input_tokens"] == 25


def test_claude_provider_normalizes_tool_use_response() -> None:
    client = _FakeClaudeClient(
        _response(
            content=[
                SimpleNamespace(type="text", text="checking"),
                SimpleNamespace(
                    type="tool_use",
                    id="call-1",
                    name="read_file",
                    input={"path": "README.md"},
                ),
            ]
        )
    )
    provider = ClaudeProvider(api_key="sk", client=client)

    result = provider.chat(
        ChatRequest(
            model="claude-test",
            messages=[{"role": "user", "content": "inspect"}],
        )
    )

    assert result.content == "checking"
    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].arguments == '{"path":"README.md"}'
    assert result.raw_assistant_message["tool_calls"][0]["function"] == {
        "name": "read_file",
        "arguments": '{"path":"README.md"}',
    }


def test_claude_provider_rejects_unsupported_content_before_network() -> None:
    client = _FakeClaudeClient(_response(content=[]))
    provider = ClaudeProvider(api_key="sk", client=client)

    with pytest.raises(LLMCapabilityError) as exc_info:
        provider.chat(
            ChatRequest(
                model="claude-test",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": "data:..."}}
                        ],
                    }
                ],
            )
        )

    assert exc_info.value.classification is ErrorClassification.FATAL_CAPABILITY
    client.messages.create.assert_not_called()


def test_claude_provider_rejects_invalid_tool_arguments_before_network() -> None:
    client = _FakeClaudeClient(_response(content=[]))
    provider = ClaudeProvider(api_key="sk", client=client)

    with pytest.raises(LLMRequestError) as exc_info:
        provider.chat(
            ChatRequest(
                model="claude-test",
                messages=[
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": "{",
                                },
                            }
                        ],
                    }
                ],
            )
        )

    assert exc_info.value.classification is ErrorClassification.FATAL_REQUEST
    client.messages.create.assert_not_called()


def test_claude_provider_rejects_thinking_before_network() -> None:
    client = _FakeClaudeClient(_response(content=[]))
    provider = ClaudeProvider(api_key="sk", client=client)

    with pytest.raises(LLMCapabilityError):
        provider.chat(
            ChatRequest(
                model="claude-test",
                messages=[{"role": "user", "content": "hello"}],
                thinking=ThinkingConfig(enabled=True),
            )
        )

    client.messages.create.assert_not_called()


def test_claude_provider_retries_529_once_under_plato_policy() -> None:
    overloaded = RuntimeError("overloaded")
    overloaded.status_code = 529  # type: ignore[attr-defined]
    client = _FakeClaudeClient(
        overloaded,
        _response(content=[SimpleNamespace(type="text", text="ok")]),
    )
    provider = ClaudeProvider(
        api_key="sk",
        client=client,
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_delay_seconds=0,
            max_delay_seconds=0,
            jitter=False,
        ),
    )

    result = provider.chat(
        ChatRequest(
            model="claude-test",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert result.content == "ok"
    assert result.retry_count == 1
    assert client.messages.create.call_count == 2


def test_claude_client_factory_disables_sdk_retries() -> None:
    response = _response(content=[SimpleNamespace(type="text", text="ok")])
    client = _FakeClaudeClient(response)
    factory = MagicMock(return_value=client)
    provider = ClaudeProvider(
        api_key="sk",
        base_url="https://gateway.example.test",
        client_factory=factory,
    )

    provider.chat(
        ChatRequest(
            model="claude-test",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    factory.assert_called_once_with(
        api_key="sk",
        base_url="https://gateway.example.test",
        max_retries=0,
    )
