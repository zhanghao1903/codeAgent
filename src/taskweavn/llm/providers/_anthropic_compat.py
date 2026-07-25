"""Pure Anthropic Messages API compatibility helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from taskweavn.llm.contracts import ChatResponse, LLMUsage, ToolCall


class AnthropicCompatError(ValueError):
    """Raised when the unified loop contract cannot map to Anthropic."""


class AnthropicUnsupportedContentError(AnthropicCompatError):
    """Raised for content types outside the text-only MVP."""


def to_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert OpenAI-shaped loop history into Anthropic messages."""

    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []

    for message in messages:
        role = str(message.get("role", "")).strip().lower()
        if role in {"system", "developer"}:
            text = _content_text(message.get("content"))
            if text:
                system_parts.append(text)
            continue
        if role == "tool":
            tool_call_id = str(message.get("tool_call_id", "")).strip()
            if not tool_call_id:
                raise AnthropicCompatError("tool result message requires tool_call_id")
            _append_message(
                converted,
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": _content_text(message.get("content")),
                    }
                ],
            )
            continue
        if role not in {"user", "assistant"}:
            raise AnthropicCompatError(f"unsupported Claude message role: {role!r}")

        blocks: list[dict[str, Any]] = []
        text = _content_text(message.get("content"))
        if text:
            blocks.append({"type": "text", "text": text})
        if role == "assistant":
            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls is not None and not isinstance(raw_tool_calls, list):
                raise AnthropicCompatError("assistant tool_calls must be a list")
            for tool_call in raw_tool_calls or ():
                blocks.append(_to_anthropic_tool_use(tool_call))
        if not blocks:
            raise AnthropicCompatError(f"Claude {role} message must not be empty")
        _append_message(converted, role, blocks)

    return "\n\n".join(system_parts) or None, converted


