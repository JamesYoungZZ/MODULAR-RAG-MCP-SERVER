# 生成 Livestream Host Copilot DEV_SPEC 的 Prompt

我想写一份完整、可执行、可用于 Spec 驱动开发的开发规范文档（`DEV_SPEC.md`），用于指导一个 Python Agent 项目的全部开发流程。

请根据下面的业务背景、系统边界、架构方向、质量目标和学习目标，生成一份接近生产级工程设计深度的 DEV_SPEC 初稿。文档不仅要描述“做什么”，还要讲清楚“为什么这样设计、替代方案是什么、Trade-off 是什么、如何测试、如何验收、如何逐步开发”。

最终文档应与一个成熟大型项目的 DEV_SPEC 体量相当，而不是简单的项目 README：

- 使用中文撰写，关键术语可附英文
- 目标篇幅约 2,800–3,400 行，约 180–240 KB
- 至少包含 7 个一级章节、完整架构图、目录树、数据流、配置示例、测试方案和详细排期
- 约 70–90 个可独立验收的开发任务
- 每项功能需求必须能映射到验收标准、测试类型和开发任务
- 不允许出现没有结论的 `TODO`、`TBD` 或空章节
- 不允许用技术名词堆砌代替设计理由
- 不生成实际业务代码，只生成开发规范

---

## 1. 项目是什么

我要开发一套面向直播电商 Host 端的实时、多语言 Agent 系统，项目暂定名：

> **Livestream Host Copilot / EU Multi-market Live Commerce Agent**

我在 Zalando 开发直播系统。Audience 端观众会不断向直播间发送聊天消息，Host 端主播需要一边直播讲解商品，一边阅读和回复观众问题。

单场 Show 约有 10,000 名观众。没有 Agent 时，主播人工消息回复率不足 10%。主播为了回复重要问题，需要停止或打断当前展示，低头看屏幕、筛选消息、组织语言并打字，影响直播节奏，也会漏掉大量具有购买意图或商品咨询价值的问题。

本项目要构建一个 Host Copilot：

1. 从高并发 Audience 消息流中识别真正值得回复的问题。
2. 区分闲聊、商品咨询、价格库存、购买意图、配送、退换货、投诉和风险内容。
3. 根据业务价值、风险、时效和消息热度进行优先级调度。
4. 调用商品、价格、库存、优惠、配送和外部 RAG 等工具获取事实。
5. 为主播生成准确、自然、多语言、符合当地市场政策的候选回复。
6. 通过独立 Judge Node 做事实、安全、政策和语言质量校验。
7. 最终由主播一键采用、编辑或忽略建议，而不是让 Agent 自动发送高风险回复。
8. 记录完整 Trace，并通过离线 Golden Dataset、Replay 和在线业务指标持续评测。

第一版是 **Human-in-the-loop Host Copilot**，不是无人值守自动客服。主播拥有最终发送权。

---

## 2. 项目定位与学习目标

这个项目不仅要能运行，更要成为一套“项目即教材、代码即面试答案”的 Agent 工程学习项目。

需要延续以下设计理念：

- **Learning by Building**：通过真实开发吃透 Agent 系统，而不是只会调用框架 API。
- **Learning by Teaching**：架构清晰、职责边界明确，适合录制视频和逐模块讲解。
- **Spec Driven Development**：先完成 DEV_SPEC，再拆解 Plan、Tasks、Checklist，最后开发和验收。
- **Code as Living Answer**：每个重要面试知识点都能在真实模块、测试或 Trace 中找到对应实现。
- **Evidence-based Resume**：简历中的指标必须来自压测、Golden Dataset 或 A/B Test，不能虚构线上效果。
- **Interview Ready**：配套基础八股、Agent 八股、项目深挖题、压力追问、参考答案和模拟面试报告。
- **Plug-and-play but Deep**：本地可运行、默认组件完整，同时保留模型、工具、队列、评测器和存储扩展点。

DEV_SPEC 中要说明如何围绕项目建立以下配套交付：

