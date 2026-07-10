# Livestream Host Copilot - Project Knowledge v0.1

## 1. 项目定位

面向 EU 20+ 市场直播电商场景的多语言 Host Copilot。系统从高并发观众消息中识别意图、业务价值与风险，为主播生成有事实依据、符合当地市场政策且可快速采用的回复建议。

业务背景：单场直播约 10,000 名观众，主播需要持续讲解商品，无法同时阅读和回复大量聊天消息，人工回复率不足 10%。查看屏幕、组织语言和打字还会打断直播节奏。

第一版采用 Human-in-the-loop：Agent 只生成建议，主播拥有最终编辑和发送权。价格、库存、优惠等强事实来自结构化 Tool；商品知识与退换货政策通过外部可插拔 RAG Tool 获取。本项目不重复实现 RAG 内部链路。

## 2. 系统主链路

```text
Audience Message Stream
  -> Input Normalizer
  -> Semantic Filter / Dedup / Cluster
  -> Intent & Value Router
  -> Priority Scheduler
  -> Dynamic Context Builder + Context Manager
  -> Fast Path | RAG/Tool Path | ReAct Path
  -> Candidate Search for High-value Messages
  -> Judge Node
  -> Host Suggestion Queue (HITL)
  -> Feedback / Trace / Evaluation
```

### 节点职责

| 节点 | 核心职责 | 不负责什么 |
|---|---|---|
| Input Normalizer | 清洗、语言识别、事件标准化 | 不做复杂意图判断 |
| Semantic Filter | 噪声过滤、重复合并、语义聚类 | 不生成最终回答 |
| Router | 意图、价值、风险、处理路径分类 | 不执行工具、不组装全部上下文 |
| Priority Scheduler | 背压、过期、优先级和每分钟建议预算 | 不改变业务事实 |
| Context Builder | 按任务动态选择消息、市场、商品和证据 | 不自行创造事实 |
| Context Manager | Token 预算、两层压缩、引用管理 | 不用摘要替代实时价格库存 |
| ReAct Loop | 对复杂问题按需调用工具并根据结果继续决策 | 不自我授权工具 |
| Tool Gateway | Schema 校验、权限、超时、重试、熔断、脱敏 | 不负责自然语言润色 |
| Candidate Search | 为高价值消息生成事实型、转化型、互动型候选 | 不对所有消息执行昂贵搜索 |
| Judge Node | 事实、安全、语言和质量验收 | 不与生成模型共享模糊的自检职责 |
| Host Queue | 展示、编辑、采用、忽略和来源解释 | 第一版不自动发送高风险消息 |

## 3. 三条执行路径

1. Fast Path：闲聊、欢迎语、明确的简单事实问题，使用模板或轻量模型。
2. Tool/RAG Path：价格、库存、商品信息、退换货政策等需要外部事实的问题。
3. ReAct Path：信息不足、需要多个工具、存在上下文依赖的复杂问题。

高业务价值且延迟预算允许时，系统执行受 ToT 启发的浅层候选搜索。工程上它更接近带策略约束的 Best-of-N，而不是递归展开完整思维树。

## 4. RAG 边界

- RAG 作为外部可插拔 Tool，Agent 只依赖稳定的输入输出契约。
- 商品价格、库存、优惠资格、配送资格必须查询结构化 Tool。
- 商品说明、材质、尺码知识和政策解释可以查询 RAG。
- Policy RAG 调用必须携带 `market`、`language`、`effective_at`、`policy_type`。
- Agent 负责决定何时检索、如何使用证据和如何降级，不负责 Chunking、Embedding、Rerank 等内部实现。

## 5. 多市场与多语言

- `sales_market` 决定商品目录、价格与促销。
- `delivery_market` 决定配送和退换货资格。
- `locale` 只决定表达语言，不能用语言推断政策市场。
- 观众回复使用观众语言；Host UI 同时展示主播偏好语言翻译。
- 首版完整评测 EN/DE/FR/IT/NL，架构支持扩展到 20+ locale。

## 6. 五层安全与权限

1. 输入层：垃圾信息、Prompt Injection、隐私和攻击内容检测。
2. 上下文层：最小化、脱敏、市场隔离，不暴露成本价、用户隐私等字段。
3. 工具层：Allowlist、Schema 校验、市场权限、超时、重试和熔断。
4. 输出层：价格、库存、优惠、政策引用、过度承诺和语言质量校验。
5. HITL 与审计层：主播最终确认；高风险问题转人工；全流程可回放。

## 7. 两层上下文压缩

