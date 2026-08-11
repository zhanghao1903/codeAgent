# Standalone LLM Provider Package Implementation Plan

> Status: S7 Taskweavn cutover verified; S8 independent review pending
>
> Branch: `codex/llm-provider-package`
>
> Last Updated: 2026-08-12
>
> Requirements: [Standalone LLM Provider Package Requirements](llm-provider-package-requirements.md)
>
> Technical Design: [Standalone LLM Provider Package Technical Design](llm-provider-package-technical-design.md)
>
> External Repository: `https://github.com/zhanghao1903/llm-provider-adapter`

## 1. Delivery Strategy

This feature is delivered as two linked repositories with one-way source
ownership:

1. `llm-provider-adapter` creates, tests, reviews, and publishes the external
   distribution.
2. Taskweavn consumes the published artifact, preserves its business adapters,
   and removes duplicate provider implementation.

No source is copied into Taskweavn as an intermediate state. No Taskweavn
dependency points at a path, editable checkout, Git URL, or unpublished wheel.
Every slice has an independent rollback point and must leave the preceding
verified state usable.

The user confirmed `llm-provider-adapter`, `llm_provider_adapter`, MIT, and
`0.1.0` on 2026-08-09. TestPyPI validation and subsequent publication of the
same verified artifacts to public PyPI are explicitly authorized.

## 2. Preconditions and Hard Gates

| Gate | Required before | Evidence |
|---|---|---|
| Confirmed requirements | F2 | accepted handoff `d52e1431b96b3d587b6fa2a8b986dd8c88f2db767a6509a50f5a1e3ac4e34b3d` |
| Technical design | F3 | committed F2 design on the feature branch |
| Distribution/import names | S1 source scaffold | explicit user choice and availability check |
| License | public repository release candidate | explicit user choice and `LICENSE`/metadata match |
| External repository write | S1 | repository identity and maintainer push permission |
| TestPyPI/PyPI publication | S5 | explicit user authorization plus configured publisher/credential |
| Taskweavn cutover | S6 | immutable public artifact, hashes, and clean-environment proof |
| Merge | each repository merge | repository-specific explicit authorization/policy |

The implementation may perform read-only package-name availability checks
after a name is proposed. It must not reserve, upload, publish, merge, tag, or
delete branches by inference.

## 3. Slice Overview

| Slice | Repository | Outcome | Depends on |
|---|---|---|---|
| S0 | Taskweavn planning | Resolve names, license, publication and merge gates | F3 |
| S1 | external package | Initialize buildable repository and CI | S0 names/license |
| S2 | external package | Implement provider-neutral core and safe telemetry | S1 |
| S3 | external package | Implement and prove all five providers | S2 |
| S4 | external package | Complete docs, artifacts, and clean-env release candidate | S3 |
| S5 | external package | Review, TestPyPI proof, and authorized public 0.x release | S4 + publication authorization |
| S6 | Taskweavn | Cut over to bounded registry dependency and thin facade | S5 |
| S7 | both | Full regression, duplicate-source audit, release readiness | S6 |
| S8 | both | PR review, remediation, merges, and post-merge traceability | S7 + merge authorization |

## 4. S0 — Resolve Deferred Release Decisions

### Inputs

- repository name is fixed as `zhanghao1903/llm-provider-adapter`;
- Python floor is fixed at 3.11;
- first release line is public PyPI 0.x;
- five-provider scope and synchronous chat boundary are fixed.

### Confirmed decisions

1. PyPI distribution name: `llm-provider-adapter`.
2. Python import package name: `llm_provider_adapter`.
3. Open-source license: MIT.
4. First version: `0.1.0`, with compatible Taskweavn range
   `>=0.1.0,<0.2.0`.
5. TestPyPI validation and public PyPI publication of the same verified
   artifacts are authorized.
6. Merge authorization remains separate for the external and Taskweavn PRs.

### Exit criteria

- chosen names and license are recorded in this plan and external metadata;
- registry/repository collision checks are captured;
- publication authorization scope is explicit;
- if a choice changes the confirmed product contract, implementation stops and
  returns to Requirements for a revised handoff.

## 5. S1 — Initialize the External Repository

### Files

```text
pyproject.toml
README.md
LICENSE
CHANGELOG.md
.gitignore
.python-version
.github/workflows/ci.yml
.github/workflows/publish.yml
src/llm_provider_adapter/__init__.py
tests/test_import.py
```

