# LLM Provider Reliability 架构事实

> Status: current implementation fact document
>
> Calibrated: 2026-08-12
>
> Package release: `llm-provider-adapter==0.1.0`
>
> Original historical document:
> [llm-provider-reliability.original.md](archive/original/llm-provider-reliability.original.md)

## 1. 文档目的

本文记录 Taskweavn 在 LLM provider 抽取完成后的真实边界。可复用的 chat
contract、错误、retry、provider catalog、协议转换、response parsing 和五个
provider transport 由外部包 `llm-provider-adapter` 负责；Taskweavn 只保留产品
装配、Agent 语义、日志/用量归属和兼容 facade。

外部包的实现和发布文档是 provider 行为的权威来源：

- repository: `https://github.com/zhanghao1903/llm-provider-adapter`；
- distribution/import: `llm-provider-adapter` / `llm_provider_adapter`；
- released version: `0.1.0`，MIT，Python 3.11+；
- Taskweavn dependency: `llm-provider-adapter[all]>=0.1.0,<0.2.0`；
- Taskweavn lock: public PyPI registry artifact，精确版本和哈希见 `uv.lock`。

## 2. Source ownership

### 2.1 外部包权威所有权

`llm_provider_adapter` 定义：

- `ChatRequest`、`ChatResponse`、`ToolCall`、`LLMUsage`；
- `ProviderCapabilities`、`ThinkingConfig`、`ProviderRoutingConfig`；
- synchronous chat-only `LLMProvider` protocol；
- `RetryPolicy`、`RetryRecord`、`BaseLLMProvider` 和错误分类；
- 安全的 provider error hierarchy 与 telemetry event/observer contract；
- OpenAI、Claude、DeepSeek、OpenRouter、LiteLLM adapters；
- provider catalog、endpoint validation、SDK compatibility conversion 和 parser。

Taskweavn 不再包含 provider transport、SDK client、协议转换或 response parser 的
实现副本。`taskweavn.llm.providers.*`、`contracts.py`、`errors.py` 和 `retry.py`
只提供兼容导出，其中共享类型保持与外部包完全相同的对象 identity。

### 2.2 Taskweavn 产品所有权

Taskweavn 继续定义：

- `LLMClient`、`LazyLLMClient`、`LLMClientConfig`；
- Settings/environment/secret projection 和默认 provider/model/timeout；
- Agent role profile、inheritance、resolver 和 usage attribution；
- Action-to-tool schema 与 tool argument parsing；
- Agent loop、Collaborator、Router、Inquiry、Risk 和 Audit 调用方策略；
- OpenHands `complete()` / `count_tokens()` 兼容路径；
- application `llm` / `llm_io` 日志与 diagnostics；
- 外部安全 telemetry event 到 Taskweavn structured log 的 allow-list adapter。

## 3. 当前调用链

Main Page 的 provider chat 主路径是：

```text
Agent caller
  -> UsageRecordingLLM
  -> AgentConfiguredLLM
  -> LazyLLMClient
  -> LLMClient.chat
  -> llm_provider_adapter provider.chat
  -> package-owned retry + SDK transport
  -> immutable ChatResponse
```

`LLMClient.complete()` 和 `count_tokens()` 仍通过 lazy `openhands.sdk.LLM`。外部
`LLMProvider` 只有 `chat()`；这两个接口是 Taskweavn 产品兼容面，不会被伪装成
外部 provider capability。

## 4. Public contract boundary

### 4.1 Request/response immutability

外部请求和响应的 JSON-shaped nested collections 递归只读，并与构造时的输入值
分离。Taskweavn 需要持久化或继续修改 transcript 时，必须调用外部模型的
`to_dict()`，获得 detached、可变且可 JSON 序列化的 projection。

当前显式转换点包括：

- Execution AgentLoop 将 `raw_assistant_message` 加入下一轮 transcript；
- Collaborator profile runner 将 assistant message 加入上下文；
- application LLM output logger 生成安全的 detached log payload。

禁止把 package-owned frozen mapping 原样写入需要标准 `json.dumps()` 的存储或
hash 路径。

### 4.2 Chat-only protocol

`LLMProvider` 声明 `name`、`capabilities` 和同步 `chat(ChatRequest)`。0.1 不提供：

- async/streaming/multimodal；
- Agent framework、persistence 或 secret storage；
- 自动 cross-provider fallback、hedging、circuit breaker；
- `complete()` 或 `count_tokens()`。

### 4.3 Provider set

| Provider | Transport | 0.1 关键事实 |
|---|---|---|
| OpenAI | OpenAI SDK | tools、reasoning effort、custom endpoint、SDK retry disabled |
| Claude | Anthropic SDK | system/message/tool conversion、custom endpoint、SDK retry disabled |
| DeepSeek | OpenAI-compatible SDK | model-profile capability preflight、thinking/reasoning support |
| OpenRouter | LiteLLM | OpenRouter routing object、reasoning output normalization |
| LiteLLM | LiteLLM | provider-dependent tools/reasoning output、`num_retries=0` |

完整能力矩阵由外部包 `docs/provider-support.md` 维护。Taskweavn 不复制该矩阵为
第二份 provider contract。

## 5. Retry, timeout, errors, and safety

外部包是 provider attempt retry 的唯一 owner：