1. `project-learner`：按知识域和知识点逐步学习项目，记录掌握进度。
2. `interview-prep`：支持广度、深挖、源码、压力和随机混合面试风格。
3. `project-review / grill-me`：专门质疑架构合理性、指标真实性和技术堆砌。
4. `resume-writer`：只能使用已经实现并有证据支持的亮点和指标。
5. 分层题库：基础知识、Agent 八股、项目深挖、系统设计和简历防守。

---

## 3. 已确认的系统主链路

DEV_SPEC 必须围绕下面的主链路展开，并清楚区分主链路节点与横切能力：

```text
Audience Message Stream
  -> Input Normalizer
  -> Semantic Filter / Deduplication / Message Clustering
  -> Intent + Business Value + Risk Router
  -> Priority Scheduler / Backpressure / TTL
  -> Dynamic Context Builder + Context Manager
  -> Fast Path | Tool/RAG Path | ReAct Path
  -> Candidate Search for High-business-value Messages
  -> Judge Node
  -> Host Suggestion Queue (HITL)
  -> Host Accept / Edit / Ignore
  -> Feedback + Trace + Replay + Evaluation
```

除了 Audience Message，还应考虑以下实时事件输入：

- Host 语音 ASR 文本
- 当前展示商品和 SKU 切换事件
- 当前直播 Market、Campaign 和 Promotion 状态
- 主播已经回复或讲解过的内容
- 商品库存和优惠变化事件
- 同类问题聚类热度变化

DEV_SPEC 要逐节点说明：

- 输入输出契约
- 职责与非职责
- 是否允许调用模型或工具
- 状态如何保存
- 超时和失败如何处理
- Trace 记录什么
- 单元、集成和 E2E 如何验证

---

## 4. Router 与实时消息流设计

### 4.1 消息流量背景

按峰值同时在线 10,000 人设计。建议在 DEV_SPEC 中使用下面的容量目标，并明确这些是设计/压测目标，不是已经发生的生产结果：

| 指标 | 目标 |
|---|---:|
| 日常平均消息流量 | 10–30 msg/s |
| 持续处理能力 | 100 msg/s |
| 突发处理能力 | 300 msg/s，持续 30 秒 |
| 90 分钟消息总量 | 5万–15万条 |
| 消息接收成功率 | ≥99.99% |

点赞、表情、进入直播间等高频互动事件应与自然语言消息分流，不能全部进入 Agent 主链路。

### 4.2 流量漏斗

不能让每条消息都调用 LLM。需要设计可配置流量漏斗：

```text
100% 规则清洗、语言检测、去重和风险预检
20%–30% 进入语义聚类
5%–10% 进入轻量意图/价值 Router
1%–3% 进入 Tool、RAG 或主力模型生成链路
0.1%–0.5% 进入高价值多候选搜索
```

请把以上比例设计成可观察、可配置的预算，而不是硬编码业务规则。

### 4.3 Router 输出

Router 至少要输出：

- `intent`：支持层级和多标签意图
- `business_value_score`
- `risk_level`
- `route`：drop / aggregate / fast / tool / rag / react / hitl
- `language` 与置信度
- `cluster_id`
- `reason_codes`
- `confidence`

意图 Taxonomy 至少覆盖：

- 闲聊、欢迎、情绪互动
- 商品属性、材质、尺码、搭配咨询
- 实时价格、库存、优惠和购买意图
- 配送、退换货和售后政策
- 投诉、纠纷、隐私和人工升级
- 垃圾信息、广告、攻击内容、Prompt Injection

### 4.4 Business Value 与 Risk 分离

Business Value 和 Risk 必须是两个正交维度。高价值、高风险的问题不能因为风险扣分而被丢弃，而应优先进入严格 Judge 或 HITL。

建议 Business Value 的可解释特征包含：

```text
购买意图 30%
当前商品相关性 20%
商品可售性 15%
同类问题热度 15%
用户互动阶段 10%
回复时效性 10%
```

权重必须可配置，并在 DEV_SPEC 中说明未来如何通过标注集、反馈和在线实验校准。

### 4.5 Priority Scheduler

