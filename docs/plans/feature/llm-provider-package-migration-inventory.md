# Standalone LLM Provider Package Migration Inventory

> Status: S7 cutover verified; S8 independent review pending
>
> Captured At: 2026-08-12
>
> Taskweavn Branch: `codex/llm-provider-package`
>
> Requirements: [Standalone LLM Provider Package Requirements](llm-provider-package-requirements.md)
>
> Technical Design: [Standalone LLM Provider Package Technical Design](llm-provider-package-technical-design.md)
>
> Implementation Plan: [Standalone LLM Provider Package Implementation Plan](llm-provider-package-implementation-plan.md)

## 1. Purpose

This inventory is the executable migration manifest between the confirmed
Taskweavn implementation and the future external package. It prevents a broad
directory copy from being mistaken for a valid extraction and gives the final
duplicate-source audit an explicit expected result.

It records current facts only. The public import namespace is confirmed as
`llm_provider_adapter`.

## 2. Verified Baseline

The confirmed AC-008 baseline is exactly these nine Taskweavn test files:

```text
tests/test_llm.py
tests/test_llm_contracts.py
tests/test_llm_providers.py
tests/test_llm_retry_policy.py
tests/test_llm_claude_provider.py
tests/test_agent_llm_config.py
tests/test_agent_llm_resolver.py
tests/test_settings_config.py
tests/test_settings_readiness.py
```

Collection command:

```bash
uv run pytest --collect-only -q \
  tests/test_llm.py \
  tests/test_llm_contracts.py \
  tests/test_llm_providers.py \
  tests/test_llm_retry_policy.py \
  tests/test_llm_claude_provider.py \
  tests/test_agent_llm_config.py \
  tests/test_agent_llm_resolver.py \
  tests/test_settings_config.py \
  tests/test_settings_readiness.py
```

Result: `76 tests collected in 0.56s`.

Execution result for the same file set: `76 passed in 0.52s`.

This is a before-migration baseline, not proof that the external package exists
or that Taskweavn has cut over. After migration, all 76 tests plus new package
boundary tests must pass against the installed registry artifact.

## 3. Module Disposition

| Current Taskweavn module | Disposition | Required final form |
|---|---|---|
| `llm/contracts.py` | split | pure re-exports for chat types; OpenHands-only aliases remain Taskweavn-owned |
| `llm/errors.py` | migrate | pure re-exports from `llm_provider_adapter.errors` |
| `llm/retry.py` | migrate | pure re-export of package base/retry types |
| `llm/provider_catalog.py` | migrate | pure re-exports; no duplicate URL/catalog logic |
| `llm/providers/_openai_compat.py` | migrate/delete | no Taskweavn parser remains |
| `llm/providers/_anthropic_compat.py` | migrate/delete | no Taskweavn conversion/parser remains |
| `llm/providers/openai.py` | migrate | deprecated pure provider re-export only |
| `llm/providers/claude.py` | migrate | deprecated pure provider re-export only |
| `llm/providers/deepseek.py` | migrate | deprecated pure provider re-export only |
| `llm/providers/openrouter.py` | migrate | deprecated pure provider re-export only |
| `llm/providers/litellm.py` | migrate | deprecated pure provider re-export only |
| `llm/providers/__init__.py` | retain facade | re-export external providers only |
| `llm/logging.py` | split | Agent I/O logs stay; provider logs consume safe package events |
| `llm/telemetry.py` | add | package observer to Taskweavn observability adapter |
| `llm/config.py` | retain/adapt | env and product defaults stay; construction delegates externally |
| `llm/client.py` | retain/adapt | chat facade delegates; OpenHands and Action helpers stay |
| `llm/agent_config.py` | retain | Agent profile inheritance remains product-owned |
| `llm/agent_resolver.py` | retain | Settings/secrets/usage runtime assembly remains product-owned |
| `llm/__init__.py` | retain facade | one-minor compatibility exports with no implementation copy |

## 4. Symbol Ownership

### 4.1 External public chat contract

The external package owns the final definitions of:

- `ChatRequest` and `ChatResponse`;
- `ToolCall` and `LLMUsage`;
- `ProviderCapabilities`, `ThinkingConfig`, and `ProviderRoutingConfig`;
- `RetryPolicy`, `RetryRecord`, and `ErrorClassification`;
- synchronous chat-only `LLMProvider`;
- normalized provider error hierarchy;
- `BaseLLMProvider`;
- provider catalog constants, labels, endpoint validation, and credential-key
  hints;
- the five provider classes.

Taskweavn may re-export these exact symbol objects during the compatibility
window. It must not subclass or wrap data models merely to preserve an import
path because that would create divergent validation or type identity.

### 4.2 Taskweavn-only symbols

The following remain implemented in Taskweavn:

- `LLMClient`, `LazyLLMClient`, and `LLMClientConfig`;
- `load_client_config_from_env()` and Taskweavn product defaults;
- OpenHands `LLMResponse`, `Message`, `ToolDefinition`, completion and token
  counting compatibility;
- `tool_schema_from_action()` and `parse_tool_arguments()`;
- `AgentLlmConfig`, `AgentLlmProfileInput`, `ResolvedAgentLlmProfile`,
  `SettingsBackedAgentLlmResolver`, and `AgentConfiguredLLM`;
- Taskweavn Agent input/output logging and usage attribution.

### 4.3 Existing symbols that must change contract

- The external `LLMProvider` drops `complete()` and `count_tokens()`.
- `ChatRequest` adds explicit `tool_choice` and `provider_options`.
- `ChatResponse` adds stable finish reason and model identity.
- normalized provider errors stop retaining `original_error` because raw SDK
  exceptions can contain secret-bearing text or payloads.
- provider logging becomes safe observer events; the package cannot call
  `taskweavn.observability`.

Compatibility tests must prove the retained Taskweavn facade still provides
its broader legacy behavior even though the external provider protocol is
chat-only.

## 5. Test Allocation

### 5.1 Move and expand in the external repository

| Current coverage | External destination |
|---|---|
| provider protocol conformance and chat models | `tests/test_contracts.py` |
| retry validation/classification/exhaustion | `tests/test_retry.py` |
| OpenAI-compatible response parsing | `tests/providers/test_openai_compat.py` |
| Anthropic message/tool conversion and parsing | `tests/providers/test_anthropic_compat.py` |
| OpenAI provider fixtures | `tests/providers/test_openai.py` |
| Claude provider fixtures | `tests/providers/test_claude.py` |
| DeepSeek provider fixtures | `tests/providers/test_deepseek.py` |
| OpenRouter provider fixtures | `tests/providers/test_openrouter.py` |
| LiteLLM provider fixtures | `tests/providers/test_litellm.py` |
| new safe telemetry and secret canaries | `tests/test_telemetry.py`, `tests/test_secret_safety.py` |
| missing extras and lazy imports | `tests/test_factory.py`, isolated install checks |

External tests are ports only where they exercise portable provider behavior.
They must use external public imports and may not import Taskweavn fixtures or
domain models.

### 5.2 Retain and adapt in Taskweavn

- `tests/test_llm.py`: facade, environment projection, OpenHands compatibility,
  Action schema, tool arguments, and chat delegation.
- `tests/test_agent_llm_config.py`: product profile semantics.
- `tests/test_agent_llm_resolver.py`: Settings/secrets/usage assembly.
- `tests/test_settings_config.py`: persistence and write-only secret behavior.
- `tests/test_settings_readiness.py`: product readiness and diagnostics.
- provider/contract/retry tests remain only as compatibility and installed
  package-boundary assertions; portable implementation cases move out.

### 5.3 New Taskweavn boundary tests

`tests/test_llm_package_boundary.py` must prove:

1. package types used by the facade come from the installed external namespace;
2. all five provider constructors resolve to external class definitions;
3. old Taskweavn import paths return the same symbol identities;
4. the dependency source is a registry artifact with a bounded range and exact
   lock entry, never path/editable/Git;
5. Taskweavn provider modules contain no transport, parser, or SDK construction;
6. Taskweavn observer maps safe events without receiving message bodies,
   headers, raw payloads, arbitrary metadata, or raw exception text;