def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI function-tool schemas into Anthropic tool schemas."""

    return [_to_anthropic_tool(tool) for tool in tools]


def parse_anthropic_response(response: Any) -> ChatResponse:
    """Normalize one Anthropic response into the shared chat contract."""

    content_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    raw_content = _field(response, "content")
    if raw_content is None:
        raw_content = ()
    try:
        blocks = tuple(raw_content)
    except TypeError as exc:
        raise AnthropicCompatError("Claude response content must be iterable") from exc

    for block in blocks:
        block_type = _field(block, "type")
        if block_type == "text":
            text = _field(block, "text")
            if not isinstance(text, str):
                raise AnthropicCompatError("Claude text response block requires text")
            content_parts.append(text)
            continue
        if block_type == "tool_use":
            tool_call_id = _required_str(_field(block, "id"), "tool_use id")
            name = _required_str(_field(block, "name"), "tool_use name")
            arguments = _field(block, "input")
            if not isinstance(arguments, Mapping):
                raise AnthropicCompatError("Claude tool_use input must be an object")
            tool_calls.append(
                ToolCall(
                    id=tool_call_id,
                    name=name,
                    arguments=json.dumps(
                        dict(arguments),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
            )
            continue
        raise AnthropicUnsupportedContentError(
            f"unsupported Claude response block type: {block_type!r}"
        )

    if not blocks:
        raise AnthropicCompatError("Claude response content must not be empty")

    content = "".join(content_parts)
    raw_assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if tool_calls:
        raw_assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                },
            }
            for tool_call in tool_calls
        ]

    raw_usage = _field(response, "usage")
    usage = _parse_usage(raw_usage)
    metadata: dict[str, Any] = {}
    for name in ("model", "stop_reason", "stop_sequence"):
        value = _field(response, name)
        if isinstance(value, str | int | float | bool):
            metadata[name] = value
    cache_creation_tokens = _optional_int(
        _field(raw_usage, "cache_creation_input_tokens")
    )
    provider_input_tokens = _optional_int(_field(raw_usage, "input_tokens"))
    if provider_input_tokens is not None:
        metadata["provider_input_tokens"] = provider_input_tokens
    if cache_creation_tokens is not None:
        metadata["cache_creation_input_tokens"] = cache_creation_tokens

    return ChatResponse(
        content=content,
        tool_calls=tool_calls,
        raw_assistant_message=raw_assistant_message,
        provider_name="claude",
        provider_request_id=_optional_str(_field(response, "id")),
        usage=usage,
        raw_response_metadata=metadata,
    )


def _append_message(
    messages: list[dict[str, Any]],
    role: str,
    blocks: list[dict[str, Any]],
) -> None:
    if messages and messages[-1]["role"] == role:
        messages[-1]["content"].extend(blocks)
        return
    messages.append({"role": role, "content": blocks})


def _to_anthropic_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function")
    if tool.get("type") != "function" or not isinstance(function, Mapping):
        raise AnthropicCompatError(
            "Claude tools must use the OpenAI function-tool shape"
        )
    name = _required_str(function.get("name"), "function tool name")
    parameters = function.get("parameters", {"type": "object", "properties": {}})
    if not isinstance(parameters, Mapping):
        raise AnthropicCompatError(
            f"Claude function tool {name!r} requires an object schema"
        )
    result: dict[str, Any] = {
        "name": name,
        "input_schema": dict(parameters),
    }
    description = function.get("description")
    if isinstance(description, str) and description:
        result["description"] = description
    return result


def _to_anthropic_tool_use(tool_call: Any) -> dict[str, Any]:
    if not isinstance(tool_call, Mapping):
        raise AnthropicCompatError("Claude assistant tool calls must be objects")
    function = tool_call.get("function")
    if not isinstance(function, Mapping):
        raise AnthropicCompatError(
            "Claude assistant tool call requires function details"
        )
    tool_call_id = _required_str(tool_call.get("id"), "assistant tool call id")
    name = _required_str(function.get("name"), "assistant tool call function name")
    arguments = function.get("arguments", "{}")
    try:
        parsed_arguments = (
            json.loads(arguments) if isinstance(arguments, str) else arguments
        )
    except json.JSONDecodeError as exc:
        raise AnthropicCompatError(
            "Claude assistant tool call arguments must be valid JSON"
        ) from exc
    if not isinstance(parsed_arguments, Mapping):
        raise AnthropicCompatError(
            "Claude assistant tool call arguments must decode to an object"
        )
    return {
        "type": "tool_use",
        "id": tool_call_id,
        "name": name,
        "input": dict(parsed_arguments),
    }


def _parse_usage(raw: Any) -> LLMUsage | None:
    if raw is None:
        return None
    provider_input_tokens = _optional_int(_field(raw, "input_tokens"))
    output_tokens = _optional_int(_field(raw, "output_tokens"))
    cache_read_tokens = _optional_int(_field(raw, "cache_read_input_tokens"))
    cache_creation_tokens = _optional_int(
        _field(raw, "cache_creation_input_tokens")
    )
    input_tokens = (
        provider_input_tokens
        + (cache_read_tokens or 0)
        + (cache_creation_tokens or 0)
        if provider_input_tokens is not None
        else None
    )
    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    cache_hit_ratio = (
        cache_read_tokens / input_tokens
        if cache_read_tokens is not None
        and input_tokens is not None
        and input_tokens > 0
        else None
    )
    usage = LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cache_read_tokens,
        cache_hit_tokens=cache_read_tokens,
        cache_hit_ratio=cache_hit_ratio,
    )
    if all(value is None for value in usage.model_dump().values()):
        return None
    return usage


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise AnthropicUnsupportedContentError(
            f"unsupported Claude message content: {type(content).__name__}"
        )

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if isinstance(item, Mapping) and item.get("type") == "text":
            text = item.get("text")
            if not isinstance(text, str):
                raise AnthropicCompatError("Claude text content block requires text")
            parts.append(text)
            continue
        block_type = item.get("type") if isinstance(item, Mapping) else type(item).__name__
        raise AnthropicUnsupportedContentError(
            f"unsupported Claude message content block: {block_type!r}"
        )
    return "".join(parts)


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _required_str(value: Any, field_name: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise AnthropicCompatError(f"Claude {field_name} must not be empty")


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "AnthropicCompatError",
    "AnthropicUnsupportedContentError",
    "parse_anthropic_response",
    "to_anthropic_messages",
    "to_anthropic_tools",
]
