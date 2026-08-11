"""Regression proof for the llm-provider-adapter extraction boundary."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from llm_provider_adapter import (
    ChatRequest as PackageChatRequest,
)
from llm_provider_adapter import (
    ChatResponse as PackageChatResponse,
)
from llm_provider_adapter import (
    ErrorClassification as PackageErrorClassification,
)
from llm_provider_adapter import (
    LLMProvider as PackageLLMProvider,
)
from llm_provider_adapter import (
    LLMUsage as PackageLLMUsage,
)
from llm_provider_adapter import (
    ProviderCapabilities as PackageProviderCapabilities,
)
from llm_provider_adapter import (
    RetryPolicy as PackageRetryPolicy,
)
from llm_provider_adapter import (
    ToolCall as PackageToolCall,
)
from llm_provider_adapter.errors import (
    LLMAuthError as PackageLLMAuthError,
)
from llm_provider_adapter.errors import (
    LLMError as PackageLLMError,
)
from llm_provider_adapter.errors import (
    MissingProviderExtraError as PackageMissingProviderExtraError,
)
from llm_provider_adapter.providers.claude import ClaudeProvider as PackageClaudeProvider
from llm_provider_adapter.providers.deepseek import DeepSeekProvider as PackageDeepSeekProvider
from llm_provider_adapter.providers.litellm import LiteLLMProvider as PackageLiteLLMProvider
from llm_provider_adapter.providers.openai import OpenAIProvider as PackageOpenAIProvider
from llm_provider_adapter.providers.openrouter import (
    OpenRouterProvider as PackageOpenRouterProvider,
)
from llm_provider_adapter.retry import BaseLLMProvider as PackageBaseLLMProvider
from llm_provider_adapter.telemetry import (
    ErrorTelemetryEvent,
    ProviderTelemetryEvent,
    RequestTelemetryEvent,
    ResponseTelemetryEvent,
    RetryTelemetryEvent,
)

from taskweavn.llm.client import LLMClient
from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    LLMProvider,
    LLMUsage,
    ProviderCapabilities,
    RetryPolicy,
    ToolCall,
)
from taskweavn.llm.errors import LLMAuthError, LLMError, MissingProviderExtraError
from taskweavn.llm.providers.claude import ClaudeProvider
from taskweavn.llm.providers.deepseek import DeepSeekProvider
from taskweavn.llm.providers.litellm import LiteLLMProvider
from taskweavn.llm.providers.openai import OpenAIProvider
from taskweavn.llm.providers.openrouter import OpenRouterProvider
from taskweavn.llm.retry import BaseLLMProvider
from taskweavn.llm.telemetry import TaskweavnTelemetryObserver

ROOT = Path(__file__).resolve().parents[1]


def test_taskweavn_contract_and_error_exports_keep_exact_package_identity() -> None:
    assert ChatRequest is PackageChatRequest
    assert ChatResponse is PackageChatResponse
    assert ErrorClassification is PackageErrorClassification
    assert LLMProvider is PackageLLMProvider
    assert LLMUsage is PackageLLMUsage
    assert ProviderCapabilities is PackageProviderCapabilities
    assert RetryPolicy is PackageRetryPolicy
    assert ToolCall is PackageToolCall
    assert LLMError is PackageLLMError
    assert LLMAuthError is PackageLLMAuthError
    assert MissingProviderExtraError is PackageMissingProviderExtraError
    assert BaseLLMProvider is PackageBaseLLMProvider


def test_taskweavn_provider_paths_are_pure_package_reexports() -> None:
    assert ClaudeProvider is PackageClaudeProvider
    assert DeepSeekProvider is PackageDeepSeekProvider
    assert LiteLLMProvider is PackageLiteLLMProvider
    assert OpenAIProvider is PackageOpenAIProvider
    assert OpenRouterProvider is PackageOpenRouterProvider


def test_public_package_dependency_is_bounded_and_locked_to_pypi() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    assert "llm-provider-adapter[all]>=0.1.0,<0.2.0" in dependencies
    assert not any(item.startswith("openai") for item in dependencies)
    assert not any(item.startswith("anthropic") for item in dependencies)

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = next(item for item in lock["package"] if item["name"] == "llm-provider-adapter")
    assert package["version"] == "0.1.0"
    assert package["source"] == {"registry": "https://pypi.org/simple"}
    assert set(package["optional-dependencies"]) == {"all"}
    assert package["sdist"]["hash"] == (
        "sha256:d84fc296a239417aa46616f385b6eab8ec2e53c1f067453ce2a591a036c1aa63"
    )
    assert package["wheels"] == [
        {
            "url": "https://files.pythonhosted.org/packages/22/a4/"
            "426603f9016518690b429c25bedcf20dfb17ca86f2114560813acbb37201/"
            "llm_provider_adapter-0.1.0-py3-none-any.whl",
            "hash": "sha256:43a0526133087d6d06897cd781a5732e337345b55b11b79a16c3bf5f4531d868",
            "size": 29051,
            "upload-time": "2026-08-11T16:10:36.538Z",
        }
    ]
    assert version("llm-provider-adapter") == "0.1.0"


def test_taskweavn_contains_no_duplicate_provider_transport_source() -> None:
    llm_root = ROOT / "src" / "taskweavn" / "llm"
    provider_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (llm_root / "providers").glob("*.py")
    )
    all_sources = "\n".join(path.read_text(encoding="utf-8") for path in llm_root.rglob("*.py"))

    assert "class OpenAIProvider" not in provider_sources
    assert "class ClaudeProvider" not in provider_sources
    assert "class DeepSeekProvider" not in provider_sources
    assert "class OpenRouterProvider" not in provider_sources
    assert "class LiteLLMProvider" not in provider_sources
    assert "from openai import OpenAI" not in all_sources
    assert "from anthropic import Anthropic" not in all_sources
    assert "litellm.completion" not in all_sources
    assert not (llm_root / "providers" / "_openai_compat.py").exists()
    assert not (llm_root / "providers" / "_anthropic_compat.py").exists()


def test_package_protocol_stays_chat_only_while_product_facade_keeps_legacy_methods() -> None:
    protocol_methods = {
        name
        for name, member in PackageLLMProvider.__dict__.items()
        if callable(member) and not name.startswith("_")
    }
    assert protocol_methods == {"chat"}
    assert callable(LLMClient.complete)
    assert callable(LLMClient.count_tokens)


def test_taskweavn_telemetry_projects_only_allowlisted_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr("taskweavn.llm.telemetry._LLM_LOGGER", logger)
    observer = TaskweavnTelemetryObserver()

    events: list[ProviderTelemetryEvent] = [
        RequestTelemetryEvent(
            provider_name="openai",
            model="gpt-test",
            message_count=2,
            tool_count=1,
            timeout_seconds=30.0,
            thinking_enabled=False,
        ),
        RetryTelemetryEvent(
            provider_name="openai",
            model="gpt-test",
            attempt=1,
            max_attempts=2,
            classification=PackageErrorClassification.RATE_LIMIT,
            delay_seconds=0.5,
            error_type="LLMProviderError",
            status_code=429,
        ),
        ResponseTelemetryEvent(
            provider_name="openai",
            model="gpt-test",
            provider_request_id="request-safe-id",
            finish_reason="stop",
            content_length=8,
            tool_call_count=0,
            usage=PackageLLMUsage(input_tokens=3, output_tokens=2, total_tokens=5),
            retry_count=1,
        ),
        ErrorTelemetryEvent(
            provider_name="openai",
            model="gpt-test",
            classification=PackageErrorClassification.FATAL_AUTH,
            error_type="LLMAuthError",
            status_code=401,
            retry_count=0,
        ),
    ]
    for event in events:
        observer.on_event(event)

    calls = logger.method_calls
    assert [call[0] for call in calls] == ["info", "warning", "info", "error"]
    payloads = [call.kwargs["data"] for call in calls]
    assert set(payloads[0]) == {
        "provider",
        "model",
        "message_count",
        "tool_count",
        "timeout_seconds",
        "thinking_enabled",
    }
    assert set(payloads[1]) == {
        "provider",
        "model",
        "attempt",
        "max_attempts",
        "classification",
        "delay_seconds",
        "error_type",
        "status_code",
    }
    assert set(payloads[2]) == {
        "provider",
        "model",
        "finish_reason",
        "content_length",
        "tool_call_count",
        "retry_count",
        "usage",
    }
    assert set(payloads[3]) == {
        "provider",
        "model",
        "classification",
        "error_type",
        "status_code",
        "retry_count",
    }
    serialized_calls = repr(calls).lower()
    for prohibited in ("messages", "headers", "authorization", "api_key", "raw_payload"):
        assert prohibited not in serialized_calls
