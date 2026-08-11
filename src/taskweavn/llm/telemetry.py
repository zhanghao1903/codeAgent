"""Map safe package telemetry events into Taskweavn structured logs."""

from __future__ import annotations

from typing import Any

from llm_provider_adapter.telemetry import (
    ErrorTelemetryEvent,
    ProviderTelemetryEvent,
    RequestTelemetryEvent,
    ResponseTelemetryEvent,
    RetryTelemetryEvent,
    TelemetryObserver,
)

from taskweavn.observability import LogContext, get_object_logger

_LLM_LOGGER = get_object_logger("llm")


class TaskweavnTelemetryObserver:
    """Project package-owned safe provider events into the product log."""

    def on_event(self, event: ProviderTelemetryEvent) -> None:
        context = LogContext(provider=event.provider_name, model=event.model)
        if isinstance(event, RequestTelemetryEvent):
            _LLM_LOGGER.info(
                "request",
                context=context,
                data={
                    "provider": event.provider_name,
                    "model": event.model,
                    "message_count": event.message_count,
                    "tool_count": event.tool_count,
                    "timeout_seconds": event.timeout_seconds,
                    "thinking_enabled": event.thinking_enabled,
                },
            )
            return
        if isinstance(event, ResponseTelemetryEvent):
            response_context = context.model_copy(
                update={"provider_request_id": event.provider_request_id}
            )
            payload: dict[str, Any] = {
                "provider": event.provider_name,
                "model": event.model,
                "finish_reason": event.finish_reason,
                "content_length": event.content_length,
                "tool_call_count": event.tool_call_count,
                "retry_count": event.retry_count,
            }
            if event.usage is not None:
                payload["usage"] = event.usage.model_dump(mode="json", exclude_none=True)
            _LLM_LOGGER.info("response", context=response_context, data=payload)
            return
        if isinstance(event, RetryTelemetryEvent):
            _LLM_LOGGER.warning(
                "retry",
                context=context,
                data={
                    "provider": event.provider_name,
                    "model": event.model,
                    "attempt": event.attempt,
                    "max_attempts": event.max_attempts,
                    "classification": event.classification.value,
                    "delay_seconds": event.delay_seconds,
                    "error_type": event.error_type,
                    "status_code": event.status_code,
                },
            )
            return
        if isinstance(event, ErrorTelemetryEvent):
            _LLM_LOGGER.error(
                "error",
                context=context,
                data={
                    "provider": event.provider_name,
                    "model": event.model,
                    "classification": event.classification.value,
                    "error_type": event.error_type,
                    "status_code": event.status_code,
                    "retry_count": event.retry_count,
                },
            )


DEFAULT_PROVIDER_TELEMETRY_OBSERVER: TelemetryObserver = TaskweavnTelemetryObserver()

__all__ = ["DEFAULT_PROVIDER_TELEMETRY_OBSERVER", "TaskweavnTelemetryObserver"]