第一层是结果外置：长 ASR、RAG 原文和大工具结果保存到外部存储，上下文只保留结构化摘要、preview 和 `ref_id`。

第二层是会话压缩：早期直播历史压成结构化状态，保留最近原文、未解决问题和已讲卖点。价格、库存、优惠等强事实不进入长期摘要，使用时重新查询。

## 8. 项目亮点

1. 高并发消息不直接打入 LLM，通过过滤、聚类、价值路由和优先级调度形成流量漏斗。
2. 将 `sales_market`、`delivery_market`、`locale` 分离，解决 EU 多市场政策和多语言混淆。
3. Tool、RAG、ReAct 和模板按事实依赖、风险与延迟动态选路。
4. Context Builder 与 Context Manager 分离，实现可控的动态上下文和两层压缩。
5. 五层安全权限将模型推理与系统授权解耦。
6. 高价值消息使用三策略候选搜索，Judge 在 Loop 外独立验收。
7. 全链路 Trace、Golden Dataset、离线回放与在线 A/B 形成评测闭环。
8. 以主播认知容量为约束，每分钟只输出 3-6 条高价值建议，而不是追求生成数量。

## 9. 核心难点

1. 实时性与推理深度冲突：完整 ReAct 与候选搜索质量更高，但直播消息会快速过期。
2. Recall 与主播负担冲突：高价值消息不能漏，但建议过多会造成新的注意力负担。
3. 多语言与多市场解耦：语言、销售市场和配送市场可能完全不同。
4. 动态事实与生成质量冲突：表达可以由模型优化，但价格、库存和政策不能由模型记忆。
5. Judge 独立性：同一模型自检容易确认自己的错误，需要规则和独立评分标准。
6. 效果归因：回复率提升不等于转化提升，必须设计曝光、采用、点击、加购和转化实验口径。

## 10. 做过的系统优化设计

- 流量优化：规则过滤、语义去重、消息聚类、优先级队列、TTL 和背压。
- 延迟优化：Fast Path、RAG Prefetch、并行只读 Tool、模型分级和预算控制。
- 成本优化：仅 5%-10% 消息进入 Router，1%-3% 进入 Tool/RAG，极少数进入候选搜索。
- 上下文优化：按需装配、结果外置、结构化 Auto-Compact、强事实按需刷新。
- 可靠性优化：Timeout、有限重试、Circuit Breaker、Fallback Template、HITL。
- 质量优化：结构化输出、候选策略约束、规则 Judge、LLM Judge、离线回放。
- 多语言优化：语言检测、双语 Host 展示、按语言切片评测、术语和 SKU 保真。

## 11. 知识地图

### 基础知识

事件驱动架构、消息队列、生产者消费者、优先级队列、背压、TTL、幂等性、限流、重试、指数退避、熔断、缓存、并发、异步 I/O、P50/P95/P99、结构化日志、Trace、状态机、接口契约、Schema 校验、单元/集成/E2E 测试。

### Agent 八股

LLM 无状态性、Prompt 与结构化输出、Function Calling、Tool Calling、ReAct、CoT、ToT、Best-of-N、Model Routing、Context Engineering、短期/长期记忆、上下文压缩、Agent Loop、停止条件、HITL、Guardrail、Prompt Injection、LLM-as-a-Judge、Golden Dataset、离线评测、在线评测、幻觉与 Grounding。

### 项目深挖

意图 taxonomy、Business Value Score、流量漏斗、消息聚类、动态上下文、两层压缩、Tool Gateway、五层权限、EU Market Resolution、多语言一致性、三策略候选搜索、Judge 重写与降级、全链路 Trace、Replay、指标归因和系统 Trade-off。

## 12. 面试介绍

### 30 秒版本

> 我在 Zalando 直播 Host 端设计了一套面向 EU 多市场的多语言 Host Copilot。单场直播约有一万名观众，主播人工回复率不足 10%。系统通过消息去重聚类、意图与业务价值路由，从高并发弹幕中筛出高价值问题；实时价格库存通过 Tool 获取，商品和政策知识通过可插拔 RAG 获取；复杂问题进入 ReAct，并由独立 Judge 做事实与安全校验，最终给主播生成可编辑的一键回复建议。系统通过 Trace、Golden Dataset 和在线指标评估回复效率、建议采纳率与转化影响。

### 证据边界

- 已知业务事实：单场约 10,000 观众、人工回复率不足 10%。
- 设计/验收目标：吞吐、P95、Router Recall、RAG/Tool 准确率等。
- 只有实际压测或 A/B Test 得到的数据，才能写成简历结果。
