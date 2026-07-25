# Settings First-Run API Contract

> Status: accepted
> Last Updated: 2026-07-24
> Plan: [Settings first-run frontend completion](../plans/feature/settings-first-run-frontend-completion.md)
> Baseline: [Settings and first-run readiness](../plans/feature/settings-first-run-readiness.md)

This contract finalizes the Product 1.0 backend slice needed for the Settings
first-run frontend completion path. It is intentionally smaller than the full
centralized runtime configuration plan.

## Scope

The sidecar supports local read/write setup for:

- LLM provider: `deepseek` by default, with `litellm`, `openrouter`, `openai`,
  and `claude` supported;
- LLM model;
- provider Base URL when `provider=openai` or `provider=claude`;
- write-only API key replacement;
- logging profile selection.

Out of scope:

- centralized runtime configuration;
- provider network validation;
- automatic retry policy;
- exposing stored secret values.

## Endpoints

All responses use the existing sidecar JSON envelope.

```text
GET /api/v1/settings/config
PATCH /api/v1/settings/config
POST /api/v1/settings/readiness/recheck
```

`GET /api/v1/settings/config` returns only safe summaries:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.settings_config.v1",
    "llm": {
      "provider": "deepseek",
      "providerSource": "default",
      "model": "deepseek-v4-pro",
      "modelSource": "default",
      "baseUrl": null,
      "baseUrlSource": "default",
      "apiKeyConfigured": false,
      "apiKeySource": "none",
      "apiKeyEnvVar": "DEEPSEEK_API_KEY"
    },
    "logging": {
      "selectedProfile": null,
      "selectedProfileSource": "default",
      "selectedProfileKnown": true,
      "defaultProfile": "normal",
      "profiles": []
    },
    "diagnostics": {
      "bundleExportAvailable": true,
      "httpExportRouteAvailable": true
    }
  },
  "error": null
}
```

`PATCH /api/v1/settings/config` accepts:

```json
{
  "llm": {
    "provider": "claude",
    "baseUrl": "https://api.anthropic.com",
    "model": "configured-claude-model",
    "apiKey": "write-only replacement"
  },
  "logging": {
    "selectedProfile": "normal"
  }
}
```

`baseUrl` is exposed for endpoint-capable providers. It defaults to
`https://api.openai.com/v1` for OpenAI and `https://api.anthropic.com` for
Claude when omitted. It must be an absolute HTTP or HTTPS URL without embedded
credentials, a query, or a fragment. The API key is write-only. It is never
returned, logged, or included in
diagnostic descriptors. If `apiKey` is omitted, existing local or environment
configuration is kept. If `apiKey` is an empty string and an effective key
already exists, the secret is unchanged. If the requested setup would still
have no effective API key, the request returns `bad_request` with Product error
metadata and safe field errors.

Successful `PATCH` returns:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.settings_config_update.v1",
    "config": {},
    "readiness": {}
  },
  "error": null
}
```

`config` is the same safe summary returned by `GET /api/v1/settings/config`.
`readiness` is a freshly recomputed `plato.settings_readiness.v1` payload.

`POST /api/v1/settings/readiness/recheck` returns the same refreshed readiness
payload as `GET /api/v1/settings/readiness`.

## Storage Policy

Product 1.0 stores this local setup under `.plato/settings/`:

- `config.json`: active provider, model, optional provider Base URL, and
  logging profile;
- `secrets.json`: provider-specific API keys under `llmProviders`.

The secret file uses `plato.local_settings_secrets.v2`. Switching provider
retains keys already stored for other providers. Legacy single-provider
`llm` secrets remain readable and migrate on the next LLM key write. The secret
file is treated as local, write-only sidecar state. Reads only expose
booleans, source labels, and env var names. Diagnostic bundle export does not
include the settings files directly, and all diagnostic payload writes still run
through the Product 1.0 redaction profile.

## Errors

Validation failures keep the top-level `ApiError` shape:

```json
{
  "code": "bad_request",
  "message": "settings config update is invalid",
  "retryable": false,
  "details": {
    "productCategory": "input_validation",
    "recoveryActions": ["edit_input", "open_settings"],
    "severity": "action_required",
    "fieldErrors": [
      {
        "path": "llm.provider",
        "message": "unsupported provider",
        "allowedValues": ["litellm", "deepseek", "openrouter", "openai", "claude"]
      }
    ]
  }
}
```

Error details must not contain raw secrets, provider payloads, prompts, logs, or
SQLite payloads.
