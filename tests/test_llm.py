"""Tests for LLMClient (1.3) and the chat-with-tools helpers (1.5).

We don't hit a real LLM here; we patch :class:`openhands.sdk.LLM` and
provider transport so the test suite stays offline and key-free.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from taskweavn.llm import (
    ChatResponse,
    LazyLLMClient,
    LLMClient,
    ToolCall,
    parse_tool_arguments,
    tool_schema_from_action,
)
from taskweavn.llm.telemetry import DEFAULT_PROVIDER_TELEMETRY_OBSERVER
from taskweavn.tools.fs import WriteFileAction
from taskweavn.types import AgentFinishAction


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_REQUEST_TIMEOUT_SECONDS",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@patch("taskweavn.llm.client.LLM")
def test_construct_passes_model_and_key(mock_llm_cls: MagicMock) -> None:
    LLMClient(model="anthropic/claude-sonnet-4-5", api_key="sk-test")
    mock_llm_cls.assert_called_once_with(model="anthropic/claude-sonnet-4-5", api_key="sk-test")


@patch("taskweavn.llm.client.LLM")
def test_complete_delegates_to_underlying_llm(mock_llm_cls: MagicMock) -> None:
    fake_llm = MagicMock()
    sentinel: Any = object()
    fake_llm.completion.return_value = sentinel
    mock_llm_cls.return_value = fake_llm

    client = LLMClient(model="anthropic/claude-sonnet-4-5", api_key="sk-test")
    result = client.complete(messages=[], tools=None)

    assert result is sentinel
    fake_llm.completion.assert_called_once_with(messages=[], tools=None)


@patch("taskweavn.llm.client.LLM")
def test_count_tokens_delegates(mock_llm_cls: MagicMock) -> None:
    fake_llm = MagicMock()
    fake_llm.get_token_count.return_value = 42
    mock_llm_cls.return_value = fake_llm

    client = LLMClient(model="anthropic/claude-sonnet-4-5", api_key="sk-test")
    assert client.count_tokens([]) == 42


@patch("taskweavn.llm.client.LLM")
def test_from_env_requires_api_key(
    mock_llm_cls: MagicMock,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLMClient.from_env()


@patch("taskweavn.llm.client.LLM")
def test_from_env_uses_model_override(
    mock_llm_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-haiku-4-5")
    client = LLMClient.from_env()
    mock_llm_cls.assert_called_once_with(model="anthropic/claude-haiku-4-5", api_key="sk-env")
    assert client.request_timeout_seconds == 180.0


@patch("taskweavn.llm.client.LLM")
def test_from_env_uses_explicit_env_mapping(
    mock_llm_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)

    client = LLMClient.from_env(
        env={
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "sk-workspace",
            "LLM_MODEL": "deepseek-chat",
        }
    )

    mock_llm_cls.assert_called_once_with(
        model="deepseek-chat",
        api_key="sk-workspace",
    )
    assert client.model == "deepseek-chat"


@patch("taskweavn.llm.providers.openai.OpenAIProvider")
def test_from_env_builds_openai_provider_with_configured_endpoint(
    mock_provider_cls: MagicMock,
) -> None:
    provider = MagicMock()
    mock_provider_cls.return_value = provider

    client = LLMClient.from_env(
        env={
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-openai",
            "OPENAI_BASE_URL": "https://gateway.example.test/v1",
            "LLM_MODEL": "gpt-test",
        }
    )

    mock_provider_cls.assert_called_once_with(
        api_key="sk-openai",
        base_url="https://gateway.example.test/v1",
        observer=DEFAULT_PROVIDER_TELEMETRY_OBSERVER,
    )
    assert client.model == "gpt-test"


@patch("taskweavn.llm.providers.claude.ClaudeProvider")
def test_from_env_builds_claude_provider_with_configured_endpoint(
    mock_provider_cls: MagicMock,
) -> None:
    provider = MagicMock()
    mock_provider_cls.return_value = provider

    client = LLMClient.from_env(
        env={
            "LLM_PROVIDER": "claude",
            "ANTHROPIC_API_KEY": "sk-ant-claude",
            "ANTHROPIC_BASE_URL": "https://gateway.example.test",
            "LLM_MODEL": "claude-test",
        }
    )

    mock_provider_cls.assert_called_once_with(
        api_key="sk-ant-claude",
        base_url="https://gateway.example.test",
        observer=DEFAULT_PROVIDER_TELEMETRY_OBSERVER,
    )
    assert client.model == "claude-test"


@patch("taskweavn.llm.client.LLM")
def test_lazy_client_uses_env_provider(
    mock_llm_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    fake_llm = MagicMock()
    sentinel: Any = object()
    fake_llm.completion.return_value = sentinel
    mock_llm_cls.return_value = fake_llm

    client = LazyLLMClient(
        env_provider=lambda: {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "sk-workspace",
            "LLM_MODEL": "deepseek-chat",
        }
    )

    assert client.model == "deepseek-chat"
    assert client.complete(messages=[], tools=None) is sentinel
    mock_llm_cls.assert_called_once_with(
        model="deepseek-chat",
        api_key="sk-workspace",
    )


@patch("taskweavn.llm.client.LLM")
def test_from_env_uses_request_timeout_override(
    mock_llm_cls: MagicMock,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "42.5")
    client = LLMClient.from_env()
    assert client.request_timeout_seconds == 42.5


@patch("taskweavn.llm.client.LLM")
def test_from_env_falls_back_to_default(
    mock_llm_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    LLMClient.from_env(default_model="anthropic/some-default")
    mock_llm_cls.assert_called_once_with(model="anthropic/some-default", api_key="sk-env")


# ---------------------------------------------------------------------------
# 1.5: tool schemas + chat()
# ---------------------------------------------------------------------------


def test_tool_schema_strips_event_bookkeeping_fields() -> None:
    schema = tool_schema_from_action(
        name="write_file",
        description="write a file",
        action_type=WriteFileAction,
    )
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "write_file"
    properties = schema["function"]["parameters"]["properties"]
    assert "path" in properties
    assert "content" in properties
    assert "event_id" not in properties
    assert "timestamp" not in properties
    assert "source" not in properties
    required = schema["function"]["parameters"]["required"]
    assert "event_id" not in required
    assert "source" not in required


def test_tool_schema_for_finish_action_has_final_answer() -> None:
    schema = tool_schema_from_action(
        name="agent_finish",
        description="finish",
        action_type=AgentFinishAction,
    )
    assert "final_answer" in schema["function"]["parameters"]["properties"]


def test_parse_tool_arguments_handles_empty() -> None:
    assert parse_tool_arguments("") == {}
    assert parse_tool_arguments("   ") == {}


def test_parse_tool_arguments_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="must decode to an object"):
        parse_tool_arguments("[1, 2, 3]")


@patch("taskweavn.llm.client.LLM")
def test_chat_parses_plain_text_response(
    mock_llm_cls: MagicMock,  # noqa: ARG001
) -> None:
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content="hello",
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": "hello"},
    )
    client = LLMClient(model="anthropic/claude", api_key="sk", provider=provider)
    result = client.chat(messages=[{"role": "user", "content": "hi"}])
    assert isinstance(result, ChatResponse)
    assert result.content == "hello"
    assert result.tool_calls == ()
    assert result.raw_assistant_message == {"role": "assistant", "content": "hello"}
    request = provider.chat.call_args.args[0]
    assert request.messages == ({"role": "user", "content": "hi"},)
    assert request.timeout_seconds == 180.0


@patch("taskweavn.llm.client.LLM")
def test_chat_parses_tool_calls(
    mock_llm_cls: MagicMock,  # noqa: ARG001
) -> None:
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content="",
        tool_calls=[
            ToolCall(
                id="c1",
                name="write_file",
                arguments='{"path":"a","content":"b"}',
            ),
        ],
        raw_assistant_message={"role": "assistant", "tool_calls": [{"id": "c1"}]},
    )
    client = LLMClient(model="anthropic/claude", api_key="sk", provider=provider)
    result = client.chat(messages=[], tools=[{"type": "function"}])

    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.id == "c1"
    assert tc.name == "write_file"
    assert tc.arguments == '{"path":"a","content":"b"}'
    assert "tool_calls" in result.raw_assistant_message
    request = provider.chat.call_args.args[0]
    assert request.tools == ({"type": "function"},)
    assert request.timeout_seconds == 180.0


@patch("taskweavn.llm.client.LLM")
def test_chat_timeout_can_be_overridden_per_call(
    mock_llm_cls: MagicMock,  # noqa: ARG001
) -> None:
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content="hello",
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": "hello"},
    )
    client = LLMClient(model="anthropic/claude", api_key="sk", provider=provider)
    client.chat(messages=[], timeout_seconds=30.0)
    request = provider.chat.call_args.args[0]
    assert request.timeout_seconds == 30.0
