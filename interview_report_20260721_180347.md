# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-07-21 18:03:47 CST  
**面试官风格**：DEEP（深挖发散型）  
**掷骰结果**：2  
**评分**：5.4/10

---

## 一、面试记录

> ✅ 答对核心要点 | ⚠️ 方向正确但细节缺失 | ❌ 未能答出或方向错误  
> 以下问题和回答均按面试原文记录，未作摘要或美化。

### 方向 1：项目综述

| 题号 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 参考答案 |
|---|---|---|---|---|
| Q1 | 这个系统里 MCP 协议起什么作用？为什么不直接暴露 REST API？ | mcp是为了给方便agent用，如果用rest api的话，client层需要做单独的适配，鉴权，参数 schema什么的，mcp只需要是标准协议，通过mcp sdk的tools/list和tools/call, 方便agent使用 | ✅ | [→ 查看](#a-mcp协议) |
| Q2 | 一个 MCP Client 从发现 `query_knowledge_hub`，到真正调用它并拿到检索结果，完整交互链路是什么？底层消息格式和传输方式分别是什么？ | ok让我来捋一下全链路<br><br>client发现方法，调用走stdio到mcp端，JSON/RPC，用的是MCP SDK官方的。然后rag端MCP层，protocalhandler加载配置，进行输入校验，然后去找对应方法的handler，那么在实现层的handler，用户的query先进入query processer，按链路进行关键词处理，然后把原query传给denseretriver，关键词列表传给sparseREtriver，分别做语义召回和BM25召回，接着做RRF融合，得出一个归一化的分数，接着按配置是否开启reranker，是LLM还是cross encoder reranker，做精排，最后经过response builder返回markdown或者带多模态的回答 | ⚠️ | [→ 查看](#a-mcp调用链路) |
| Q3 | 这里的“归一化”具体发生在哪里？RRF 如何处理 Dense 相似度和 BM25 分数量纲不同的问题？请写出融合公式，并说明同一个文档只出现在一路召回结果中时怎么计分。 | 发生在RRF融合的时候。这个公式是 积分（1/r+rank（chunk）） | ❌ | [→ 查看](#a-rrf公式) |

### 方向 2：项目经历深挖（无简历模式）

| 题号 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 露馅 | 参考答案 |
|---|---|---|---|---|---|
| Q4 | 在这个项目的 Ingestion Pipeline 中，你认为哪个阶段最容易出现 Bug？为什么？请结合一个你实际遇到或能够具体推演的故障场景，说明它的表现、定位方法和解决方案。 | 好，我先说下ingestion的全链路吧<br><br>pdf -> loader 变成markdown，进行chunking，三阶段增强，生成向量/生成sparse postings，存储<br><br>在我理解，pdf质量不好的情况下，或者，pdf质量可以但是段落被分页的情况下，出bug比较多，也就是脏数据的情况。<br><br>那么我们就遇到了，并且出促成了我们架构的演进<br>首先我们为什么选择recursive chunking策略就是因为转化成markdown后，先按结构化的顺序拆分，这样可以清清除些符号。然后我们的增强阶段，第一阶段做text清洗，开始是按规则，后面做了LLM轻量模型做清洗。处于成本和延迟的考虑并没有做全量LLM清洗，而是对有脏数据大于20%才开 | ⚠️ | 否 | [→ 查看](#a-ingestion故障分析) |
| Q5 | 这 20% 的脏数据比例是如何计算的？请说明检测单位、脏数据判定规则，以及 Pipeline 在规则清洗与 LLM 清洗之间的分流逻辑。如果 LLM 清洗超时或把有效内容误删了，系统如何发现并降级？ | 是通过规则计算的，有库可以计算有效字符和文档长度的比较。<br><br>LLM清洗的时候，会附上清洗前的原文chunk一起往后走，确保原文也还在， | ❌ | 是 | [→ 查看](#a-清洗分流与降级) |
| Q6 | 原文 Chunk 和清洗后 Chunk 在数据模型中具体如何关联？最终参与 Dense Embedding、BM25 建索引和生成回答的分别是哪一份？如果两份都入库，如何避免重复召回；如果只索引清洗版，原文保留在哪里、什么时候使用？ | 这个我不知道，算是给自己挖坑了 | ❌ | 是 | [→ 查看](#a-原文与清洗版本) |

### 方向 3：技术深挖

| 题号 | 问题（原文） | 候选人回答（原文，不摘要） | 评估 | 参考答案 |
|---|---|---|---|---|
| Q7 | Reranker 的精排候选集设置多大比较合适？如果候选集的 K 开得过大，会带来哪些具体问题？你会依据什么数据来确定这个 K？ | 根据我们的调研，用户一般只看3-5个，所以最终输出是5个，那么reranker的输出就是10个，<br><br>那么reranker的输入应该是10个。k过大的话，成本和延迟都会上升，再往前推，dense，sparse检索的topk也会变大，这样存储也会上升。<br><br>k一般先有个初始值，然后调参来判断效果，会看那三个指标 | ⚠️ | [→ 查看](#a-reranker候选集) |
| Q8 | 请给出各阶段明确的 Top-K，例如 Dense 召回多少、Sparse 召回多少、RRF 融合后保留多少、Reranker 输入和最终输出多少。为什么用户只看 3–5 个结果，不能直接推出 Reranker 只需要输入 10 个？另外，你说的“三个指标”具体是哪三个？ | dense20个，sparse20个，fusion通过去重大概输入有30+个，输出20个，然后做rerank，20个取前5 | ⚠️ | [→ 查看](#a-topk漏斗) |
| Q9 | 这个项目的可插拔架构是怎么实现的？假设现在要新增一个 Embedding Provider，请具体说明需要新增或修改哪些文件、实现什么接口，以及配置如何驱动运行时选择该 Provider。 | 可插拔是通过base类，factory，registry，还有privoders实现的。<br><br>新增一个embedding和新增一个LLM还不太一样，embedding模型换，向量维度很可能会变，需要重新建vector databse | ⚠️ | [→ 查看](#a-可插拔架构) |

### 实际考察题目

1. MCP 相比 REST API 的价值
2. MCP Tool 发现、调用及完整检索链路
3. RRF 公式、异构分数处理和单路命中计分
4. Ingestion Pipeline 脏数据故障分析
5. 规则清洗与 LLM 清洗的分流、校验和降级
6. 原文 Chunk 与清洗后 Chunk 的版本关系
7. Reranker 候选集 K 的选择
8. Dense、Sparse、Fusion、Rerank 的 Top-K 漏斗
9. 可插拔架构及新增 Embedding Provider

---

## 二、逐题纠错

### Q1：MCP 的作用及与 REST API 的区别

**你答对的部分**：

- MCP 面向 Agent/AI Client，能够减少不同 Client 针对每个服务分别适配的成本。
- `tools/list` 用于发现工具，`tools/call` 用于调用工具，工具参数有标准 Schema。

**不准确或缺失的部分**：

- 你把“鉴权”也列为 MCP 相比 REST 自动解决的问题，这不准确。MCP 标准化的是能力发现和调用方式，并不意味着不需要鉴权；使用远程传输时仍要设计认证和授权。Stdio 场景通常依赖本机进程边界，所以看起来没有单独的网络鉴权。
- REST 也可以借助 OpenAPI 描述参数 Schema，因此差异不只是“REST 没有 Schema”，而是 MCP 为 Agent 原生规定了 Tools、Resources、Prompts 等语义和交互方式。
- 没有提到本项目选择 Stdio 的具体收益与局限：零端口、零网络依赖，适合本地私有知识库；但不适合远程访问和多 Client 并发。

**更准确的回答方式**：先说明 MCP 标准化 Agent 的能力发现与调用，再说明本项目使用 Stdio 的部署收益，最后承认 REST 在远程服务、多租户、网关治理方面可能更合适。

### Q2：MCP Client 到 RAG 结果的完整链路

**你答对的部分**：

- 说出了 Stdio、JSON-RPC、Handler 分派、参数校验以及 Dense/Sparse → RRF → Rerank → Response Builder 的主链路。
- 能区分原 Query 用于 Dense 语义召回、关键词用于 Sparse/BM25 召回，整体表达有系统视角。

**不准确或缺失的部分**：

- “JSON/RPC”应为 **JSON-RPC 2.0**。
- 完整协议链路还缺少初始化握手，以及 `tools/list` 返回工具名称、描述和输入 Schema 后，Client 再发送 `tools/call` 的过程。
- “RRF 得出一个归一化的分数”是错误表述。RRF 不归一化 Dense 和 BM25 的原始分数，而是直接丢弃原始分数，只融合每一路的排名。
- “Response Builder 返回 Markdown 或带多模态的回答”表述略混。检索 Tool 返回的是检索内容、Citation 以及可选的 `ImageContent`；是否进一步生成最终自然语言答案，取决于 Client/Agent 的后续处理。
- `protocalhandler`、Query Processor 的具体行为属于源码级陈述，但回答中没有给出文件或类名，因此只能确认架构方向，不能确认你确实掌握实际实现。

**更准确的回答方式**：按“初始化 → 工具发现 → Tool 调用 → 参数校验/分派 → Query Pipeline → MCP Content 返回”六步展开，并区分协议层、业务 Handler 和检索实现层。

### Q3：RRF 公式与异构分数处理

**明确错误**：

- 你回答的“积分（1/r+rank（chunk））”不是 RRF 公式；这里没有积分运算。
- 分母应是 `k + rank`，不是 `1/r + rank`。
- 多路结果需要分别计算后求和，你没有表示 Dense 与 Sparse 两路的累加。
- 没有回答单路命中时如何计分，也没有解释为什么不需要归一化原始分数。

**正确公式**：

$$Score_{RRF}(d)=\sum_{r\in R_d}\frac{1}{k+rank_r(d)}$$

双路检索时，即 Dense 排名贡献加 Sparse 排名贡献。若文档只出现在一路，另一路贡献为 0。`k` 通常取 60，是抑制头部排名差异的平滑因子。

**这是本场最严重的知识缺口之一**：RRF 是项目 Hybrid Search 的核心，真实面试中写错公式会明显降低面试官对项目真实性的判断。

### Q4：Ingestion 中最容易出 Bug 的阶段

**你答对的部分**：

- 基本说出了 PDF → Markdown → Chunking → Transform → Dense/Sparse → Storage 的摄取链路。
- 识别出低质量 PDF、跨页断句和脏数据是常见问题，这个方向合理。
- 能从成本和延迟角度考虑规则处理与 LLM 处理的组合，具备工程意识。

**不准确或缺失的部分**：

- `RecursiveCharacterTextSplitter` 的主要作用是按分隔符优先级切分并尽量保留结构，不是“清除符号”。PDF 噪声的清除应由解析/清洗或 ChunkRefiner 负责。
- 本项目知识库中的 Transform 三步是 ChunkRefiner、MetadataEnricher、ImageCaptioner；你把第一步概括成“Text 清洗”，遗漏了 ChunkRefiner 合并语义断裂段落这一核心职责。
- “脏数据大于 20% 才开启 LLM”是很具体的实现陈述，但没有说明检测公式、代码位置、阈值实验或回归数据，因此目前更像临时补充的包装，不能视为已经证明的真实设计。
- 问题要求说明“表现、定位方法和解决方案”，你的回答主要描述方案演进，没有给出 Trace/日志证据、复现样本、修复前后指标或回归测试。

**更好的案例结构**：给出一个具体 PDF 样本 → 展示 Markdown/Chunk 异常 → 用阶段 Trace 定位是在 Load 还是 Split 引入 → 描述修复 → 用 Hit Rate、重复率或人工标注集证明修复有效。

### Q5：20% 脏数据阈值与降级

**你答对的部分**：

- 知道可以通过有效字符占比构造启发式规则。
- 意识到保留清洗前原文有利于审计和回退。

**不准确或缺失的部分**：

- “有库可以计算”无法证明实现。需要说出使用的库/函数、检测单位以及计算公式。
- “有效字符 / 文档长度”仍然不够明确：中文、英文、数字、空白、Markdown 符号分别是否算有效字符？按整个文档计算还是按 Chunk 计算？
- 没有说明 20% 阈值怎么得到。合理做法应是在标注样本上评估误报、漏报、成本和延迟后选择阈值。
- 携带原文并不等于能够发现 LLM 误删。仍需长度变化率、关键实体保留、差异检查、抽样评估或质量模型。
- 没有回答 LLM 超时后的重试、熔断和回退策略。

**结论**：方向有合理性，但当前回答没有形成可实现、可测试的完整方案。

### Q6：原文 Chunk 与清洗后 Chunk 的关系

**你的回答**：“这个我不知道，算是给自己挖坑了。”

这道题没有技术作答，因此判定为 ❌。不过，直接承认不知道比继续编造数据模型更好。

你之前声称“原文 Chunk 会一起往后走”，就必须能够回答：

- 两个版本是否共享稳定 Chunk ID，还是父子 ID？
- Dense 和 BM25 索引哪一版？
- 两版都索引时如何合并同源结果，避免重复召回？
- 原文保存在哪个字段或存储中？
- Citation、生成上下文和失败回退分别使用哪一版？

如果项目实际上没有双版本设计，就不应该在前一题临时引入这一方案。面试中可以改为：“目前实现只保留 Refined Content；生产化时我会增加 Raw Content 和 Transform Version 用于审计与回退。”

### Q7：Reranker 候选集大小

**你答对的部分**：

- K 过大会增加精排延迟和计算/API 成本，这一点正确。
- 知道 K 应通过调参和指标验证，而不是完全凭经验固定。

**明确问题**：

- 回答先说“Reranker 输出 10 个”，紧接着又说“Reranker 输入应该是 10 个”，输入与输出混淆。
- 用户最终只看 3–5 个结果，只能决定最终输出 K，不能推出 Reranker 输入 K。精排输入需要更大，才能从粗排候选中把真正相关的结果提升到前 5。
- 你说 Dense/Sparse Top-K 增大会导致“存储上升”，通常不正确。索引已提前持久化，查询时扩大 Top-K 主要增加检索、传输、融合和精排计算，不会增加持久化索引空间。
- “会看那三个指标”却没有说出指标名称，使这句话无法验证。至少应明确候选 Recall/Hit Rate、精排后 MRR/NDCG、P95/P99 延迟和成本。

### Q8：各阶段 Top-K 漏斗

**你答对的部分**：

- 第二次回答把漏斗说清了：Dense Top-20、Sparse Top-20、去重后约 30+、RRF 保留 20、Rerank 后取 5。这是一套合理的初始配置。

**仍然遗漏的部分**：

- 没有回答为什么展示 5 条时，Reranker 仍需要输入 20 条：核心原因是保证候选召回余量，让精排纠正粗排顺序。
- 没有补充上一题所说的“三个指标”。
- “去重大概 30+”取决于两路结果重叠度。极端情况下可能接近 20，也可能达到 40；需要说明这是观测值而非固定规则。
- 没有说明如何选择这些数值。标准做法是扫描不同 K，比较 Hit Rate/MRR、延迟和成本曲线，选择满足质量约束的最小 K。

### Q9：可插拔架构与新增 Embedding Provider

**你答对的部分**：

- Base 类、Factory、Provider 实现和注册映射是可插拔架构的核心。
- 指出 Embedding 模型切换可能改变向量维度，旧 Collection 不兼容，需要重新 Embedding 或新建 Collection，这是很有价值的工程补充。

**不准确或缺失的部分**：

- 没有按问题要求列出具体文件：`src/libs/embedding/your_provider.py`、`src/libs/embedding/factory.py`、`config/settings.yaml`。
- 没有说明继承 `BaseEmbedding` 后需要实现如 `embed_texts()` 等接口。
- 没有解释 Factory 如何根据 YAML 中的 `embedding.provider` 选择实现。
- 你提到了 `registry`，但项目知识库描述的是 Factory 中的 `provider_map`。如果源码确实另有 Registry，需要给出代码位置；否则不要额外加入未经确认的组件。
- “重新建 vector database”表述太宽泛。通常是新建兼容维度的 Collection/索引并重新生成向量，不一定需要更换或整体重建数据库系统。

**完整回答应该分两层**：先答新增 Provider 的三处代码改动，再补充模型维度、距离度量、重建索引和迁移期间双读/切换等运行风险。

---

## 三、参考答案

### <a id="a-mcp协议"></a>MCP 的作用及其与 REST API 的区别

MCP 基于 JSON-RPC 2.0，为 AI Client 与工具或数据源之间定义标准的能力发现和调用接口。Client 可通过 `tools/list` 获取工具及其输入 Schema，再通过 `tools/call` 发起调用。相比普通 REST API，MCP Client 不必为每个服务重新约定工具发现、参数 Schema、内容类型与 Agent 集成方式。

本项目使用 Stdio Transport：Client 以子进程启动 Server，通过 stdin/stdout 交换协议消息，日志必须写入 stderr。需要远程调用、多客户端并发、统一网关鉴权时，HTTP 类传输通常更合适；MCP 并不天然消除鉴权需求，而是标准化 Agent 与能力提供方的交互。

### <a id="a-mcp调用链路"></a>MCP Tool 完整调用链路

1. Client 建立 Stdio 会话并完成 MCP 初始化。
2. Client 调用 `tools/list`，Server 返回 `query_knowledge_hub` 的名称、描述和输入 Schema。
3. Client 使用 `tools/call` 提交 `query`、可选 `top_k` 和 `collection`；底层消息采用 JSON-RPC 2.0。
4. Server 校验参数并分派到 Tool Handler。
5. Query Pipeline 执行 QueryProcess → DenseRecall 与 SparseRecall → RRF Fusion → 可选 Rerank。
6. Response Builder 组装内容、Citation 及可选 `ImageContent`，再通过 MCP 响应返回 Client。

### <a id="a-rrf公式"></a>RRF 融合

$$Score_{RRF}(d)=\sum_{r\in R_d}\frac{1}{k+rank_r(d)}$$

在本项目的双路检索中，可写为：

$$Score_{RRF}(d)=\frac{1}{k+Rank_{Dense}(d)}+\frac{1}{k+Rank_{Sparse}(d)}$$

RRF 不直接归一化 Dense 相似度或 BM25 分数，而是丢弃绝对分数，只使用每一路的排名，因此天然规避量纲差异。`k` 是平滑因子，通常取 60。若文档只出现在一路结果中，只累加该路的 `1/(k+rank)`；未出现的一路贡献为 0。

### <a id="a-ingestion故障分析"></a>Ingestion 故障分析

完整链路为 Load → Split → Transform → Embed → Upsert。低质量 PDF、跨页断句、页眉页脚和乱码通常首先在 Load 阶段引入，并在 Split 阶段被放大。定位时应保留阶段产物和 Trace，对比原 PDF、canonical Markdown、初始 Chunk、Refined Chunk，并统计字符异常率、空 Chunk 比例、重复率和语义断裂样本。

项目中的 ChunkRefiner 用于合并逻辑相关但被物理切断的段落并去噪；它不是简单依赖 `RecursiveCharacterTextSplitter` 清除符号。回答真实故障案例时，应说明输入样本、可观测现象、定位证据、修复前后指标和回归测试。

### <a id="a-清洗分流与降级"></a>清洗分流、质量校验与降级

如果设计“异常比例超过 20% 才调用 LLM”的策略，必须先把口径定义清楚：检测单位是文档还是 Chunk；分母是字符数、token 数还是行数；异常字符、重复页眉、断词、乱码分别如何判定。阈值应由标注集上的 Precision/Recall、成本和延迟共同确定，不能只说“有库可以算”。

LLM 清洗应设置超时、重试和熔断；失败时回退到规则清洗或原始 Chunk。清洗前后还应做长度比、关键实体保留率、哈希/差异检查及抽样评估。仅仅携带原文并不能自动发现误删，也没有说明最终哪一版被索引。

### <a id="a-原文与清洗版本"></a>原文与清洗后 Chunk 的版本关系

一种清晰设计是保留稳定的逻辑 Chunk ID，并记录 `raw_content`、`refined_content`、`transform_version` 和父子/来源关系。Dense 与 BM25 应基于同一个明确的 canonical 检索文本建索引，避免两份内容作为独立 Chunk 重复召回；原文作为审计、回退和重新处理依据保存。生成阶段使用命中的 canonical 内容，并可在质量异常时回退原文。

如果确实要双版本入库，必须引入版本字段、同源去重和结果折叠策略，并明确 Citation 指向哪一版。

### <a id="a-reranker候选集"></a>Reranker 候选集大小

Cross-Encoder 必须对每个 `(Query, Chunk)` 实时推理，候选集越大，延迟和计算成本近似线性增加；LLM Rerank 还会增加 token 成本，并可能触及上下文长度。常见起点是 10–30 条，但最终值应通过离线评估和线上延迟预算确定。

调参时至少观察候选集 Recall/Hit Rate、精排后的 MRR 或 NDCG、P50/P95/P99 延迟和成本。最终展示 5 条只决定输出 K，不等于 Reranker 输入只需 5 或 10 条；Reranker 需要更大的候选池，才能在粗排顺序不理想时把相关文档提升到前 5。

### <a id="a-topk漏斗"></a>Top-K 漏斗

一个可用的初始配置可以是 Dense Top-20、Sparse Top-20，去重融合后保留 RRF Top-20，Reranker 对这 20 条精排并输出 Top-5。该配置不是固定答案，应画出 `K → Hit Rate/MRR/延迟/成本` 曲线后选择拐点。

Dense 与 Sparse 的 Top-K 增大主要增加检索计算、融合候选数量以及 Reranker 成本，不会自然推导出持久化存储空间增加，因为索引通常已经建好。回答时还应明确所谓“三个指标”的名称和定义。

### <a id="a-可插拔架构"></a>新增 Embedding Provider

项目通过 Base 抽象类、Factory 和 YAML 配置驱动组件实例化。新增 Provider 的核心步骤是：

1. 新建 `src/libs/embedding/your_provider.py`，继承 `BaseEmbedding` 并实现 `embed_texts()` 等接口。
2. 修改 `src/libs/embedding/factory.py`，在 `provider_map` 中注册 Provider 名称与实现类的映射。
3. 修改 `config/settings.yaml` 中的 `embedding.provider` 及相关参数。

Embedding Provider 切换还要校验向量维度和距离度量是否与现有 Collection 兼容。维度改变时，旧向量无法直接复用，需要新建或迁移 Collection，并重新 Embedding；这是很好的工程补充，但不能替代上述接口、注册和配置步骤。

---

## 四、简历包装点评

> 本场未提供简历，以下只针对面试中主动陈述的项目经历判断，不对简历真实性作最终结论。

### 包装合理 ✅

- **“MCP 方便 Agent 使用标准协议”**：能说出 `tools/list`、`tools/call`、Stdio 和 JSON-RPC，说明对协议定位及基本交互有实际认知。
- **“Dense 20、Sparse 20、Fusion Top-20、Rerank 后取 5”**：被追问后能够给出一致的候选漏斗，架构主干基本成立。
- **“Embedding 模型变化可能导致向量维度变化，需要重建 Vector Database”**：这是有效的迁移风险意识，超出了只背 Base/Factory 的表面回答。

### 露馅点 ❌

- **“RRF 融合后得出一个归一化的分数”** → 无法写出正确公式，遗漏平滑因子 `k`、两路排名求和以及单路命中的计分方式。**严重性：高**（RRF 是 Hybrid Search 的核心算法）。
- **“脏数据大于 20% 才开启 LLM 清洗”** → 无法给出具体库、异常字符定义、检测单位、阈值来源或可复现逻辑。**严重性：高**（过于具体的指标如果没有测量口径，很容易被判断为包装）。
- **“清洗前原文 Chunk 一起往后走”** → 无法解释原文和清洗版本的数据模型、索引策略及去重方式，并明确承认不知道。**严重性：高**（方案没有闭环）。
- **“可插拔由 Base、Factory、Registry、Providers 实现”** → 没有答出具体文件、接口方法和 YAML 配置步骤。**严重性：中**（知道模式名称，但代码级落点不足）。

### 改进建议

- 熟练写出 RRF 公式，解释 `k=60`、排名融合为何不需要归一化，以及单路缺失如何计分。
- 删除或弱化无法复现的“20%”表述；若保留，补齐检测代码位置、公式、阈值实验和降级策略。
- 为 Raw/Refined Chunk 画出数据模型和状态流，明确哪份进入 Dense、BM25、生成上下文及审计存储。
- 记住新增 Embedding Provider 的三个代码落点，并准备向量维度变化时的迁移方案。

---

## 五、综合评价

**优势**：

- MCP 与 RAG 查询链路的主干较清楚，能从 Tool 调用讲到 Dense/Sparse、RRF、Reranker 和 Response Builder。
- 能识别 PDF 脏数据、跨页语义断裂、精排延迟成本和 Embedding 维度迁移等真实工程问题。
- 在 Q6 直接承认不知道，没有继续编造，这对真实面试是加分的诚信表现。

**薄弱点**：

- 算法精度不足：RRF 的概念、公式和“归一化”含义混淆。
- 具体设计没有闭环：20% 分流阈值、原文保留、清洗质量检测和降级策略无法落到可执行实现。
- 指标表达不完整：提到“三个指标”但没有说出名称，也未建立 Top-K、召回率、排序质量、延迟和成本之间的关系。
- 源码掌握偏浅：可插拔架构能说出模式，但没有回答文件、接口、注册与配置细节。

**面试官建议**：

先补齐四个最可能被追问击穿的闭环：RRF 公式；各阶段 Top-K 与评估指标；Raw/Refined Chunk 数据流；新增 Provider 的具体文件和接口。练习时每个设计都用“输入 → 处理 → 输出 → 存储 → 失败降级 → 评估证据”六步回答，避免只讲概念或临时给出没有口径的数字。

---

## 六、评分

| 维度 | 分数（满分 10） | 评分依据 |
|---|---:|---|
| 项目架构掌握 | 6.5 | 能讲清 MCP 到检索、融合、精排和响应的主链路，也知道 Ingestion 主流程；但部分组件职责和版本数据流没有闭环。 |
| 简历真实性 | 6.0 | 未提供简历；MCP 和 Top-K 描述有一定可信度，也能诚实承认未知，但“20% 阈值”等具体陈述缺少测量与实现证据。 |
| 算法理论深度 | 3.5 | 知道 Dense/Sparse、BM25、Rerank 的作用和成本，但 RRF 核心公式答错，评估指标未能说出。 |
| 实现细节掌握 | 4.5 | 能说出 Stdio、JSON-RPC、Base/Factory 和向量维度迁移风险；未说出 Provider 的文件/接口/配置，也不知道 Raw/Refined Chunk 如何索引。 |
| 表达清晰度 | 6.5 | 能按链路展开，回答自然；部分概念混用、数量关系前后不清，关键追问时缺少结构化证据。 |
| **综合** | **5.4** | **架构层面基本掌握，但算法与实现细节存在 3 处以上明显缺失，符合 5–6 分档。** |
