"""LLM-specific Settings models, storage helpers, and projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import Field

from taskweavn.llm.provider_catalog import (
    PROVIDER_LABELS,
    SUPPORTED_LLM_PROVIDERS,
    LlmProviderName,
    base_url_env_var,
    default_base_url,
    preferred_api_key_env_var,
    required_api_key_env_vars,
    validate_provider_base_url,
)
from taskweavn.server.ui_contract.base import UiContractModel

SettingsProvider = LlmProviderName
SettingsConfigSource = Literal["default", "env", "stored"]
SettingsApiKeySource = Literal["none", "env", "stored"]

SUPPORTED_SETTINGS_PROVIDERS = SUPPORTED_LLM_PROVIDERS
SETTINGS_SECRETS_SCHEMA_VERSION = "plato.local_settings_secrets.v2"


class SettingsConfigProviderOption(UiContractModel):
    id: SettingsProvider
    label: str
    required_api_key_env_vars: tuple[str, ...]
    preferred_api_key_env_var: str
    base_url_env_var: str | None = None
    default_base_url: str | None = None


class SettingsConfigLlm(UiContractModel):
    provider: str
    provider_source: SettingsConfigSource
    provider_options: tuple[SettingsConfigProviderOption, ...]
    model: str
    model_source: SettingsConfigSource
    base_url: str | None = None
    base_url_source: SettingsConfigSource
    api_key_configured: bool
    api_key_source: SettingsApiKeySource
    api_key_env_var: str


class UpdateSettingsConfigLlmPayload(UiContractModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None


class LlmSettingsSecretReader(Protocol):
    def read_llm_provider_secret(self, provider: str) -> str | None: ...


@dataclass(frozen=True)
class LlmSettingsFieldIssue:
    path: str
    message: str
    allowed_values: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()


def build_llm_summary(
    config: Mapping[str, Any],
    effective_env: Mapping[str, str],
    *,
    base_env: Mapping[str, str],
    store: LlmSettingsSecretReader,
    default_model: str,
    default_provider: str,
) -> SettingsConfigLlm:
    """Build the safe effective LLM Settings summary."""

    stored_llm = config.get("llm")
    provider_source: SettingsConfigSource = "default"
    model_source: SettingsConfigSource = "default"
    if isinstance(stored_llm, Mapping) and isinstance(stored_llm.get("provider"), str):
        provider_source = "stored"
    elif "LLM_PROVIDER" in base_env:
        provider_source = "env"
    if isinstance(stored_llm, Mapping) and isinstance(stored_llm.get("model"), str):
        model_source = "stored"
    elif "LLM_MODEL" in base_env:
        model_source = "env"

    provider = effective_env.get("LLM_PROVIDER", default_provider).strip().lower() or "unknown"
    model = effective_env.get("LLM_MODEL", default_model).strip() or default_model
    base_url, base_url_source = llm_base_url(
        provider,
        stored_llm=stored_llm,
        base_env=base_env,
    )
    api_key_source, api_key_env_var = llm_api_key_source(
        provider,
        base_env=base_env,
        store=store,
    )

    return SettingsConfigLlm(
        provider=provider,
        provider_source=provider_source,
        provider_options=llm_provider_options(),
        model=model,
        model_source=model_source,
        base_url=base_url,
        base_url_source=base_url_source,
        api_key_configured=api_key_source != "none",
        api_key_source=api_key_source,
        api_key_env_var=api_key_env_var,
    )


def llm_config_update(payload: UpdateSettingsConfigLlmPayload) -> dict[str, Any]:
    """Build the storage-safe active LLM config object."""

    provider = payload.provider.strip().lower()
    result: dict[str, Any] = {
        "provider": provider,
        "model": payload.model.strip(),
    }
    if base_url_env_var(provider) is not None:
        configured_base_url = (
            payload.base_url if payload.base_url is not None else default_base_url(provider)
        )
        result["baseUrl"] = (
            configured_base_url.strip().rstrip("/")
            if isinstance(configured_base_url, str)
            else ""
        )
    return result


def validate_llm_settings(
    *,
    provider: str,
    model: str,
    base_url: object,
    api_key_available: bool,
) -> tuple[LlmSettingsFieldIssue, ...]:
    """Validate provider-neutral LLM Settings values."""

    issues: list[LlmSettingsFieldIssue] = []
    if provider not in SUPPORTED_SETTINGS_PROVIDERS:
        issues.append(
            LlmSettingsFieldIssue(
                path="llm.provider",
                message="unsupported provider",
                allowed_values=SUPPORTED_SETTINGS_PROVIDERS,
            )
        )
    if not model:
        issues.append(
            LlmSettingsFieldIssue(
                path="llm.model",
                message="model must not be empty",
            )
        )
    endpoint_env_var = base_url_env_var(provider)
    if endpoint_env_var is not None:
        try:
            validate_provider_base_url(provider, str(base_url or ""))
        except ValueError as exc:
            issues.append(
                LlmSettingsFieldIssue(
                    path="llm.baseUrl",
                    message=str(exc),
                    env_vars=(endpoint_env_var,),
                )
            )
    if provider in SUPPORTED_SETTINGS_PROVIDERS and not api_key_available:
        issues.append(
            LlmSettingsFieldIssue(
                path="llm.apiKey",
                message="an API key is required for the selected provider",
                env_vars=required_api_key_env_vars(provider),
            )
        )
    return tuple(issues)


def llm_api_key_replacement(
    payload: UpdateSettingsConfigLlmPayload | None,
) -> str | None:
    if payload is None or "api_key" not in payload.model_fields_set:
        return None
    raw = payload.api_key
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def has_effective_llm_api_key(
    provider: str,
    *,
    replacement: str | None,
    base_env: Mapping[str, str],
    store: LlmSettingsSecretReader,
) -> bool:
    if replacement is not None:
        return True
    if store.read_llm_provider_secret(provider) is not None:
        return True
    return any(bool(base_env.get(key, "").strip()) for key in required_api_key_env_vars(provider))


def llm_api_key_source(
    provider: str,
    *,
    base_env: Mapping[str, str],
    store: LlmSettingsSecretReader,
) -> tuple[SettingsApiKeySource, str]:
    preferred_env_var = preferred_api_key_env_var(provider)
    if store.read_llm_provider_secret(provider) is not None:
        return "stored", preferred_env_var
    for key in required_api_key_env_vars(provider):
        if base_env.get(key, "").strip():
            return "env", key
    return "none", preferred_env_var


def project_llm_effective_env(
    *,
    config: Mapping[str, Any],
    base_env: Mapping[str, str],
    store: LlmSettingsSecretReader,
    default_provider: str,
) -> dict[str, str]:
    """Project stored active LLM settings over one base environment."""

    env = dict(base_env)
    llm = config.get("llm")
    if isinstance(llm, Mapping):
        provider = llm.get("provider")
        model = llm.get("model")
        configured_base_url = llm.get("baseUrl")
        if isinstance(provider, str) and provider.strip():
            env["LLM_PROVIDER"] = provider.strip().lower()
        if isinstance(model, str) and model.strip():
            env["LLM_MODEL"] = model.strip()
        endpoint_env_var = (
            base_url_env_var(provider) if isinstance(provider, str) and provider.strip() else None
        )
        if (
            endpoint_env_var is not None
            and isinstance(configured_base_url, str)
            and configured_base_url.strip()
        ):
            env[endpoint_env_var] = configured_base_url.strip()

    provider = env.get("LLM_PROVIDER", default_provider).strip().lower()
    secret = store.read_llm_provider_secret(provider)
    if secret is not None:
        env[preferred_api_key_env_var(provider)] = secret
    return env


def read_legacy_llm_secret(data: Mapping[str, Any]) -> tuple[str, str] | None:
    llm = data.get("llm")
    if not isinstance(llm, Mapping):
        return None
    provider = llm.get("provider")
    api_key = llm.get("apiKey")
    if not isinstance(provider, str) or not isinstance(api_key, str):
        return None
    if not provider.strip() or not api_key.strip():
        return None
    return provider.strip().lower(), api_key


def read_llm_provider_secret(
    data: Mapping[str, Any],
    provider: str,
) -> str | None:
    normalized_provider = provider.strip().lower()
    providers = data.get("llmProviders")
    if isinstance(providers, Mapping):
        provider_secret = providers.get(normalized_provider)
        if isinstance(provider_secret, Mapping):
            api_key = provider_secret.get("apiKey")
            if isinstance(api_key, str) and api_key.strip():
                return api_key
    legacy_secret = read_legacy_llm_secret(data)
    if legacy_secret is not None and legacy_secret[0] == normalized_provider:
        return legacy_secret[1]
    return None


def llm_provider_secret_payload(
    data: Mapping[str, Any],
    *,
    provider: str,
    api_key: str,
    updated_at: datetime,
) -> dict[str, Any]:
    """Migrate legacy LLM secret data and update one provider key."""

    existing = {
        key: value
        for key, value in dict(data).items()
        if key not in {"schemaVersion", "updatedAt", "llm", "llmProviders"}
    }
    raw_providers = data.get("llmProviders")
    providers = dict(raw_providers) if isinstance(raw_providers, Mapping) else {}
    legacy_secret = read_legacy_llm_secret(data)
    if legacy_secret is not None:
        legacy_provider, legacy_api_key = legacy_secret
        providers.setdefault(legacy_provider, {"apiKey": legacy_api_key})
    providers[provider.strip().lower()] = {"apiKey": api_key}
    return {
        "schemaVersion": SETTINGS_SECRETS_SCHEMA_VERSION,
        "updatedAt": _timestamp(updated_at),
        **existing,
        "llmProviders": providers,
    }


def llm_provider_options() -> tuple[SettingsConfigProviderOption, ...]:
    return tuple(
        SettingsConfigProviderOption(
            id=provider,
            label=PROVIDER_LABELS[provider],
            required_api_key_env_vars=required_api_key_env_vars(provider),
            preferred_api_key_env_var=preferred_api_key_env_var(provider),
            base_url_env_var=base_url_env_var(provider),
            default_base_url=default_base_url(provider),
        )
        for provider in SUPPORTED_SETTINGS_PROVIDERS
    )


def llm_base_url(
    provider: str,
    *,
    stored_llm: object,
    base_env: Mapping[str, str],
) -> tuple[str | None, SettingsConfigSource]:
    endpoint_env_var = base_url_env_var(provider)
    if endpoint_env_var is None:
        return None, "default"
    if isinstance(stored_llm, Mapping):
        stored_base_url = stored_llm.get("baseUrl")
        if isinstance(stored_base_url, str) and stored_base_url.strip():
            return stored_base_url.strip(), "stored"
    env_base_url = base_env.get(endpoint_env_var)
    if isinstance(env_base_url, str) and env_base_url.strip():
        return env_base_url.strip(), "env"
    return default_base_url(provider), "default"


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "LlmSettingsFieldIssue",
    "LlmSettingsSecretReader",
    "SETTINGS_SECRETS_SCHEMA_VERSION",
    "SUPPORTED_SETTINGS_PROVIDERS",
    "SettingsApiKeySource",
    "SettingsConfigLlm",
    "SettingsConfigProviderOption",
    "SettingsConfigSource",
    "SettingsProvider",
    "UpdateSettingsConfigLlmPayload",
    "build_llm_summary",
    "has_effective_llm_api_key",
    "llm_api_key_replacement",
    "llm_config_update",
    "llm_provider_secret_payload",
    "project_llm_effective_env",
    "read_legacy_llm_secret",
    "read_llm_provider_secret",
    "validate_llm_settings",
]