Priority Scheduler 要支持：

- 优先级队列
- 消息 TTL 与过期丢弃
- 背压和容量保护
- 每分钟 Host 建议预算
- 相似建议合并和替换
- 已回答问题抑制
- 高风险消息转人工优先级
- 公平性与低优先级饥饿保护

主播认知容量是系统最终约束。建议 Host 端只展示 3–6 条建议/分钟，待处理队列最多 3–5 条。

---

## 5. 动态上下文与两层压缩

Context Builder 和 Context Manager 必须拆开设计：

- **Context Builder** 负责决定“本次模型应该看到什么”。
- **Context Manager** 负责决定“上下文放不下时如何控制预算和压缩”。

动态上下文可以包含：

- 当前消息及所属语义聚类
- 当前商品、SKU、销售市场和配送市场
- 最近 Host ASR 与已讲卖点
- 最近已经回复的问题
- 当前促销和 Campaign
- 经过权限过滤的 Tool 结果
- RAG 证据与引用
- 风险、语言和输出约束

### 第一层压缩：大结果外置

- 长 ASR、RAG 原文、大型 Tool 返回、历史消息写入外部存储
- 模型上下文只保留结构化摘要、preview、hash 和 `ref_id`
- 需要时可以按引用重新获取原文

### 第二层压缩：Auto-Compact

- 将早期直播历史压成结构化状态
- 保留最近原文、未解决投诉、已讲卖点、高频意图和风险提示
- 摘要必须可版本化、可追踪、可重建
- 价格、库存、优惠、有效政策等强事实不能被压成长期模型记忆，使用时必须重新查询

DEV_SPEC 要讨论滑动窗口、结构化摘要、事件状态、Token 预算、摘要漂移、恢复和重新压缩的 Trade-off。

---

## 6. Agent 编排与路径选择

系统至少包含三条执行路径：

1. **Fast Path**：闲聊、欢迎语、明确简单问题，使用模板或轻量模型。
2. **Tool/RAG Path**：需要商品、价格、库存、优惠、配送或政策事实的问题。
3. **ReAct Path**：需要多步决策、多个工具、上下文追问或失败恢复的复杂问题。

ReAct Loop 必须具备：

- 明确的状态和 Observation
- Tool 调用前的 Schema 与权限校验
- 最大步骤数、最大 Tool 次数、Token 和总延迟预算
- 重复调用检测
- 停止条件
- 可恢复状态
- 超时、拒绝、降级和人工升级

不是所有消息都要进入 ReAct。DEV_SPEC 必须明确说明为什么固定 Workflow 与动态 Agent Loop 要混合使用。

---

## 7. Tool Calling 与外部 RAG 边界

### 7.1 结构化业务 Tools

第一版至少设计以下只读工具契约：

- `get_product_details`
- `get_live_offer`
- `get_inventory_by_market`
- `get_size_availability`
- `get_shipping_eligibility`
- `get_live_session_context`

价格、库存、优惠资格、配送资格属于动态强事实，必须来自结构化 Tool，不能让 LLM 从历史上下文或 RAG 中猜测。

### 7.2 RAG 作为外部可插拔 Tool

本项目不重新设计和实现 RAG 内部的 Chunking、Embedding、Hybrid Search、Rerank 等能力。现有 RAG 项目是独立、可插拔的知识服务。

Agent 侧只设计稳定的 RAG Tool 契约，例如：

- `search_product_knowledge`
- `search_return_policy`

调用参数至少包含：

- query
- sales_market
- delivery_market
- language
- policy_type
- effective_at
- product_id / sku（可选）
- top_k

返回至少包含：

- answer evidence / passages
- citations
- market
- language
- policy version
- effective period
- confidence
- source reference

Agent 负责“什么时候调用、如何使用证据、如何验证和如何降级”，不负责 RAG 内部检索实现。

### 7.3 Tool Gateway

所有工具调用必须经过 Tool Gateway，模型不能自我授权。Gateway 负责：

