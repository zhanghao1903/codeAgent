# Requirements: Standalone LLM Provider Package

- Status: Confirmed
- Requirement owner: Taskweavn product and engineering
- Source: User conversation in the configured Requirements task
- Created: 2026-08-09
- Last updated: 2026-08-09
- Confirmed by: User in Requirements task
- Confirmed at: 2026-08-09T10:30:28Z

## Source Request

重新评估 Taskweavn 当前 LLM provider 层的独立打包边界。目标是把可复用能力做成单独发布、独立版本化的 Python 包；Taskweavn 以后通过正常包依赖使用它，而不是继续持有 provider 实现代码；其他聊天机器人、想法验证应用或 Agent 应用也可以使用同一个包。包源码的权威 Git 仓库为 [`zhanghao1903/llm-provider-adapter`](https://github.com/zhanghao1903/llm-provider-adapter)；distribution/import 名称由用户明确延后决定。

## Problem And Desired Outcome

Taskweavn 已经具有 provider-neutral chat contract、统一响应、重试与错误分类，以及 OpenAI、Claude、DeepSeek、OpenRouter、LiteLLM provider 适配器。这些能力具有跨应用复用价值，但当前位于 `taskweavn.llm` 命名空间，并与 Taskweavn 的 Agent 角色路由、Settings、usage ledger、observability、Action schema 和 OpenHands 兼容接口混在同一模块树中。

如果其他应用复制这些实现，会产生多份协议转换、错误分类和重试逻辑；如果 Taskweavn 继续直接维护 provider transport，则每次新增供应商或修复协议兼容性都必须发布整个产品。期望结果是形成一个不依赖 Taskweavn 业务模型的外部 Python 包，由它提供稳定的 LLM chat/provider 能力，并让 Taskweavn 退化为配置、业务归属和运行时集成层。

## Current Boundary Assessment

### External package should own

- provider-neutral synchronous chat request and response contracts；
- tool call、usage、reasoning metadata、request ID 和 provider capability 的归一化模型；
- provider-neutral error taxonomy、retry policy、retry record 和 timeout 行为；
- provider transport、协议转换、响应解析和安全错误净化；
- provider catalog 中可跨应用复用的 ID、默认 endpoint、credential key 名称和 capability 元数据；
- 明确、可选的 provider SDK dependencies；
- 不绑定具体日志系统的安全 telemetry hook 或 observer contract；
- 独立构建、测试、版本、变更日志和使用文档。

### Taskweavn should continue to own

- Agent role/profile 配置、继承和 provider resolution；
- Settings 的持久化、secret storage、readiness API 和前端表单；
- token usage 对 Workspace、Session、Task、Plan、Agent 的归属与持久化；
- Taskweavn observability、Audit、diagnostic bundle 和产品日志投射；
- `Action` / `Observation` 业务模型以及 Action 到 tool schema 的转换规则；
- AgentLoop、Router、Collaborator、Audit Agent 等业务调用方；
- 暂未迁移的 OpenHands `complete()` / `count_tokens()` 兼容层；
- 产品级 provider 选择、跨 provider fallback、预算、权限和用户体验。

## Goals

- 建立一个无 Taskweavn 业务依赖、可供多个 Python 应用复用的 LLM provider 包。
- 让 Taskweavn 通过已发布且有版本约束的包依赖使用 provider 能力，不 vendor、不复制、不通过仓库相对路径导入 provider 源码。
- 在迁移期间保持现有 chat、tool calling、usage、retry、timeout、错误分类和安全净化行为。
- 让 provider SDK、协议兼容和回归测试可以独立演进、发布和回滚。
- 把 Taskweavn 留成薄业务适配层，并显著减少仓库内 provider transport 与协议转换代码。

## Non-goals

- 不把 EventBus、Action、Observation、Agent、Task、Plan、Session 或 UI 抽象放进该包。
- 首版不新增 async API、streaming、multimodal、Batch API、Files API 或 provider 专属 Responses API。
- 首版不新增自动模型路由、跨 provider fallback、circuit breaker、health check、hedging、rate limiter 或价格预算管理。
- 不让公共包持久化 API key、Taskweavn Settings、usage ledger、Audit 或日志文件。
- 不在本需求中重新设计各 provider 已有的官方协议能力，也不借迁移隐式扩大 thinking 或 extended-thinking 语义。
- 不在需求阶段决定目录布局、类名、工厂实现或内部模块拆分；这些属于后续技术设计。

## User Scenarios

### Scenario 1: Taskweavn consumes the published package

- Actor: Taskweavn maintainer
- Starting context: Taskweavn 当前在仓库内维护 provider transport 和协议转换代码。
- Action: 安装并锁定一个已发布的兼容版本，通过薄适配层构造 provider 并执行现有 chat 调用。
- Expected outcome: Taskweavn 行为和现有调用方 contract 保持兼容，provider 实现不再由 Taskweavn 源码拥有。
- Failure recovery: 新包版本不兼容时，可回退到最近一个已验证版本；未验证版本不得进入 Taskweavn release lock。

### Scenario 2: Another application calls an LLM provider

- Actor: 聊天机器人或想法验证应用的开发者
- Starting context: 应用没有 Taskweavn 的 Agent、Task、Settings 或 observability 模块。
- Action: 只安装需要的 provider extra，显式传入 model、credential、endpoint、timeout 和 chat request。
- Expected outcome: 应用获得统一的 chat response、tool calls、usage、request metadata 和错误类型，不需要安装或导入 Taskweavn。
- Failure recovery: 缺少对应 provider extra 或配置无效时，在发起网络请求前得到明确、可处理且不泄露 secret 的错误。

### Scenario 3: Application uses tool calling across providers

- Actor: Agent application developer
- Starting context: 应用使用 provider-neutral message 和 tool schema。
- Action: 分别通过支持 tool calling 的 provider 发送等价请求。
- Expected outcome: provider-specific request/response 被转换为统一 tool call contract，provider 不支持的能力被显式拒绝而不是静默降级。
- Failure recovery: 调用方可以根据统一 capability/error 信息选择修改请求；包不自动切换 provider。

### Scenario 4: A provider request fails transiently

- Actor: Package consumer
- Starting context: 请求遇到 rate limit、可重试的 server error、timeout 或 transport error。
- Action: 包按照调用方可配置的单一 retry policy 执行有限重试。
- Expected outcome: 成功响应携带完整 retry records；重试耗尽时抛出归一化错误并保留安全诊断信息。
- Failure recovery: 调用方决定是否稍后重试、换 provider 或向用户报告；包不做隐藏的跨 provider fallback。

## Functional Requirements

| ID | Requirement | Source | Priority | Confirmation |
| --- | --- | --- | --- | --- |
| REQ-001 | LLM provider 能力必须作为独立版本化、可构建和可发布的 Python distribution 交付，并可从不包含 Taskweavn 源码的干净环境安装。 | User | Must | Confirmed |
| REQ-002 | Taskweavn 必须通过正常 dependency declaration 与 lockfile 使用已发布版本；不得 vendor provider 源码、复制实现或依赖仓库相对路径。 | User | Must | Confirmed |
| REQ-003 | 公共包必须提供稳定的 provider-neutral synchronous chat contract，至少覆盖 messages、model、tools、tool choice、temperature、max tokens、timeout、provider options 和 thinking capability declaration。 | Existing contracts; DEC-003 | Must | Confirmed |
| REQ-004 | 公共包必须归一化 text、reasoning、tool calls、finish reason、usage、cache token usage、provider/model、request ID、retry records 和安全 raw metadata；无法提供的字段必须有稳定的空值语义。 | Existing contracts | Must | Confirmed |
| REQ-005 | 每个被迁移的 provider adapter 必须保留当前已声明的 capability 和参数支持；不支持的能力必须在请求前或 provider response 解析时显式失败，不得静默忽略或降级。 | Existing provider implementation | Must | Confirmed |
| REQ-006 | 公共包必须拥有统一错误分类、错误净化和有界重试行为，并保证 SDK 内部重试关闭或不与包级重试重复；不得自动执行跨 provider fallback。 | Reliability ADR and current retry behavior | Must | Confirmed |
| REQ-007 | 公共包不得记录或返回 API key、authorization header、完整敏感 request/response、secret-bearing exception repr 或未经净化的 SDK payload。 | Existing security contract | Must | Confirmed |
| REQ-008 | 公共包必须允许消费者通过可选 extras 只安装所需 provider SDK；chat core 不得依赖 Taskweavn、OpenHands、UI 框架、数据库或具体 observability 实现。 | Reuse goal | Must | Confirmed |
| REQ-009 | 公共包必须接受显式配置，并可提供跨应用复用的 provider catalog/validation；它不得拥有 Taskweavn Settings 持久化、secret storage 或 UI contract。 | Boundary assessment | Must | Confirmed |
| REQ-010 | 公共包必须提供不绑定具体日志框架的安全 telemetry seam，使消费者可以接收 request、response、retry 和 error 摘要；默认行为不得要求 Taskweavn logger。 | Current observability coupling | Should | Confirmed |
| REQ-011 | 首版必须包含 DEC-002 最终确认的 provider 集合；Taskweavn 只有在对应 provider 已从外部包可用并通过等价测试后，才能删除该 provider 的仓库内实现。 | User; DEC-002 | Must | Confirmed |
| REQ-012 | Taskweavn 必须保留 Agent resolution、Settings、usage attribution/persistence、Audit/diagnostics 和 Action-to-tool-schema 逻辑，并通过薄适配层把这些业务概念映射到公共包 contract。 | Boundary assessment | Must | Confirmed |
| REQ-013 | Taskweavn 迁移不得改变现有 provider 选择、配置优先级、tool calling、usage 记录、retry/error、request logging 摘要和调用方失败语义，除非后续需求显式批准。 | Regression goal | Must | Confirmed |
| REQ-014 | 公共包必须产出 wheel 和 sdist，并在干净环境验证安装、import、provider extra、基础 chat fake/contract tests 和文档示例。 | Publishing goal | Must | Confirmed |
| REQ-015 | 公共包必须发布 provider support matrix、配置说明、安全边界、迁移说明、版本兼容策略和最小使用示例。 | External reuse goal | Must | Confirmed |
| REQ-016 | Taskweavn 必须使用有上界的兼容版本范围并锁定精确版本；package 升级应有独立回归门禁和可操作的版本回退路径。 | Package migration precedent | Must | Confirmed |
| REQ-017 | 外部包与 Taskweavn 集成完成后，Taskweavn 仓库不得继续拥有 provider transport、provider-specific protocol conversion 或 provider response parser 的重复实现；临时兼容 facade 只允许转发到外部包并必须有移除窗口。 | User; DEC-005 | Must | Confirmed |
| REQ-018 | 包的公开 API 在同一兼容版本范围内必须遵守声明的兼容策略；breaking change 必须通过新的不兼容版本范围发布。 | External consumer goal | Must | Confirmed |
| REQ-019 | 包源码必须以 `https://github.com/zhanghao1903/llm-provider-adapter` 为权威 Git 仓库；首次实现必须初始化该仓库，不得在 Taskweavn 仓库内建立第二份权威 package source。 | User confirmation | Must | Confirmed |

## Acceptance Criteria

| ID | Requirement IDs | Observable criterion | Confirmation |
| --- | --- | --- | --- |
| AC-001 | REQ-001, REQ-014 | Given 一个不含 Taskweavn 的干净 Python 环境，when 安装构建出的 wheel 及一个 provider extra，then 包可 import，contract/provider 可构造，离线 contract tests 通过。 | Confirmed |
| AC-002 | REQ-002, REQ-016 | Given Taskweavn 的 dependency metadata 和 lockfile，when 检查 LLM package 依赖，then 它来自已发布 distribution、有上界约束并锁定精确版本，不使用 editable/path/repository-relative source。 | Confirmed |
| AC-003 | REQ-003, REQ-004, REQ-005 | Given 每个首版 provider 的 text、tool call、usage、reasoning/unsupported-capability fixture，when 执行统一 chat contract，then 输出与 capability/error 行为符合 provider support matrix。 | Confirmed |
| AC-004 | REQ-006 | Given retryable 和 non-retryable failure fixtures，when 执行请求，then 只发生包级有界重试，retry records 可观察，non-retryable failure 不重试，且不会切换 provider。 | Confirmed |
| AC-005 | REQ-007, REQ-010 | Given 包含测试 secret 和敏感 SDK payload 的失败，when 收集 exception、telemetry 和测试日志，then secret、authorization 和原始敏感 payload 均不可见。 | Confirmed |
| AC-006 | REQ-008 | Given 只安装 chat core 或单一 provider extra 的环境，when 查看依赖和 import 行为，then 不要求 Taskweavn/OpenHands/数据库/UI，且未安装的 provider 返回明确 missing-extra 错误。 | Confirmed |
| AC-007 | REQ-009, REQ-012 | Given Taskweavn Settings 和 Agent role profile，when 构造一次 LLM 调用，then 业务仓库完成配置/归属映射，公共包只接收通用配置和 chat contract。 | Confirmed |
| AC-008 | REQ-011, REQ-013 | Given 当前 Taskweavn LLM、Settings 和 Agent resolver 回归套件，when 切换到包依赖，then 当前 76 项基线测试继续通过，并补充真实 package-boundary integration tests。 | Confirmed |
| AC-009 | REQ-017 | Given 完成迁移的 Taskweavn source tree，when 搜索 provider SDK client、provider-specific request conversion 和 response parser，then 除外部包 import/薄 facade 外不存在仓库内重复实现。 | Confirmed |
| AC-010 | REQ-014, REQ-015, REQ-018 | Given 一个不了解 Taskweavn 的外部应用开发者，when 按 README 安装并运行离线示例，then 能选择 provider、构造 chat/tool 请求、处理 usage 和统一错误，并能判断版本兼容范围。 | Confirmed |
| AC-011 | REQ-016 | Given 新 package 版本未通过 Taskweavn 回归，when 准备 release，then lockfile 不升级；given 已升级版本出现回归，then 可恢复最近验证版本而无需恢复 provider 源码副本。 | Confirmed |
| AC-012 | REQ-019 | Given 首次 package implementation，when 检查 Git remote 和源码位置，then 唯一权威 package source 位于 `zhanghao1903/llm-provider-adapter`，Taskweavn 仅保留消费端适配。 | Confirmed |

## Constraints

- 当前仓库 Python floor 是 `>=3.11`；首版 package 同样采用 Python `>=3.11`。
- 当前生产 LLM 主路径是 synchronous `chat()`；`complete()` 与 `count_tokens()` 仍通过 OpenHands 兼容层提供。
- 当前 provider catalog 包含 `openai`、`claude`、`deepseek`、`openrouter` 和 `litellm`。
- 包源码的权威 Git 仓库是 `https://github.com/zhanghao1903/llm-provider-adapter`；该公开仓库在确认时为空，首次实现必须先完成基础初始化。
- OpenAI 与 Claude 当前使用官方 SDK；DeepSeek 与 OpenRouter 使用 OpenAI-compatible transport；LiteLLM 是兼容入口。
- SDK 自带 retry 必须关闭或证明不会和统一 retry owner 重复。
- package 不能依赖 Taskweavn 的 `observability`、`usage`、Settings、Action 或 Agent 模块。
- 未发布、未锁定或未通过 clean-environment smoke 的 package 版本不能替换 Taskweavn 仓库内实现。

## Failure And Recovery

- 缺少 provider extra、credential、model 或合法 endpoint 时，在网络请求前返回可处理的配置错误。
- provider capability 不匹配时显式返回 capability error，不丢弃参数后继续调用。
- retry 耗尽后返回统一错误和安全 retry records；是否稍后重试或切换 provider 由调用方决定。
- timeout/transport error 不保证 upstream 未接收或计费；包必须记录这一语义，且不得在调用方 retry 之外增加隐藏重放。
- package 发布失败或 clean install 失败时，Taskweavn migration 不得切换依赖。
- Taskweavn 升级后发生回归时，优先回退到上一个已验证 package 版本；不得用重新复制 provider 源码作为常规恢复方式。

## Assumptions

| ID | Assumption | Reason | Impact if wrong | Status |
| --- | --- | --- | --- | --- |
| ASM-001 | 当前 76 项 LLM/Settings/Agent resolver 测试可作为迁移前行为基线，但仍需增加独立 package contract tests 和 package-boundary integration tests。 | 2026-08-09 在最新 `main` 上验证通过。 | 若基线覆盖不足，迁移可能保留测试但改变真实协议行为。 | Accepted as current evidence |
| ASM-002 | 其他目标应用需要的是 provider-neutral chat/tool/usage/error 能力，而不是 Taskweavn 的 Agent 或任务领域模型。 | 用户明确要求公共复用，并此前将 Event 与业务 Action/Observation 分离。 | 若外部应用还需要 Agent framework，需另立需求，不能扩张本包。 | Accepted |
| ASM-003 | 独立版本与独立发布意味着 package 源码不归 Taskweavn 产品仓库所有；Taskweavn 只保留 integration code。 | 用户要求“通过包引入，而不是代码”，并指定独立 Git 仓库。 | 若未来改为同仓 monorepo，仓库代码量与发布隔离目标会变化。 | Accepted |

## Open Decisions

| ID | Decision | Options or recommended default | Impact | Status |
| --- | --- | --- | --- | --- |
| DEC-001 | distribution、import package 和源码仓库叫什么、由谁维护？ | 源码仓库已确认为 `zhanghao1903/llm-provider-adapter`；distribution/import 名称由用户明确延后，但必须在公共 API freeze 和首次发布前决定。 | 仓库 ownership 已确定；延后的名称仍会决定发布坐标、namespace 和文档。 | Repository resolved; package name deferred |
| DEC-002 | 首版迁移哪些 provider？ | 一次性迁移当前五个：OpenAI、Claude、DeepSeek、OpenRouter、LiteLLM。 | 允许最终清空 Taskweavn 仓库内 provider 实现，并定义首版测试/依赖规模。 | Accepted recommended default |
| DEC-003 | 首版公共 contract 是否只覆盖 synchronous `chat()`？ | 只覆盖 `chat()`；`complete()`/`count_tokens()` 暂留 Taskweavn OpenHands compatibility adapter，后续按真实跨应用需求独立评估。 | 公共包首版不依赖或重做 OpenHands compatibility。 | Accepted recommended default |
| DEC-004 | 首版如何发布及支持什么 Python floor/license？ | 接受独立 GitHub 仓库、PyPI `0.x` 公共发布、Python `>=3.11`、先 TestPyPI/clean-env 验证；license 选择延后，但必须在首次公开发布前决定。 | 发布与 Python 支持策略已确定；license 仍是发布前合规门禁。 | Publishing accepted; license deferred |
| DEC-005 | `taskweavn.llm` 旧导入是否保留兼容窗口？ | 保留一个有明确移除版本的薄 re-export/adapter 窗口，不保留 provider 实现。 | 降低 Taskweavn 内部迁移风险，同时确保 provider 源码真正移出。 | Accepted recommended default |

## Traceability

| Source statement or artifact | Derived IDs |
| --- | --- |
| 用户要求“独立打包发布，Taskweavn 通过包引入，其他应用也可用”。 | REQ-001, REQ-002, REQ-014, REQ-015, REQ-017, REQ-018 |
| 用户确认推荐边界，并指定 `zhanghao1903/llm-provider-adapter`；package 名称延后决定。 | REQ-019, ASM-002, ASM-003, DEC-001, DEC-002, DEC-003, DEC-004, DEC-005 |
| [`first-party-openai-claude-providers.md`](first-party-openai-claude-providers.md) 已实现官方 OpenAI/Claude adapter、统一 settings/runtime 与无静默 fallback。 | REQ-003, REQ-005, REQ-006, REQ-013 |
| [`ADR-0006-llm-provider-transport-boundary.md`](../../decisions/ADR-0006-llm-provider-transport-boundary.md) 规定 provider transport boundary。 | REQ-005, REQ-006, REQ-009, REQ-012 |
| [`llm-provider-reliability.md`](../../architecture/llm-provider-reliability.md) 记录统一 contract、retry、error、normalization、logging 与已知限制。 | REQ-003, REQ-004, REQ-006, REQ-007, REQ-010 |
| [`app-control-tool-package-migration.zh-CN.md`](app-control-tool-package-migration.zh-CN.md) 提供本仓库已验证的“外部包拥有能力、Plato 保留业务适配、bounded version + lock + rollback”迁移模式。 | REQ-002, REQ-012, REQ-016, REQ-017 |
| 最新 `main` 的 76 项 LLM/Settings/Agent resolver 测试通过。 | REQ-013, AC-008, ASM-001 |

## Confirmation

- [x] Problem and desired outcome are correct.
- [x] Goals and non-goals match the intended scope.
- [x] Requirements describe the required behavior.
- [x] Acceptance criteria can judge completion.
- [x] Assumptions are accepted or corrected.
- [x] Decisions are resolved or explicitly deferred.

Decision: Confirmed by user on 2026-08-09; package name and license are explicitly deferred until before first public release.
