# Feature Plan: First-Party OpenAI and Claude Providers

> Status: implemented
> Type: Product capability and provider integration
> Last Updated: 2026-07-24
> Scope: Plato global Settings, LLM provider layer, Agent loop compatibility
> Related Plan: [LLM Provider 抽象、自动重试与 DeepSeek Thinking](./llm-provider-retry-thinking.md)
> Related Contract: [Settings First-Run API Contract](../../engineering/settings-first-run-api-contract.md)
> Usage Contract: [Token Usage Analytics Contract](../../engineering/token-usage-analytics-contract.md)
> Technical Design: [First-Party OpenAI and Claude Providers Technical Design](./first-party-openai-claude-providers-technical-design.md)

---

## 1. 背景

Plato 已有统一的 `LLMClient`、provider 抽象、重试与错误分类，也已支持
LiteLLM、DeepSeek 和 OpenRouter。但是，对 OpenAI 和 Claude 的使用仍缺少一等
产品入口和稳定的官方 SDK adapter。

仅允许用户把模型名写成 `anthropic/...` 或通过 OpenRouter 间接调用 Claude，
不能满足以下需求：

- 用户无法明确判断当前请求实际由哪个 provider 执行；
- 用户无法在设置页配置 provider 自己的 endpoint、model 和 key；
- provider 特有的消息协议和 tool call 行为缺少独立适配与测试；
- readiness 无法准确说明缺少的是哪个 provider 的配置；
- 发生鉴权、endpoint 或请求协议错误时，用户难以判断恢复方式。

本特性把 OpenAI 和 Claude 作为 Plato 的一等 LLM provider，同时保持 Agent loop
只依赖统一的 LLM 请求/响应合同。

---

## 2. 产品目标

1. 用户可以在全局设置中选择 `OpenAI` 或 `Claude`。
2. 两个 provider 都提供三项明确配置：
   - Base URL
   - Model
   - API key
3. 配置保存后，Plato 的 Router、Collaborator、Execution Agent 和其他使用
   `LLMClient` 的能力使用所选 provider。
4. OpenAI 和 Claude 都必须支持 Agent loop 所需的多轮对话与工具调用。
5. readiness、日志和错误反馈能够明确暴露 provider、model、endpoint 来源和安全的
   失败原因，但永不暴露 API key。
6. OpenAI 和 Claude 的成功调用进入现有 token usage ledger，至少支持总 token
   和 provider 报告的缓存命中 token。
7. 已有 LiteLLM、DeepSeek 和 OpenRouter 行为保持兼容。

---

## 3. 用户故事

### US-1 配置 OpenAI

作为 Plato 用户，我可以在设置页选择 OpenAI，填写 Base URL、Model 和 API key，
保存后让 Plato 使用该配置运行 Agent。

### US-2 配置 Claude

作为 Plato 用户，我可以在设置页选择 Claude，填写 Base URL、Model 和 API key，
保存后让 Plato 通过 Anthropic Messages API 运行 Agent。

### US-3 使用自定义兼容 endpoint

作为使用代理网关或企业网关的用户，我可以修改 provider 的 Base URL，而不需要
修改代码或启动命令。

### US-4 判断当前行为

作为排障用户，我可以从设置摘要、readiness 和 LLM 日志判断当前 provider、model
与 Base URL，但看不到任何 secret。

### US-5 Agent 使用工具

作为 Plato 用户，我选择 Claude 后，Agent 仍可以调用文件、搜索或其他工具，并在
工具结果返回后继续推理，而不是只能完成文本问答。

### US-6 查看 Token 使用情况

作为 Plato 用户，我使用 OpenAI 或 Claude 后，可以在现有用量视图中看到调用的总
token 和 provider 报告的缓存命中 token，并按 Workspace、Session、Plan 和 Task
聚合。provider 未报告缓存数据时，页面应显示不可用，而不是错误显示为零命中。

---

## 4. MVP 范围

### 4.1 Provider

新增并正式支持：