- Tool Allowlist 与能力注册
- 参数 Schema 校验
- Market 与权限 Scope 校验
- 数据最小化和脱敏
- Timeout、有限重试和 Circuit Breaker
- Idempotency 与调用去重
- Observation 标准化
- 错误码映射
- 审计和 Trace

真实 Zalando 内部 API 不属于开源项目范围。项目应提供 Mock/Fake Adapter 和稳定接口，不能编造公司内部系统名称、数据或实现细节。

---

## 8. EU 20+ 市场与多语言设计

必须把以下三个维度分开：

- `sales_market`：直播所属销售站点，决定商品目录、价格和促销。
- `delivery_market`：用户收货国家，决定配送和退换货资格。
- `locale`：决定回复表达语言，不能用于推断政策市场。

示例：德国销售站直播中，一个法国配送用户使用英语提问，商品价格可能来自 DE sales market，配送和退换货适用 FR delivery market，最终回答语言为 EN。

系统架构支持 EU 20+ locale。第一阶段完整构建和评测以下五种语言：

- English
- German
- French
- Italian
- Dutch

多语言设计必须覆盖：

- Language Detection 与置信度
- Code-switching
- 用户语言回复 + Host 偏好语言翻译
- 品牌名、SKU、优惠码和法规名称保真
- 多语言 Router 与 Judge
- 各语言独立评测切片
- 当地语言政策缺失时的英文源回退和翻译标记
- 翻译不能改变数字、价格、政策条件和引用

不要把“调用翻译模型”当作完整多语言设计。

---

## 9. 高价值候选搜索与 Judge Node

对于高 Business Value 且延迟预算允许的问题，生成三种策略候选：

1. `factual`：事实直接、简洁准确。
2. `conversion`：在不夸大和不操纵的前提下，自然引导商品点击或购买。
3. `engagement`：更适合主播口播和直播互动。

严格术语上，这种一次分支、统一评分和剪枝的方案更接近 **ToT-inspired shallow candidate search / constrained Best-of-N**，而不是递归展开完整 Tree of Thought。DEV_SPEC 必须诚实说明这个 Trade-off，避免面试中夸大。

建议仅在 `business_value_score >= threshold`、风险允许且剩余延迟预算充足时触发。需要配置全局和每分钟调用上限。

### Judge Node

Judge 必须位于生成 Loop 外，分层执行：

1. **Deterministic Validator**：价格、库存、优惠、SKU、市场、政策版本、引用和禁用词。
2. **Safety Validator**：隐私、Prompt Injection、歧视、过度承诺、售后和法律风险。
3. **Quality Judge**：相关性、简洁度、语言自然度、Host 可读性和转化价值。

Judge 不通过时返回结构化 `reason_codes`。最多重写一次；再次失败后必须走安全模板、保守回答或 HITL，禁止无限重写。

DEV_SPEC 要讨论 LLM-as-a-Judge 的位置偏差、长度偏差、同模型偏差、规则校验优先级和人工校准方案。

---

## 10. 五层安全与权限体系

必须设计以下五层安全权限：

### 第 1 层：输入风险层

- 垃圾信息、广告、攻击内容、隐私、Prompt Injection 检测
- 规则与轻量语义分类结合
- 输入本身永远是不可信数据

### 第 2 层：上下文与数据权限层

- 数据最小化、字段 Allowlist、PII 脱敏
- Market、直播间和用户作用域隔离
- 成本价、毛利、供应商备注和用户敏感信息不得进入模型上下文

### 第 3 层：工具权限层

- 模型只提出 Tool Intent，不拥有授权能力
- 第一版只读工具优先
- 未来发券、退款、补偿等写操作必须单独审批、幂等和审计

### 第 4 层：输出校验层

- 强事实一致性
- 市场政策一致性
- 禁止过度承诺
- 多语言语义一致性

### 第 5 层：HITL 与审计回放层

- 主播最终确认
- 投诉、退款、隐私、政策灰区转人工
- 保存可脱敏回放的决策证据

同时考虑 GDPR 场景下的数据最小化、保留期限、删除、审计和测试数据匿名化。不要在没有法律依据时声称系统已经“完全合规”。