7. OpenHands `complete()` and `count_tokens()` still work independently of the
   external chat protocol.

## 6. Caller Compatibility Surface

Production callers currently import the LLM layer from audit, CLI, core loop,
interaction risk, main-page helpers, read-only inquiry, runtime input routing,
Settings, collaborator execution, and usage recording. The migration should
not rewrite all callers directly to `llm_provider_adapter` during the compatibility
window. They keep importing `taskweavn.llm` so Taskweavn remains the product
assembly boundary.

Only the Taskweavn facade/config/telemetry layer imports the external package
directly. This limits package knowledge in the product repository and makes a
future compatible package upgrade independently testable.

## 7. Dependency Disposition

Current direct Taskweavn dependencies include `openai` and `anthropic`; LiteLLM
is present transitively through OpenHands. After cutover:

- provider SDKs are declared by external provider extras;
- Taskweavn requests the extras required for all five configured providers;
- a provider SDK remains a direct Taskweavn dependency only if a non-LLM
  product path independently imports it, with that exception documented;
- `openhands-sdk` remains because Taskweavn still owns completion/token counting;
- the external core has no OpenHands or Taskweavn dependency.

`uv.lock` must identify the exact public external version and artifact hashes.

## 8. Duplicate-Source Audit

The final Taskweavn review runs source searches for:

```text
from openai import OpenAI
from anthropic import Anthropic
litellm.completion
parse_openai_compatible_response
parse_anthropic_response
to_anthropic_messages
to_anthropic_tools
class OpenAIProvider
class ClaudeProvider
class DeepSeekProvider
class OpenRouterProvider
class LiteLLMProvider
```

Expected final result: no provider transport, conversion, or parser definition
in Taskweavn. Pure re-export imports are allowed and must point to the external
namespace. Any unrelated SDK consumer must be enumerated rather than silently
ignored.

The dependency audit also rejects `path`, `editable`, `git`, local wheel, or
repository-relative sources for `llm-provider-adapter`.

## 9. Migration Evidence

Completed external package evidence:

- public package `llm-provider-adapter==0.1.0`, MIT, Python 3.11+;
- external package PR #1 merged at `c7b40207a1cbe1216f7669eb1a761d3a921f49a2`;
- release-controller PR #2 merged at `19e7526086c8306b5823c17fb4d5e5eba60e800d`;
- GitHub release workflow run `31506383555` completed successfully;
- TestPyPI registry/download/isolated-extra verification passed before public upload;
- public PyPI wheel SHA-256
  `43a0526133087d6d06897cd781a5732e337345b55b11b79a16c3bf5f4531d868`;
- public PyPI sdist SHA-256
  `d84fc296a239417aa46616f385b6eab8ec2e53c1f067453ce2a591a036c1aa63`;
- clean public-index Python 3.12 `[all]` installation constructed all five
  providers and ran the offline fake successfully.

Completed Taskweavn cutover evidence:

- bounded `[all]>=0.1.0,<0.2.0` public registry dependency and exact `uv.lock`;
- direct Taskweavn `openai`/`anthropic` dependencies removed;
- exact external contract/error/retry/provider symbol identity through compatibility exports;
- provider transport/conversion/parser implementation removed from Taskweavn;
- safe package telemetry projected through `TaskweavnTelemetryObserver`;
- recursively immutable package response messages converted through `to_dict()`
  before Taskweavn transcript, checkpoint, and log serialization;
- new `tests/test_llm_package_boundary.py` enforces the dependency, identity,
  source-removal, telemetry, and chat-only protocol boundaries.

Completed Taskweavn verification evidence:

- complete backend suite: `1604 passed, 1 skipped`;
- changed Python scope Ruff: passed;
- changed production/boundary-test strict Mypy: passed;
- `uv lock --check` and `git diff --check`: passed;
- exact duplicate provider source scan: no matches;
- the nine-file pre-migration 76-test baseline remains covered by the complete
  suite, with six additive package boundary tests.

Evidence still required before feature closure:

- Taskweavn PR exact-head independent review and any remediation;
- Taskweavn merge proof and lifecycle post-merge traceability.
