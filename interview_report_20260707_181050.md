# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-07-07 18:10:50  
**面试官风格**：HARD 压力质疑型  
**掷骰结果**：5  
**评分**：3.0/10

---

## 一、面试记录

> ✅ 答对核心要点 | ⚠️ 方向正确但细节缺失 | ❌ 未能答出或方向错误

### 方向 1：项目综述

| 轮次 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 参考答案 |
|-----|-------------|---------------------------|------|---------|
| Q1 | 你简历里写“采用 DEV_SPEC + Agent Skill 驱动开发流程，覆盖编码、测试、配置、打包等环节，完成 68 个子任务和 1200+ 自动化测试用例”。我先不问 RAG，先问工程真实性：这 1200+ 自动化测试是怎么分层的？Unit、Integration、E2E 分别测什么？你怎么保证这些测试不是 AI 生成出来“看起来很多”，但实际上没覆盖核心行为？ | 这些测试用例都是平时开发中 收集的，包括beta UAT时发现的问题，以及线上随机采样2%构建的 | ⚠️ | [→ 查看](#a-测试体系) |
| Q2 | 你这个回答听起来像“测试样本来源”，但我问的是测试分层和覆盖有效性。你说来自平时开发、Beta UAT、线上 2% 随机采样，那我继续追：线上随机采样 2% 的数据，怎么转成可自动化回归测试？具体讲三点：1. 你采样的是用户 query、检索结果、最终 answer，还是完整 trace？2. 这些样本怎么标注 golden answer / expected chunk？人工标注还是自动生成？3. 如果 LLM 输出本身有随机性，你的自动化测试怎么避免 flaky？ | 完整 trace 自动生成 3. 不知道 | ❌ | [→ 查看](#a-测试体系) |
| Q3 | 你这里已经有一个明显风险了。你说采样的是完整 trace，golden answer / expected chunk 是自动生成，但 LLM 随机性导致 flaky 怎么处理你不知道。那我会质疑：这 1200+ 自动化测试里，真正能稳定证明系统正确性的比例可能并不高。继续追问：如果让你现在补救这个设计，你会怎么把“线上 trace 自动生成测试”改成一个可靠的评估集？请具体说：1. 哪些字段可以直接做确定性断言？2. 哪些字段不能直接断言，只能做指标评估？3. 你会怎么引入人工审核，避免自动生成的 golden answer 把错误答案固化进测试集？ | 不知道 | ❌ | [→ 查看](#a-测试体系) |

### 方向 2：简历深挖

| 轮次 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 露馅 | 参考答案 |
|-----|-------------|---------------------------|------|-----|---------|
| Q4 | 你简历里写：“构建五阶段 Ingestion Pipeline，覆盖 PDF 解析、语义切分、Metadata 增强、图片描述生成、Embedding 与幂等 Upsert”，还写了“多模态文档处理”。我问具体点：Image Caption 是怎么进入检索链路的？不要只说“生成图片描述”。你讲清楚：1. Caption 生成后写到哪里？2. 它是作为 metadata 检索，还是拼进 chunk text 参与 embedding？3. 用户 query 命中这个 chunk 后，原始图片怎么返回给 Agent / MCP Client？ | 写到metadata里，image存盘带的有chunk id，chunk里有image source | ❌ | 是 | [→ 查看](#a-多模态检索) |
| Q5 | 你这个回答只答到一半，而且有个关键点不稳。你说“写到 metadata 里”，但如果 Caption 只在 metadata 里，默认向量检索并不会因为图片描述命中，除非你把 metadata 拼进 embedding 文本，或者检索时专门做 metadata filtering。你还说“image 存盘带 chunk id”，这个也太粗了，真正要讲清楚的是 image_id、chunk metadata、ImageStorage / image_index.db、MCP 返回内容之间的关系。我继续追：如果用户问“那张展示系统架构的图是什么内容？”，系统最后能返回原始图片，你认为中间最少需要哪些字段打通？按链路讲：1. Chunk text / metadata 里要有什么字段？2. ImageStorage 里要有什么索引？3. MCP tool 返回时，是只返回文本 citation，还是会返回图片内容？图片内容以什么形式返回？ | 不知道 | ❌ | 是 | [→ 查看](#a-多模态检索) |
| Q6 | 现在问 Agent 岗最核心的一块：你写了 “基于 MCP 暴露 query_knowledge_hub 等 3 类工具，使 Agent 可通过 Tool Calling 调用私有知识库”。我问你：MCP 和你自己写一个 REST API 给 Agent 调，有什么本质区别？不要只说“标准化”。你讲清楚：1. MCP 里 Tool 是怎么被 Client 发现和调用的？2. 这个项目为什么选 Stdio Transport，而不是 HTTP？3. Stdio 模式下为什么日志不能随便打到 stdout？ | 不知道 | ❌ | 是 | [→ 查看](#a-mcp协议) |

### 方向 3：技术深挖

| 轮次 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 参考答案 |
|-----|-------------|---------------------------|------|---------|
| Q7 | 你简历写：“实现 BM25 + Dense Embedding 混合召回，结合 RRF 融合与 Cross-Encoder / LLM Rerank，将 Hit Rate@10 提升至约 90%+”。先问最基础的：RRF 的公式是什么？为什么这里不用 Dense 分数和 BM25 分数直接加权平均？顺便讲清楚：1. RRF 依赖的是 rank 还是原始 score？2. k=60 这个参数大概起什么作用？3. 如果 Dense 和 BM25 两路结果完全不重叠，RRF 会怎么处理？ | 不知道 | ❌ | [→ 查看](#a-rrf公式) |
| Q8 | 你简历写：“LLM / Embedding / Reranker / VectorStore / Evaluator 可插拔架构，支持 Azure OpenAI、OpenAI、Ollama、DeepSeek 等 4+ Provider 配置切换”。我问你最落地的：如果现在要新增一个 Embedding Provider，比如接入一个公司内部 embedding 服务，你需要改哪些地方？请按代码结构讲：1. 新增哪个类？继承哪个 Base？2. Factory 或注册映射在哪里改？3. settings.yaml 里大概需要配哪些字段？4. 为什么调用方不应该直接 new InternalEmbeddingClient()？ | 新增provider，在factory里 | ⚠️ | [→ 查看](#a-可插拔架构) |
| Q9 | 这个回答太泛了，面试里基本等于没答。“新增 provider，在 factory 里”只是方向，不能证明你真的做过可插拔架构。我要你补具体一点：如果我是代码评审人，我会问：你新增 provider 时，怎么保证它符合系统统一接口？继续讲：1. Embedding Provider 需要实现哪些核心方法？比如是单条 embed，还是 batch embed？2. 你怎么处理不同厂商返回维度不一致的问题？3. 如果内部 embedding 服务超时，调用链怎么降级？是报错中断 ingestion，还是跳过当前 chunk，还是走 fallback provider？ | 不知道 | ❌ | [→ 查看](#a-可插拔架构) |
| Q10 | 最后问一个你简历里最显眼的量化指标：你写 “Hit Rate@10 达到约 90%+，端到端查询延迟控制在 1s 左右”。这两个数字都很容易被质疑。先问 Hit Rate@10：Hit Rate@10 到底怎么算？请你具体讲：1. 一条 query 的 golden answer / expected chunk 是什么？2. Top-10 里怎样算“命中”？按 chunk_id 精确匹配，还是按语义包含？3. 90%+ 是和什么 baseline 对比？纯 Dense、纯 BM25、还是无 Rerank 的 Hybrid？4. 如果 Reranker 把正确 chunk 从第 3 名排到第 11 名，Hit Rate@10 会发生什么？ | 不知道 | ❌ | [→ 查看](#a-hit-rate) |

---

## 二、参考答案

### <a id="a-测试体系"></a>Q: 测试分几层？单元测试怎么 mock LLM？

三层金字塔：

- **Unit（单元测试）**：只测业务逻辑，用 `unittest.mock.patch` 替换 LLM 客户端返回预设响应，避免真实 API 调用。
- **Integration（集成测试）**：验证模块间协作，例如 Ingestion Pipeline、Chroma 存储读写、BM25 索引读写。
- **E2E（端到端测试）**：启动真实 MCP Server 子进程，发送 JSON-RPC 消息验证完整链路。

如果用线上 trace 转自动化测试，可靠做法是：结构字段、状态码、调用阶段、返回数量、chunk_id 是否存在等做确定性断言；LLM answer 文本不做逐字断言，而用 Hit Rate@K、MRR、Faithfulness、Answer Relevancy 等指标评估；核心 golden set 需要人工审核，避免自动生成的错误答案被固化。

---

### <a id="a-多模态检索"></a>Q: 图片的 Caption 如何参与检索？检索命中后图片怎么返回？

1. **摄取**：ImageCaptioner（Vision LLM，如 GPT-4o）为图片生成 Caption，文本缝合进 Chunk 正文，参与 Embedding 向量化。
2. **检索**：用户文字查询时，Caption 文本可以被向量检索命中；BM25 也能索引 Caption 关键词。
3. **返回**：chunk metadata 中保留 `image_refs` / `image_id` 等引用，再从 `image_index.db` 中通过 `image_id → 文件路径` 找到原始图片，Base64 编码后通过 MCP 返回 `ImageContent` 给 Client。

关键点是：仅把 caption 放 metadata 里通常不足以被默认向量检索命中，除非检索文本构造时显式拼入 metadata。

---

### <a id="a-mcp协议"></a>Q: MCP 是什么规范？暴露了哪些 Tool？

MCP（Model Context Protocol）是面向 AI Client 与外部工具/数据源的标准协议，基于 JSON-RPC 2.0。Client 可以通过协议发现 Server 暴露的 tools，并以标准格式调用，不需要为每个 REST API 单独适配。

本项目采用 **Stdio Transport**：Client 以子进程启动 Server，stdin/stdout 通信，零网络依赖，适合本地私有知识库。Stdio 模式下 stdout 必须只输出合法 MCP / JSON-RPC 消息，普通日志应走 stderr，否则会污染协议流，导致 Client 解析失败。

对外暴露 3 个 Tool：

| Tool | 功能 | 关键参数 |
|------|------|---------|
| `query_knowledge_hub` | 主检索入口（Hybrid Search + Rerank） | `query`, `top_k?`, `collection?` |
| `list_collections` | 列举可用文档集合 | 无 |
| `get_document_summary` | 获取文档摘要与元信息 | `doc_id` |

---

### <a id="a-rrf公式"></a>Q: RRF 融合公式是什么？k 值含义？为什么不用线性加权？

`Score_RRF(d) = 1 / (k + Rank_Dense(d)) + 1 / (k + Rank_Sparse(d))`

- RRF 依赖排名 rank，不依赖原始 score。
- `k` 是平滑因子，常用经验值为 60；调大后分数更均匀，调小后头部排名权重更强。
- 不直接线性加权，是因为 BM25 分数和向量相似度量纲不同、范围不同，需要额外归一化和权重调参。RRF 只看排名，更稳健。
- 如果两路完全不重叠，RRF 会把两路候选都纳入融合列表，单路靠前结果仍会得到分数，但不会有“双路共同命中”的加成。

---

### <a id="a-可插拔架构"></a>Q: 新增一个 Embedding Provider 需要改哪些文件？

典型三步：

1. 新建 `src/libs/embedding/your_provider.py`，继承 `BaseEmbedding`，实现统一接口，例如批量 `embed_texts()`。
2. 修改 `src/libs/embedding/factory.py`，在 provider 映射中注册 `"your_provider": YourProviderClass`。
3. 修改 `config/settings.yaml`，配置 `embedding.provider`、模型名、endpoint、api_key、batch_size、timeout 等字段。

调用方不应该直接 `new InternalEmbeddingClient()`，因为这会破坏配置驱动和开闭原则，使 Pipeline 依赖具体厂商实现，后续切换 OpenAI / Azure / Ollama / 内部服务时需要改业务代码。

---

### <a id="a-hit-rate"></a>Q: Hit Rate@K 是怎么计算的？

`HitRate@K = Top-K 结果中至少命中一条 Golden Answer 的查询数 / 总查询数`

对 Golden Test Set 中每条 `(query, expected_chunks)`，取 Top-K 检索结果，至少一条匹配则 hit=1，否则 hit=0。`@10` 表示正确文档或 chunk 出现在 Top-10 内即可，不要求排第一。

如果 Reranker 把正确 chunk 从第 3 名排到第 11 名，对 Hit Rate@10 来说，这条 query 会从命中变为未命中；这说明 Hit Rate@10 对 Top-K 边界敏感，但不衡量第 1 名质量，头部排序质量通常要结合 MRR 看。

---

## 三、简历包装点评

### 包装合理 ✅

- **“通用 RAG 框架 / Agent 知识中枢”这个包装方向本身合理**：相比“电商场景 RAG 系统”，它更贴 Agent 开发工程师岗位，能突出 Tool Calling、MCP、可插拔架构和知识库接入能力。
- **“新增 provider，在 factory 里”**：你能说出可插拔架构的最外层方向，但缺少接口、配置、异常和维度校验细节，只能算弱支撑。

### 露馅点 ❌

- **“1200+ 自动化测试用例”** → 只能说明测试样本来源，不能说明 Unit / Integration / E2E 分层、确定性断言、flaky 控制和 golden set 审核。**严重性：高**。
- **“多模态文档处理 / 图片描述生成”** → 将 caption 只说成写入 metadata，没讲清 caption 进入 embedding 文本、`image_id`、`image_index.db`、Base64 `ImageContent` 返回链路。**严重性：高**。
- **“MCP Tool Calling / Agent 知识中枢”** → MCP 与 REST 的区别、Tool 发现与调用、Stdio Transport、stdout/stderr 分工都答不上来。**严重性：高**，这是 Agent 岗核心。
- **“RRF 融合 / Hybrid Search”** → RRF 公式、rank 与 score 区别、`k=60` 含义、两路不重叠场景都不知道。**严重性：高**。
- **“可插拔架构支持 4+ Provider”** → 只能说“新增 provider，在 factory 里”，无法讲 Base 接口、配置字段、维度一致性、超时和 fallback。**严重性：中高**。
- **“Hit Rate@10 达 90%+”** → 不知道 Hit Rate@10 如何计算、golden answer / expected chunk 如何定义、baseline 如何对比。**严重性：高**。

### 改进建议

- 先把简历里最容易被问穿的强表述降级：`1200+ 自动化测试用例` 不要作为核心卖点，改成“补充了覆盖核心模块的单元、集成和端到端测试”，除非你能讲清分层和稳定性。
- MCP 必须优先补：`tools/list`、`tools/call`、JSON-RPC、Stdio Transport、stdout 只放协议消息、stderr 打日志，这些是 Agent 岗基础。
- RRF 和 Hit Rate@10 必须背熟：公式、k 值、为什么不用加权平均、Hit Rate@K 与 MRR 区别、baseline 怎么设计。
- 多模态链路按字段背：caption 拼入 chunk text、metadata 保留 image refs、`image_index.db` 负责 `image_id → path`、MCP 返回 Base64 图片内容。
- 可插拔架构按“三处修改”背：新增 provider 类、factory 注册、settings 配置；再补接口方法、维度检查、timeout / fallback。

---

## 四、综合评价

**优势**：

- 能接受压力追问并直接承认“不知道”，这比乱编更好。
- 对“可插拔 provider 要在 factory 里注册”有最基础方向感。
- 简历包装方向本身贴 Agent 岗，但当前知识储备支撑不足。

**薄弱点**：

- Agent 核心 MCP 基础缺失，无法解释协议、工具发现、调用方式和 Stdio 约束。
- RAG 检索核心缺失，RRF、Hit Rate@10、baseline、评估集都无法回答。
- 工程化表述过强，但测试分层、golden set、flaky 控制都讲不出来。
- 多模态链路只停留在“图片有 metadata / source”，没有形成可检索、可返回的完整链路。
- 可插拔架构只有概念，没有接口级、配置级、异常策略级细节。

**面试官建议**：

短期不要再扩展简历内容，先把当前简历每一句强表述拆成“定义、代码位置、输入输出、失败场景、评估方式”五类答案。你现在最该补的是 MCP、RRF、Hit Rate@10、Image Caption 检索链路和 Provider 三步接入。补完这些之前，这份简历不适合直接投强 Agent 工程岗，因为核心词一追就断。

---

## 五、评分

| 维度 | 分数（满分 10） | 评分依据 |
|-----|---------------|----------|
| 项目架构掌握 | 3 | 能知道有 provider / factory，但 MCP、多模态、测试链路和检索评估都无法展开。 |
| 简历真实性 | 2.5 | 多个强表述无法支撑，尤其是 MCP、RRF、Hit Rate@10、1200+ 测试。 |
| 算法理论深度 | 2 | RRF 公式、Hit Rate@10 定义都答不上来。 |
| 实现细节掌握 | 2.5 | 不清楚 ImageStorage、MCP 返回、Embedding Provider 接口、异常策略。 |
| 表达清晰度 | 5 | 回答简短诚实，但多数问题只给“不知道”，无法形成完整因果链。 |
| **综合** | **3.0** | 当前只能说明你接触过这些概念，无法支撑“独立设计与开发通用 RAG MCP Server”的简历强度。 |