---

## 11. 优雅降级与可靠性

降级不是故障发生后的临时补丁，而是预先设计的能力层级：

```text
ReAct + Multi-tool + Judge
  -> RAG/Tool Prefetch + Single Generation
  -> Structured Tool + Template
  -> Fixed Safe Template
  -> HITL / No Answer
```

需要覆盖：

- 主力模型失败切轻量模型或模板
- RAG 无结果时不允许自由编造
- 价格、库存、优惠 Tool 超时时使用保守话术，不输出旧事实
- Judge 不通过时有限重写
- Router 不可用时规则路由
- 队列过载时丢弃过期低价值消息，保护高价值和高风险消息
- Trace 存储不可用时不阻塞核心建议链路
- 系统重启后的状态恢复与幂等消费

请给出 Retry、Backoff、Jitter、Timeout、Circuit Breaker、Bulkhead、Idempotency 和 Dead-letter Queue 的适用边界与 Trade-off。

---

## 12. 可观测性与 Trace

每条进入有效处理链路的消息都要有 `trace_id`，关键 Span 至少包含：

- normalize
- language_detection
- semantic_filter
- dedup / clustering
- router
- priority_queue
- context_build
- context_compact
- model_inference
- tool_gateway / individual tool
- candidate_generation
- deterministic_judge
- llm_judge
- host_action
- feedback

Trace 需要记录：

- 输入输出摘要与脱敏引用
- intent、value、risk、route 和 reason_codes
- 模型、Prompt、Policy 和配置版本
- Tool 参数摘要、结果状态和引用
- Token、成本、P50/P95/P99 延迟
- 重试、降级和错误
- Host 采用、编辑或忽略行为

使用结构化 JSON Lines 和轻量本地持久化作为默认方案，同时预留 OpenTelemetry 或远程 Trace Backend Adapter。Dashboard 应支持：

- 系统总览
- 实时消息漏斗
- Router 混淆和流量分布
- 单次 Agent Trace 瀑布图
- Tool 与降级分析
- 多语言/多市场质量切片
- Golden Dataset 和回归结果
- Host 采纳与编辑反馈

必须说明 Trace 采样、PII 脱敏、存储成本和回放可重复性的取舍。

---

## 13. Agent 评测体系

建立离线、回放、集成和在线四层评测闭环。

### 13.1 Router 与流量评测

| 指标 | 验收目标 |
|---|---:|
| Router Macro-F1 | ≥0.90 |
| 每种 MVP 语言 Macro-F1 | ≥0.85 |
| 高购买意图 Recall | ≥0.95 |
| 高风险消息 Recall | ≥0.98 |
| 错误 Market 识别率 | <0.1% |

不能只使用总体 Accuracy，因为闲聊和噪声类别占比会掩盖关键意图漏召回。

### 13.2 Tool 与外部知识评测

| 指标 | 验收目标 |
|---|---:|
| Tool Selection Accuracy | ≥95% |
| Tool 参数正确率 | ≥98% |
| Tool 调用成功率 | ≥99.5% |
| Policy Evidence Recall@5 | ≥90% |
| 引用正确率 | ≥98% |
| Golden Dataset 中错误国家/过期政策召回 | 0 |
| Golden Dataset 中价格、库存、优惠幻觉 | 0 |

RAG 评测只验证 Agent 调用契约、过滤参数和证据消费，不重新评测 RAG 内部算法。

### 13.3 生成、Judge 与安全评测

| 指标 | 验收目标 |
|---|---:|
| 首次生成 Judge 通过率 | ≥85% |
| 一次重写后通过率 | ≥95% |
| 严重不安全建议率 | <0.1% |
| 价格/优惠错误率 | 测试集为 0 |
| 错误政策承诺率 | <0.1% |
| 多语言语义一致性 | ≥90% |

### 13.4 延迟与容量评测

| 链路 | P95 目标 |
|---|---:|
| 过滤、去重、聚类 | <50ms |
| Router | <200ms |
| Tool + Template Fast Path | <800ms |
| RAG + Single Generation | <1.5s |
| ReAct + Judge | <2.5s |
| Three-candidate Search + Judge | <4s |