### Changes

- create a feature branch in the empty authoritative repository;
- configure a PEP 517 build with `src` layout and Python `>=3.11`;
- declare minimal core dependencies and development groups;
- declare empty provider extras initially, then populate them in S3;
- configure Ruff, strict Mypy, Pytest, build, metadata, and Python-version CI;
- make publication workflow environment-protected and OIDC-capable, without
  publishing on ordinary pushes or PRs;
- expose a provisional version from package metadata only after names are final.

### Tests/checks

```text
uv sync --all-groups
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv build
python -m zipfile -l dist/*.whl
```

### Rollback

Close the unmerged external PR/branch. Taskweavn remains unchanged.

## 6. S2 — Provider-Neutral Core and Safety Boundary

### External files

```text
src/llm_provider_adapter/contracts.py
src/llm_provider_adapter/errors.py
src/llm_provider_adapter/telemetry.py
src/llm_provider_adapter/retry.py
src/llm_provider_adapter/catalog.py
src/llm_provider_adapter/factory.py
tests/test_contracts.py
tests/test_errors.py
tests/test_telemetry.py
tests/test_retry.py
tests/test_catalog.py
tests/test_factory.py
tests/test_secret_safety.py
```

### Behavior changes

- implement synchronous chat-only protocol and frozen strict models;
- add `tool_choice`, `provider_options`, finish reason, model/provider identity,
  request ID, normalized usage, retry records, and stable `None`/empty semantics;
- implement provider capability validation before transport;
- implement normalized errors without retaining unsafe SDK payloads or text;
- implement deterministic bounded retry with injectable clock/random/sleeper;
- implement request/response/retry/error telemetry events and no-op observer;
- contain observer failures;
- implement provider catalog and endpoint validation without environment reads;
- implement missing-extra detection in the explicit factory.

### Tests/checks

- model validation and serialization snapshots;
- tool/thinking/routing/provider-option rejection cases;
- retry matrix for status, auth, context, timeout, unknown, and exhaustion;
- secret canaries in `str`, `repr`, trace-visible attributes, telemetry, and
  captured logs;
- observer exception containment;
- core-only import with provider SDKs absent.

### Rollback

Revert S2 without changing the build scaffold or Taskweavn.

## 7. S3 — Five Provider Adapters

### External files

```text
src/llm_provider_adapter/providers/__init__.py
src/llm_provider_adapter/providers/_openai_compat.py
src/llm_provider_adapter/providers/_anthropic_compat.py
src/llm_provider_adapter/providers/openai.py
src/llm_provider_adapter/providers/claude.py
src/llm_provider_adapter/providers/deepseek.py
src/llm_provider_adapter/providers/openrouter.py
src/llm_provider_adapter/providers/litellm.py
tests/providers/test_openai.py
tests/providers/test_claude.py
tests/providers/test_deepseek.py
tests/providers/test_openrouter.py
tests/providers/test_litellm.py
tests/providers/test_openai_compat.py
tests/providers/test_anthropic_compat.py
tests/fixtures/providers/*
```

### Behavior changes

- port behavior from the confirmed Taskweavn snapshot, changing imports and
  telemetry calls but not silently redesigning provider semantics;
- disable SDK retries in every adapter or prove the SDK path does not retry;
- use injected fake clients in unit tests and prohibit real network access;
- normalize finish reason, provider/model identity, request ID, usage/cache and
  reasoning fields required by the new contract;
- reject unsupported parameters/capabilities before the SDK call;
- populate extras for `openai`, `claude`, `deepseek`, `openrouter`, `litellm`,
  and `all`;
- verify importing the core and unrelated providers does not import optional
  SDKs eagerly.

### Provider proof matrix

| Case | OpenAI | Claude | DeepSeek | OpenRouter | LiteLLM |
|---|---:|---:|---:|---:|---:|
| text response | yes | yes | yes | yes | yes |
| tool request/response | yes | yes | yes | yes | yes |
| usage/cache parsing | yes | yes | yes | yes | yes |
| reasoning output | yes | explicit current capability | yes | fixture-driven | fixture-driven |
| unsupported capability | yes | yes | yes | yes | yes |
| request/model/provider ID | yes | yes | yes | yes | yes |
| SDK retry disabled | yes | yes | yes | yes | yes |
| safe failure | yes | yes | yes | yes | yes |