- SDK/LiteLLM retry 被禁用；
- auth、request、capability、context-limit 和 unknown failure 不自动重试；
- allow-listed transient/rate-limit failure 可在 `RetryPolicy` 边界内重试；
- 所有识别出的 timeout 均不 replay，包括没有显式 `timeout_seconds` 时来自 SDK
  默认值的 timeout，因为 upstream 是否已接受或计费不可知；
- package 不自动更换 provider。

normalized public error、retry record 和 telemetry 不保留 raw SDK exception、
exception context/cause、header、credential、request/response body 或任意 metadata。
Taskweavn 调用方只依赖类型、classification、status 和安全 message；不得重新引入
`original_error` 兼容访问。

## 6. Configuration and assembly

Taskweavn 的 Settings/environment 投影继续支持：

- `deepseek`、`openrouter`、`litellm`、`openai`、`claude`；
- provider-specific credential 与 custom endpoint；
- `LLM_MODEL`、`LLM_REQUEST_TIMEOUT_SECONDS`；
- DeepSeek thinking 和 OpenRouter routing；
- Agent role profile/inheritance 与 usage attribution。

外部包本身从不读取 environment，也不持久化 secrets。所有 credential、endpoint、
model 和 routing 都由 Taskweavn 显式解析后传入 provider constructor/request。
provider constructor 会在 transport 前校验 required credential 和 endpoint。

`LLMClient(model=..., provider=None)` 只在第一次 `chat()` 时 lazy 构造 LiteLLM
adapter。这使 OpenHands-only `complete()` / `count_tokens()` 可以在不满足外部 chat
credential 预检时继续保持原兼容行为。

## 7. Telemetry, logging, and usage

Taskweavn 为所有自身构造的 provider 注入 `TaskweavnTelemetryObserver`。adapter 只
映射 package allow-list event：

- request: provider/model、message/tool count、timeout、thinking flag；
- response: finish reason、content/tool counts、request ID、normalized usage、retry count；
- retry/error: classification、attempt、delay、safe error type、status code。

该 adapter 不接收或记录 messages、tool arguments、headers、raw payload、任意
metadata 或 raw exception text。observer failure 由外部包隔离，不能改变 chat 结果。

Application `llm_io` 仍是 Taskweavn 自己的诊断面，可能包含调用方显式记录的完整
prompt/response。它不属于外部包的安全 telemetry contract，部署时必须继续按
Taskweavn logging policy 管理。

`UsageRecordingLLM` 仍只对成功的 logical chat response 写 workspace usage event；
provider retry attempt 和最终失败不生成额外 usage event。

## 8. Compatibility and deprecation

现有 Taskweavn import path 在一个 minor compatibility window 内保留，并直接
re-export 外部 symbol。新的可复用 consumer 应直接 import
`llm_provider_adapter`；Taskweavn 内部产品调用方继续通过 `taskweavn.llm` 装配面。

最早移除兼容 re-export 的版本是 Taskweavn `0.3.0`，且需要：

1. repository-wide import audit；
2. release note 和迁移提示；
3. 独立 breaking-change review；
4. 不因 0.1.x package patch upgrade 提前删除。

## 9. Release and rollback boundary

外部 `0.1.0` 的 TestPyPI 和 public PyPI 发布使用同一个 workflow artifact。Taskweavn
只接受 public registry dependency，不接受 path/editable/Git/local-wheel/vendor source。

升级遵循：

1. 保持 bounded range `<0.2.0`；
2. 更新 exact lock；
3. 跑 provider facade、error、telemetry、Agent loop 和 full backend regression；
4. 任何 package head/artifact 变化均重新 review。

若需要回滚，Taskweavn 应回退 consumer commit/lock 到先前版本；不得在 Taskweavn
仓库重新复制 provider implementation。公开 PyPI release 不可删除或覆盖。

## 10. Known limits

1. `complete()` / `count_tokens()` 仍绕过 external chat retry 和 usage normalization。
2. 同步 transport 不能由 AgentLoop hard-cancel；timeout 仍依赖 SDK 返回。
3. 没有真实 provider credential 的常规 CI；transport 通过 deterministic fake/fixture
   和 package CI 验证。
4. Application `llm_io` disclosure policy 仍由 Taskweavn 管理。
5. Agent role client 是 runtime assembly snapshot；Runtime Config 尚无 live LLM
   consumer replacement。
6. provider upstream 行为可能变化；0.1.x upgrade 必须有 package fixture 和 consumer
   regression 证据。

## 11. Verification index

- requirements: `docs/plans/feature/llm-provider-package-requirements.md`
- technical design: `docs/plans/feature/llm-provider-package-technical-design.md`
- implementation plan: `docs/plans/feature/llm-provider-package-implementation-plan.md`
- migration inventory: `docs/plans/feature/llm-provider-package-migration-inventory.md`
- release trace: `docs/releases/standalone-llm-provider-package.md`
- boundary tests: `tests/test_llm_package_boundary.py`
- package lock: `uv.lock`

修改此边界时至少验证 exact symbol identity、registry lock source/hashes、五 provider
re-export、safe telemetry allow-list、immutable serialization、OpenHands compatibility、
duplicate-source scan、AgentLoop/Collaborator integration 和 full backend suite。