低价值消息排队超过 10 秒后应过期。性能测试必须同时报告硬件、并发、数据规模、模型配置、P50/P95/P99、错误率和降级率。

### 13.5 Host 与业务指标

以下是目标或实验假设，不是当前真实结果：

| 指标 | 建议目标 |
|---|---:|
| 全部有效问题回复率 | 从不足 10% 提升到 25%–35% |
| 高价值消息回复率 | 60%–75% |
| 建议采纳率 | 首版 ≥40%，成熟后 ≥60% |
| 主播编辑率 | <30% |
| 平均人工编辑时间 | <5 秒 |
| 消息到实际回复时间 | 中位数 <8 秒 |
| 重复问题聚合覆盖率 | ≥80% |

商品点击率、加购率和转化率必须通过 A/B Test 或严格实验口径验证。DEV_SPEC 要设计从 `suggestion_id` 到展示、采用、发送、点击、加购和转化的归因链路，但不得提前声称转化已经提升。

### 13.6 Golden Dataset

Golden Dataset 必须覆盖：

- 多语言和 Code-switching
- EU 不同 sales/delivery market 组合
- 强购买意图和隐式购买意图
- 商品、价格、库存、促销和尺码问题
- 退换货和卫生例外等高风险政策问题
- 投诉、隐私、Prompt Injection 和越权 Tool 请求
- Tool 超时、RAG 无结果、模型失败和 Judge 失败
- 重复消息、消息风暴、过期和乱序事件

需要说明人工标注、双人复核、标签一致性、坏 Case 回流、版本管理和防止测试集污染。

---

## 14. 测试方案要求

采用 TDD 和测试金字塔：

### 单元测试

重点测试：

- Normalizer、语言检测和 Schema
- 去重、聚类和热度计算
- Business Value 与 Risk 规则
- Priority、TTL、背压和预算
- Context 选择和两层压缩
- Tool Gateway 权限、重试、熔断和脱敏
- ReAct 停止条件和循环检测
- Deterministic Judge
- 多市场解析
- 指标计算和 Trace 序列化

外部模型、业务 API 和 RAG 一律使用 Fake/Mock，确保单元测试快速且确定。

### 集成测试

至少覆盖：

- Message -> Router -> Scheduler
- Router -> Context -> Tool/RAG
- ReAct -> Tool Gateway -> Observation
- Candidate Search -> Judge -> Rewrite/Fallback
- sales_market / delivery_market / locale 冲突
- Trace -> Replay -> Evaluation
- Host Accept/Edit/Ignore Feedback

### E2E 测试

至少设计以下完整场景：

1. 简单价格问题走 Fast Tool Path。
2. 高购买意图问题生成三策略候选并由 Judge 选优。
3. 德国销售市场、法国配送用户、英语提问泳衣退货政策。
4. Tool 超时后输出保守模板，不编造价格。
5. Prompt Injection 无法改变 Tool 权限和系统规则。
6. 300 msg/s 突发下高价值消息仍能在预算内到达 Host Queue。
7. 多语言回复保持数字、SKU、优惠码和引用一致。
8. 系统重启后消息不重复生成建议。

### 测试工程要求

- 使用 `pytest`
- 支持参数化、Fixture、Fake Clock 和确定性随机种子
- 核心业务逻辑单元测试覆盖率 ≥85%
- 关键集成和 E2E 场景 100% 覆盖
- LLM 输出使用结构化契约、Snapshot/Rubric 和容差断言，不使用脆弱的完整字符串相等
- CI 中区分快速单测、集成测试、Golden Eval 和压力测试

---

## 15. 本地优先与技术约束