### Rollback

Revert a provider commit independently while keeping core and already-proven
providers. S4 cannot start until all five are present.

## 8. S4 — Documentation, Build, and Clean-Environment Candidate

### External files

```text
README.md
CHANGELOG.md
docs/provider-support.md
docs/configuration.md
docs/security.md
docs/compatibility.md
docs/migration.md
examples/fake_chat.py
examples/tool_call.py
scripts/verify_dist.py
tests/test_readme_examples.py
```

### Required documentation

- installation for core and every provider extra;
- synchronous chat and tool-call examples;
- provider support/capability matrix;
- explicit configuration and endpoint validation;
- safe error and telemetry usage;
- timeout, retry, no-fallback, and possible-upstream-billing semantics;
- compatibility policy for 0.x;
- migration guide from `taskweavn.llm`;
- security boundary and non-goals.

### Artifact checks

Build wheel and sdist from the exact candidate commit. In fresh Python 3.11+
environments, prove:

1. core install/import with no provider SDK;
2. each provider extra install and construction;
3. `all` extra install;
4. wheel and sdist contain only intended source/docs/licenses;
5. offline fake chat and README examples pass;
6. package metadata, version, license, URLs, and Python classifiers agree;
7. no Taskweavn/OpenHands/UI/database import or dependency exists.

Record artifact SHA-256 hashes. Do not commit `dist/`, virtualenvs, caches, or
credentials.

### Rollback

Do not publish. Fix the candidate and rebuild from a new commit.

## 9. S5 — External Review and Authorized Publication

### Review readiness

- external branch is pushed;
- external PR is open and non-draft;
- CI and clean-environment evidence point to its exact head;
- public API, names, license, docs, changelog, and release notes are final;
- independent review has no blocking findings.

### Publication sequence

1. build once from the reviewed commit;
2. publish those artifacts to TestPyPI only with explicit authorization;
3. install them in clean environments and rerun import/extra/fake checks;
4. compare installed metadata and hashes with the candidate;
5. publish the same approved version to public PyPI only with explicit
   authorization;
6. verify public index metadata and clean install by version;
7. create tag/release only if separately authorized and bound to the reviewed
   commit.

Publication is not considered successful from upload output alone. The public
index and clean installer must both resolve the exact version.

### Rollback

Published versions are immutable and are not overwritten. A bad version is
yanked only with explicit authorization, followed by a fixed new version. Until
public proof succeeds, Taskweavn does not consume it.

## 10. S6 — Taskweavn Consumer Migration

### Taskweavn files

```text
pyproject.toml
uv.lock
src/taskweavn/llm/__init__.py
src/taskweavn/llm/contracts.py
src/taskweavn/llm/errors.py
src/taskweavn/llm/retry.py
src/taskweavn/llm/provider_catalog.py
src/taskweavn/llm/config.py
src/taskweavn/llm/client.py
src/taskweavn/llm/logging.py
src/taskweavn/llm/telemetry.py
src/taskweavn/llm/providers/*.py
src/taskweavn/llm/agent_config.py
src/taskweavn/llm/agent_resolver.py
tests/test_llm_package_boundary.py
tests/test_llm.py
tests/test_llm_contracts.py
tests/test_llm_providers.py
tests/test_llm_retry_policy.py
tests/test_llm_claude_provider.py
tests/test_agent_llm_config.py
tests/test_agent_llm_resolver.py
tests/test_settings_config.py
tests/test_settings_readiness.py
docs/architecture/llm-provider-reliability.md
CHANGELOG.md
```

### Changes

- declare `llm-provider-adapter>=0.1.0,<0.2.0`,
  and lock the exact public registry artifact/hashes;
- remove direct provider SDK dependencies from Taskweavn when no other feature
  needs them; provider extras move onto the package requirement;
- replace chat contracts, errors, retry, catalog, transports, and parsers with
  external imports;
- keep pure `taskweavn.llm` and provider-submodule re-export wrappers for the
  documented compatibility window;
- keep environment/Settings resolution in Taskweavn and pass explicit config to
  the package factory/provider constructors;
- add a Taskweavn telemetry observer adapter for current safe provider logs;
- retain Agent I/O logging, usage attribution, OpenHands completion/token
  counting, Action schema, and tool argument helpers;