| Provider ID | 显示名 | 默认 Base URL | 专用 API key 环境变量 |
|---|---|---|---|
| `openai` | OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `claude` | Claude | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` |

两个 provider 均允许使用 `LLM_API_KEY` 作为兼容 fallback。专用环境变量优先。

### 4.2 设置页

设置页继续使用单一全局 LLM 配置入口。当前版本没有 workspace 或 session 级配置
入口，因此这里的变更影响整个 Plato 应用。

选择 OpenAI 或 Claude 时显示：

- Provider：下拉选择；
- Base URL：必填 URL；
- Model：必填 provider-native model ID；
- API key：write-only replacement field。

API key 已配置时只显示“已配置”和来源，不回显原值。留空保存表示保留现有有效
secret；首次配置且没有任何有效 key 时，保存失败并定位到 API key 字段。

### 4.3 运行时

运行时必须根据 `LLM_PROVIDER` 构造唯一 provider adapter：

- `openai` 使用官方 OpenAI SDK；
- `claude` 使用官方 Anthropic SDK；
- 不通过字符串猜测模型供应商；
- 不在失败后静默切换到 LiteLLM、OpenRouter 或其他 provider；
- provider 不可用时直接返回结构化错误。

### 4.4 Agent loop 能力

OpenAI 和 Claude 的 MVP 均必须支持：

- system、user、assistant 多轮消息；
- assistant tool call；
- tool result 回传；
- 一轮或多轮 tool call 后继续生成；
- timeout；
- input、output 和 total token usage；
- provider 报告的 cache hit token usage；
- request ID 和安全的 provider metadata；
- transport 层既有自动重试与错误分类。

Claude adapter 负责在 Plato 的统一合同与 Anthropic Messages API 之间转换：

- system message → Anthropic `system`；
- OpenAI-shaped function tool → Anthropic `tools[].input_schema`；
- assistant tool call → `tool_use`；
- tool result → `tool_result`；
- Claude response → Plato `ChatResponse` 和统一 `ToolCall`。

转换只发生在 Claude adapter 内，不进入 Router、Agent loop 或 Settings。

### 4.5 Token usage

OpenAI 和 Claude adapter 必须把 provider usage 归一化为现有 `LLMUsage`：

- `input_tokens`；
- `output_tokens`；
- `total_tokens`；
- `cached_tokens`；
- `cache_hit_tokens`；
- provider 明确报告时的 `cache_miss_tokens`；
- 可计算时的 `cache_hit_ratio`。

总量优先使用 provider 报告值；provider 未给出 total、但同时给出完整 input 和 output
时，使用两者之和。Anthropic 的完整 input 是 `input_tokens`、
`cache_creation_input_tokens` 和 `cache_read_input_tokens` 之和。缓存命中量只能使用
provider 明确报告的 cached/cache-read token，不能根据请求长度或 Context Manager
stable prefix 推测。

成功的 `ChatResponse` 继续由现有 `UsageRecordingLLM` 写入 usage ledger，并通过现有
Workspace、Session、Plan 和 Task token summary 聚合。provider 没有返回缓存字段时，
缓存字段保持 `null`，不能把“未报告”显示成零命中。

---

## 5. 非目标

MVP 不包含：

- provider 自动选择或模型智能路由；
- provider 失败后的跨 provider fallback；
- workspace、session 或单个 Agent 的设置入口；
- 网络连通性或真实付费请求的自动 readiness 探测；
- streaming UI；
- Batch API、Files API、Responses API 专属能力；
- Claude extended thinking 或 OpenAI/Claude 模型专属推理参数统一；
- 图片、音频、PDF 等多模态输入；
- API key 查看、复制或导出；
- provider quota、费用预算或模型价格管理。

这些能力必须通过后续独立需求进入，不能通过 provider adapter 的隐式行为加入。

---

## 6. 配置与生效规则

### 6.1 配置对象

安全配置摘要包含：

```json
{
  "provider": "claude",
  "providerSource": "stored",
  "baseUrl": "https://api.anthropic.com",
  "baseUrlSource": "default",
  "model": "claude-model-id",
  "modelSource": "stored",
  "apiKeyConfigured": true,
  "apiKeySource": "stored",
  "apiKeyEnvVar": "ANTHROPIC_API_KEY"
}
```

`providerOptions` 是前后端共享事实源。每个选项声明：

- provider ID 和 label；
- key 环境变量优先级；
- Base URL 环境变量；
- 默认 Base URL。

前端不得再次维护一套独立 provider 规则；只允许在后端 contract 不可用的降级展示中
使用与 contract 对齐的静态 fallback。

### 6.2 环境变量投射

| 设置字段 | OpenAI | Claude |
|---|---|---|
| Provider | `LLM_PROVIDER=openai` | `LLM_PROVIDER=claude` |
| Base URL | `OPENAI_BASE_URL` | `ANTHROPIC_BASE_URL` |
| Model | `LLM_MODEL` | `LLM_MODEL` |
| API key | `OPENAI_API_KEY` | `ANTHROPIC_API_KEY` |

应用运行期间从集中设置对象生成 effective environment。设置保存成功后，新创建的
LLM client 使用新配置；已发出的请求不被中断或重放。

### 6.3 Base URL 校验

Base URL 必须：

- 是绝对 `http` 或 `https` URL；
- 不包含用户名或密码；
- 不包含 query 或 fragment；
- 使用有效端口；
- 保存时移除末尾 `/`。

URL 校验失败属于可修复输入错误，不发起 provider 请求。

---

## 7. 安全与隐私

1. API key 只写，不通过 GET、PATCH response、日志、事件、Audit 或诊断包返回。
2. provider secret 按 provider 独立保存；切换 provider 不删除其他 provider 的 key。
3. 错误信息不得包含 request headers、Authorization、原始 SDK request 或 secret。
4. 日志可以记录：
   - provider；
   - model；
   - Base URL；
   - request purpose；
   - message/tool 数量；
   - timeout；
   - request ID；
   - token usage；
   - 安全的错误分类。
5. 日志是否记录 prompt/content 继续服从现有日志 profile，不由 provider 自行扩大。

---

## 8. Readiness 与错误体验

readiness 是本地配置检查，不自动发送真实 LLM 请求。

### 8.1 Blocking issues

| Code | 条件 | 建议恢复操作 |
|---|---|---|
| `llm.invalid_provider` | provider 不受支持 | 打开设置并选择 provider |
| `llm.missing_api_key` | 没有有效 key | 填写 key 或设置对应环境变量 |
| `llm.invalid_model` | model 为空 | 填写 provider-native model ID |
| `llm.invalid_base_url` | endpoint 格式无效 | 修改 Base URL |

### 8.2 运行时错误

运行时错误沿用统一分类：

- `fatal_auth`：key 无效或无权限，不重试；
- `fatal_request`：model、消息或 tool schema 无效，不重试；
- `fatal_capability`：请求了 MVP 未支持的 provider 能力，不重试；
- `rate_limit` / `retryable`：按既有 transport retry policy 重试；
- `context_limit`：明确提示上下文超限；
- `unknown`：安全失败并保留诊断关联信息。

用户可见错误必须说明“哪个 provider 的什么配置或请求失败”，不能只显示
“LLM unavailable”。

---

## 9. 兼容与迁移

1. 默认 provider 仍由现有产品默认值决定，本特性不自动切换用户 provider。
2. 现有 `litellm`、`deepseek`、`openrouter` 配置继续有效。
3. 使用 LiteLLM 的 `anthropic/...` 模型字符串不会自动迁移为 `claude`。
4. 选择 first-party provider 后，Model 使用 provider-native ID，不要求
   `openai/` 或 `anthropic/` 前缀。
5. `LLMClient.chat()` 的上层调用合同保持不变。
6. Claude adapter 输出 OpenAI-shaped `raw_assistant_message`，确保现有 Agent loop
   可以把 assistant tool call 和 tool result 写回历史。

---

## 10. 验收标准

### AC-1 Provider catalog

- 设置 API 返回 `openai` 和 `claude`；
- 两者分别返回正确的 label、key 环境变量、Base URL 环境变量和默认 Base URL。

### AC-2 OpenAI 设置

- 用户选择 OpenAI 后可以编辑三项配置；
- 保存后 effective environment 包含 OpenAI provider、endpoint、model 和 key；
- GET response 和页面均不包含 key 原文。

### AC-3 Claude 设置

- 用户选择 Claude 后可以编辑三项配置；
- 保存后 effective environment 包含 Claude provider、endpoint、model 和 key；
- GET response 和页面均不包含 key 原文。

### AC-4 Readiness

- 两个 provider 对缺 key、空 model、非法 Base URL 给出一致且可定位的 blocking issue；
- 合法本地配置无需发起网络请求即可进入 ready。

### AC-5 OpenAI runtime

- 文本请求成功映射为统一 `ChatResponse`；
- function tool call 可以进入 Agent loop；
- request ID、错误分类、input/output/total tokens 可观测；
- OpenAI `prompt_tokens_details.cached_tokens` 或兼容 cache hit 字段进入
  `cache_hit_tokens` 和 usage ledger。

### AC-6 Claude runtime

- system/user/assistant 消息正确转换；
- function schema 正确转换为 Anthropic tool schema；
- `tool_use` 正确转换为统一 `ToolCall`；
- 下一轮 assistant tool call 和 tool result 正确转换回 Anthropic Messages API；
- request ID、错误分类、input/output/total tokens 可观测；
- Anthropic `cache_read_input_tokens` 进入 `cache_hit_tokens` 和 usage ledger；
- Anthropic 三个 input counter 汇总为统一 `input_tokens`，并参与 `total_tokens`；
- `cache_creation_input_tokens` 不被错误标记为 cache miss。

### AC-7 无静默 fallback

- OpenAI 或 Claude 初始化、鉴权或调用失败时，不调用其他 provider；
- 用户获得结构化错误和恢复建议。

### AC-8 回归

- LiteLLM、DeepSeek 和 OpenRouter 的已有测试通过；
- Settings 前端测试、backend contract 测试、类型检查和生产构建通过。

---

## 11. 测试矩阵

| 层级 | OpenAI | Claude |
|---|---|---|
| Catalog/config | provider metadata、key、Base URL | provider metadata、key、Base URL |
| Storage | write-only key、endpoint 持久化 | write-only key、endpoint 持久化 |
| Readiness | ready / missing key / invalid URL | ready / missing key / invalid URL |
| Provider unit | text、tool call、total/cache-hit usage、timeout | message conversion、tool use/result、total/cache-hit usage、timeout |
| Error unit | auth/request/retry | auth/request/capability/retry |
| Frontend | 选择、默认 URL、保存三项 | 选择、默认 URL、保存三项 |
| Regression | DeepSeek/OpenRouter/LiteLLM | DeepSeek/OpenRouter/LiteLLM |

真实 provider 网络调用不进入默认测试套件。可在显式 integration test 中使用开发者
自己的 key 验证，但测试不得打印或持久化 key。

---

## 12. 交付切片

### Slice 1: Product contract

- 接受本特性方案；
- 更新 Settings API contract；
- 确定 provider ID、环境变量和默认 endpoint。

### Slice 2: Provider catalog and Settings

- 后端 provider catalog；
- 配置存储和 effective environment；
- readiness；
- 前端 provider 表单；
- write-only secret 测试。

### Slice 3: Official SDK adapters

- OpenAI adapter；
- Claude adapter；
- 双向 tool protocol 转换；
- input/output/total/cache-hit usage、request ID、日志和错误分类。

### Slice 4: Verification and documentation

- 后端与前端完整回归；
- build、lint、typecheck；
- 配置文档和安全说明；
- 可选的显式真实 provider integration smoke。

---

## 13. 完成定义

只有同时满足以下条件，本特性才可标记为 done：

- 用户能在设置页完成 OpenAI 或 Claude 三项配置；
- 配置安全地进入对应官方 SDK；
- 两个 provider 都能支撑 Agent loop 工具调用闭环；
- 两个 provider 的总 token 和 provider 报告的缓存命中 token 进入现有 usage ledger；
- 失败时没有跨 provider 静默 fallback；
- readiness 和日志能说明当前实际行为；
- secret 不出现在任何读取合同或诊断产物中；
- 所有验收测试和既有 provider 回归通过。