- 编程语言：Python 3.11+
- 测试：pytest
- 默认本地可运行，不依赖 Zalando 内部系统
- 默认使用 Fake Product、Inventory、Promotion、Policy 和 RAG Adapter
- SQLite 或本地文件用于开发态持久化
- JSON Lines 用于默认 Trace 存储
- Agent、LLM Provider、Tool、Queue、Memory、Judge、Evaluator 和 Trace Backend 必须可插拔
- 配置驱动，使用 `settings.yaml` 或等价配置文件
- 本地模式可以使用内存队列，架构上预留 Redis Streams/Kafka 等生产 Adapter
- 不强制绑定某个 Agent 框架；如果选择 LangGraph 或类似框架，必须说明它解决了什么问题，以及不用框架的替代实现
- 不使用真实公司私有代码、接口、密钥或数据
- 所有 Demo 数据必须匿名化或合成

DEV_SPEC 的技术选型部分应分别给出：

1. 默认本地实现。
2. 可替换生产实现。
3. 选择理由。
4. 未选择方案及 Trade-off。

---

## 16. DEV_SPEC 文档结构要求

请严格按下面结构组织最终 DEV_SPEC：

## 1. 项目概述

- 业务背景与痛点
- 项目目标与非目标
- 设计理念
- 用户角色和核心场景
- 已知事实、设计假设和待验证指标的区分
- 学习、面试和简历定位

## 2. 核心特点

- 高并发消息流量漏斗
- 意图、价值和风险三维 Router
- 动态上下文与两层压缩
- Fast/Tool/RAG/ReAct 混合编排
- EU 多市场、多语言
- 五层权限与 HITL
- 高价值候选搜索与 Judge
- 全链路 Trace、Replay 和评测闭环
- 可插拔、本地优先架构

## 3. 技术选型与核心系统设计

至少包含：

### 3.1 Event Ingestion 与 Message Normalization
### 3.2 Semantic Filter、Dedup 与 Clustering
### 3.3 Intent / Value / Risk Router
### 3.4 Priority Scheduler、TTL 与 Backpressure
### 3.5 Dynamic Context Builder
### 3.6 Context Manager 与两层压缩
### 3.7 Agent Orchestrator 与 ReAct Loop
### 3.8 Tool Registry 与 Tool Gateway
### 3.9 外部 RAG Tool 契约
### 3.10 EU Market Resolution 与多语言
### 3.11 Candidate Search 与 Judge Node
### 3.12 五层安全权限与 HITL
### 3.13 Retry、Fallback 与故障恢复
### 3.14 Trace、Replay 与 Dashboard
### 3.15 Golden Dataset 与 Agent Evaluation
### 3.16 Host Suggestion API / Console

每节都要包含：目标、输入输出、关键流程、边界、异常、指标、替代方案、Trade-off 和验收方式。

## 4. 测试方案

- TDD 理念
- 测试金字塔
- 单元、契约、集成、E2E、Golden Eval、Replay、压力和安全测试
- 多语言、多市场测试矩阵
- Fake/Mock 策略
- 测试数据和隐私
- CI 分层
- 覆盖率和质量门禁

## 5. 系统架构与模块设计

- 完整 ASCII 架构图
- 主链路与横切能力图
- 状态机图
- 目录结构树
- 模块职责与依赖方向
- 核心领域对象和事件 Schema
- Message Flow、Fast Flow、ReAct Flow、HITL Flow、Replay Flow
- 配置文件完整示例
- 数据存储、生命周期和删除策略
- 扩展点与 Adapter 设计
- 需求追踪矩阵

## 6. 项目排期

按约一小时一个可验收增量拆解，建议至少包含以下阶段：

- 阶段 A：工程骨架、配置和测试基座
- 阶段 B：事件模型、消息清洗、去重和聚类
- 阶段 C：Router、价值评分、风险分类和调度器
- 阶段 D：动态上下文、状态管理和两层压缩
- 阶段 E：Tool Gateway、外部 RAG 契约和 ReAct
- 阶段 F：EU Market、多语言和翻译一致性
- 阶段 G：候选搜索、Judge、五层权限和 HITL
- 阶段 H：Trace、Replay、Golden Dataset 和评测
- 阶段 I：Host Console、性能、可靠性和故障恢复
- 阶段 J：E2E、文档、Demo 和发布验收
- 阶段 K：project-learner、题库、模拟面试和 resume-writer