- update architecture/changelog with dependency range, exact proven version,
  compatibility window, and rollback command.

### Migration tests

- all confirmed 76 baseline tests pass without importing local provider code;
- Settings/Agent resolver builds every external provider;
- provider telemetry maps to current structured logs;
- usage attribution stays product-owned;
- `complete()` and `count_tokens()` still use OpenHands;
- old Taskweavn import paths resolve to the same external symbols;
- an isolated import test fails if an editable/path/Git dependency appears;
- source scan proves no SDK construction/conversion/parser duplicate remains.

### Rollback

Before merge, revert S6 and retain the current Taskweavn implementation. After
merge, restore the previously verified external version through the bounded
dependency and regenerated exact lock. Provider source is never copied back as
the normal rollback mechanism.

## 11. S7 — Full Verification and Release Readiness

### External repository

```text
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv build
<clean-environment verification script against wheel and sdist>
git diff --check <base>...<head>
```

### Taskweavn repository

```text
uv run ruff check <changed Python files and affected tests>
uv run mypy <changed production modules>
uv run pytest -q <76-test baseline and package-boundary tests>
uv run pytest -q
uv lock --check
git diff --check <base>...<head>
```

Repository-wide checks may be supplemented, not replaced, by exact changed-path
checks. Every skipped check records its reason and risk. Network provider smokes
are not required for deterministic acceptance unless separately authorized;
SDK fake/contract tests remain mandatory.

### Duplicate-source audit

Search Taskweavn for:

- `OpenAI(`, `Anthropic(`, and LiteLLM transport entry points;
- provider-specific message conversion and response parser symbols;
- direct provider SDK imports;
- copied external package modules;
- path/editable/Git dependency sources.

Only documented Taskweavn compatibility re-exports and unrelated SDK consumers
may remain, each explained in the audit record.

## 12. S8 — PRs, Independent Review, Merge, and Traceability

### External package PR

- targets `zhanghao1903/llm-provider-adapter:main`;
- includes package source, tests, docs, CI, release metadata, and artifact proof;
- review binds the exact head used to build and publish.

### Taskweavn PR

- targets the confirmed Taskweavn base lineage;
- includes only design/plan, dependency/lock, thin integration, tests, docs, and
  lifecycle records;
- review binds the exact consumer head and public package version.

Blocking findings are fixed in the owning repository and exact-head review is
repeated. Merge authorization is not inferred from approval. Branch deletion,
tags, releases, yanks, and publication are separate mutations.

### Final traceability record

Record:

- requirements handoff/document/commit/hash;
- F2 and F3 commits;
- external repository branch, commits, PR, reviewed head, merge SHA;
- distribution/import names, license, version, artifact hashes, TestPyPI/public
  proof, and tag/release if authorized;
- Taskweavn dependency range, exact lock version/hash, branch, commits, PR,
  reviewed head, and merge SHA;
- checks, limitations, rollback version, and compatibility-wrapper removal
  target.

## 13. Requirement-to-Slice Traceability

| Requirements | Slices |
|---|---|
| REQ-001, REQ-014, REQ-015, REQ-018, REQ-019 | S0, S1, S4, S5, S8 |
| REQ-003, REQ-004, REQ-006, REQ-007, REQ-010 | S2, S3, S7 |
| REQ-005, REQ-008, REQ-009, REQ-011 | S2, S3, S4 |
| REQ-002, REQ-012, REQ-013, REQ-016, REQ-017 | S5, S6, S7, S8 |

## 14. Definition of Done

The feature is complete only when:

1. the external package is the unique authoritative source and all five
   provider adapters satisfy their contract fixtures;
2. wheel/sdist and every provider extra pass clean-environment checks;
3. an explicitly authorized public 0.x release is independently verifiable;
4. Taskweavn consumes that release through a bounded registry dependency and
   exact lock, with no provider implementation duplication;
5. Taskweavn behavior, compatibility imports, usage, logs, Settings, Agent
   resolution, and OpenHands compatibility pass their regression gates;
6. both exact repository snapshots have independent review evidence and all
   blocking findings are closed;
7. authorized merge/release facts and rollback coordinates are recorded in the
   lifecycle trace.

S0 is resolved. F4 starts with authoritative external repository initialization
and does not claim publication until the authorized artifact checks succeed.