要求：

- 总任务数约 70–90 个
- 每个任务有任务编号、目的、依赖、修改/新增文件、行为要求、验收标准和测试方法
- 包含阶段进度表、总体进度表和里程碑
- 初始状态全部为未开始，不得伪造已完成任务和测试数量
- 明确主闭环优先级，先做能跑通的垂直切片，再扩展复杂能力

## 7. 可扩展性与未来展望

- 自动回复的安全灰度
- Redis/Kafka 等生产消息基础设施
- 多直播间和多租户
- 写操作 Tool：发券、补偿、退款等审批工作流
- 更丰富的用户反馈和长期学习
- 更严格的因果评估
- 跨模态直播理解
- 多 Agent 是否必要及其 Trade-off
- 云端部署、容量和成本治理
- 从项目代码自动生成学习材料与题库

---

## 17. 必须明确写出的 Trade-off

DEV_SPEC 至少要深入讨论以下取舍：

1. 纯规则 vs 轻量分类器 vs 主力 LLM Router。
2. 所有消息进入 LLM vs 分层流量漏斗。
3. 固定 Workflow vs 动态 ReAct Loop。
4. Tool Prefetch vs ReAct 按需调用。
5. 单候选 vs 三候选搜索。
6. 完整 ToT vs 浅层 Best-of-N。
7. 同模型自检 vs 独立 Judge。
8. LLM Judge vs 确定性规则。
9. 长上下文直接堆叠 vs 结构化状态与两层压缩。
10. 最新强事实实时查询 vs 缓存。
11. 回复更多消息 vs 控制主播认知负担。
12. 高价值 Recall vs 无效建议 Precision。
13. 多语言统一模型 vs 分语言策略和评测。
14. 本地内存队列 vs Redis/Kafka。
15. 全量 Trace vs 采样、成本和隐私。
16. 自动发送 vs HITL。
17. 单 Agent vs Multi-Agent。
18. 真实业务复杂度 vs 开源项目可复现性。

每个 Trade-off 都要给出当前选择、原因、代价、适用边界和未来切换条件。

---

## 18. 简历与指标真实性要求

DEV_SPEC 必须把指标分成三类：

1. **已知业务事实**：例如单场约 10,000 观众、人工消息回复率不足 10%。
2. **设计/验收目标**：例如 100 msg/s、Router Recall、P95 延迟。
3. **实际实验结果**：只有代码完成并运行压测、Golden Eval 或 A/B Test 后才能填写。

禁止：

- 把目标值写成已经达到的结果
- 虚构线上请求量、准确率或转化提升
- 虚构 Zalando 内部 API、团队人数或部署情况
- 把三候选生成夸大成完整递归 ToT
- 把 RAG 外部调用包装成自己重新实现 RAG 全链路

文档中要预留“验收证据”和“简历可用指标”字段。只有任务完成并存在命令输出、评测报告或实验数据时，才能更新。

---

## 19. 最终输出质量要求

生成 DEV_SPEC 前请自检：

1. 主链路中的每个节点是否都有明确职责和非职责。
2. 每条功能需求是否有对应验收标准。
3. 每项非功能指标是否说明测量环境和统计口径。
4. RAG 是否始终保持外部可插拔 Tool 边界。
5. 是否区分 sales_market、delivery_market 和 locale。
6. 是否完整覆盖两层压缩、五层权限、ReAct、候选搜索、Judge、Trace 和评测。
7. 是否包含失败、降级、恢复、过期、乱序和背压。
8. 是否覆盖多语言、多市场和安全测试矩阵。
9. 是否把学习、题库、模拟面试和简历工具纳入正式交付。
10. 是否存在技术术语堆砌、无理由选型或不真实指标。
11. 是否有完整架构图、目录树、配置示例、任务排期和需求追踪矩阵。
12. 文档篇幅和细节是否足以独立指导后续 Plan、Tasks、Checklist 和开发。

最终请直接输出完整 `DEV_SPEC.md` 内容，不要只给目录、提纲或摘要。
