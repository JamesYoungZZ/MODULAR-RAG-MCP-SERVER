# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-07-14 18:01:11  
**面试官风格**：MIX（随机混搭型）  
**掷骰结果**：6  
**评分**：4.0/10

---

## 一、面试记录

> ✅ 答对核心要点 | ⚠️ 方向正确但细节缺失 | ❌ 未能答出或方向错误

### 方向 1：项目综述

#### Q1

**问题（原文）**：如果要把这个系统部署给多个团队使用，也就是支持多租户，现有架构需要做哪些改动？

**候选人回答（原文）**：单机存储要改变，向量数据库也要扩展成分布式的，

**评估**：⚠️ 识别到了单机存储与扩展性问题，但多租户不等同于单纯分布式化。回答遗漏租户身份与鉴权、collection/索引隔离、配置与密钥隔离、配额和限流、Trace 与评估数据隔离等关键设计。

**参考答案**：[→ 查看](#a-多租户)

### 方向 2：项目深挖

#### Q2

**问题（原文）**：你认为这套系统目前最大的技术风险是什么？你会如何缓解这个风险？

**候选人回答（原文）**：瓶颈在LLM吧，还是分布式的问题，如果输入过多，负载过大，需要负载均衡，分流

**评估**：⚠️ 能意识到 LLM 延迟、负载和横向扩展风险，但没有区分摄取与查询链路，也没有给出超时、限流、缓存、队列、重试、熔断或降级等完整措施。

**露馅**：否。方向合理，但项目级细节不足。

**参考答案**：[→ 查看](#a-llm风险)

#### Q3

**问题（原文）**：你刚才提到“瓶颈在 LLM”和“需要负载均衡、分流”。具体说说：在这套系统里，哪些 LLM 调用位于在线查询链路，哪些位于离线摄取链路？你会分别采用什么限流、缓存和降级策略？

**候选人回答（原文）**：在线查询部分，query被embedding模型转成向量，sparse阶段，也被LLM提取关键词。

rerank阶段，如果开启了LLM rerank，也是瓶颈。

做分流，只对high business的做LLM rereanker，其他的做crossencoder rerank，提取关键词用jieba

**评估**：⚠️ 能指出 Query Embedding、可选 LLM Rerank，并提出按业务等级分流以及使用 Cross-Encoder/Jieba 降低成本，具有一定工程意识。但 Embedding 模型不应笼统归为 LLM；本项目 Sparse Route 的核心是 BM25，并未要求由 LLM 提取关键词。回答也完全遗漏离线 Transform 中的 ChunkRefiner、MetadataEnricher、ImageCaptioner，以及题目要求的限流、缓存与故障降级策略。

**露馅**：是。对 Ingestion 中三个 LLM 增强步骤不熟悉。**严重性：中**。

**参考答案**：[→ 查看](#a-llm链路)

### 方向 3：技术深挖

#### Q4

**问题（原文）**：Dashboard 里的 Query Trace 能看到哪些信息？Dense 和 Sparse 两路召回结果是怎么对比展示的？

**候选人回答（原文）**：query trace能看到从query->ingestion-> 存数据库->在线检索-> 融合-> reranker到response builder的每一步输入输出，两路召回要做融合

**评估**：❌ 混淆了 Ingestion Trace 与 Query Trace。在线 Query Trace 不经过摄取和存数据库；回答也没有说明 Dense/Sparse 候选、分数/排名、融合结果及 Rerank 前后排名变化如何展示。

**参考答案**：[→ 查看](#a-可观测性)

#### Q5

**问题（原文）**：你确定 Query Trace 会经过 `ingestion` 和“存数据库”吗？这两步通常属于摄取链路，而不是在线查询链路。

请重新梳理一次：一次在线查询的 Trace 究竟包含哪些阶段？每个阶段至少会记录什么数据？不要只说“输入输出”，请给出具体字段或指标。

**候选人回答（原文）**：query噢，用户query会在dense阶段被转成embedding，去vector database检索，还会被提取关键字，在sparse阶段去BM25 检索，接着融合，reranker

**评估**：⚠️ 纠正后基本说出了 DenseRecall、SparseRecall、Fusion、Rerank 主链路，但仍漏掉 QueryProcess，且没有按要求给出阶段耗时、候选数量、分数分布、Provider/Method、Rerank 前后排名等具体 Trace 数据。

**参考答案**：[→ 查看](#a-可观测性)

#### Q6

**问题（原文）**：`chunk_id` 是怎么生成的？为什么不用 UUID？如果源文件只修改了一行，哪些 chunk 的 ID 会发生变化？

**候选人回答（原文）**：不知道

**评估**：❌ 未能回答项目幂等 Upsert 的核心实现。

**参考答案**：[→ 查看](#a-幂等性)

#### Q7

**问题（原文）**：你说不知道，那我们换一种方式推导。

如果系统重复摄取同一份文件，而 `chunk_id` 每次都随机生成，会出现什么问题？为了让 Upsert 具备幂等性，你认为 `chunk_id` 至少应该由哪些稳定字段计算出来？请给出一个具体方案。

**候选人回答（原文）**：sha256根据chunk内容生成，一般是64kb。还可以加上模型版本号

**评估**：⚠️ 推导出了内容 SHA256 确定性哈希，可避免随机 ID 导致重复写入，方向正确。但“64kb”与本项目实现无关；仅用内容可能让相同文本片段发生 ID 冲突。项目方案还包含 `source_path` 与 `section_path`，模型版本也不是当前 `chunk_id` 的组成部分。

**参考答案**：[→ 查看](#a-幂等性)

---

## 二、参考答案

### <a id="a-多租户"></a>Q：系统如何改造成多租户架构？

**参考答案**：

1. 在 MCP/API 入口引入租户身份、鉴权和权限控制，每个请求携带可信的 `tenant_id`。
2. Chroma collection、BM25 索引、图片索引、摄取历史和 Trace 均按租户隔离；可选择逻辑 namespace 或物理库隔离。
3. 配置、模型密钥、文档生命周期和评估数据按租户管理，所有查询与删除操作强制带租户过滤条件。
4. 增加租户级配额、并发限制、任务队列、限流和成本统计，避免 noisy neighbor。
5. 多实例部署时，将本地文件和 SQLite/pickle 状态迁移到共享或分布式存储；向量库也应选择支持持久化、多副本和水平扩展的后端。

分布式向量库是扩展手段之一，但租户隔离和权限边界才是多租户改造的核心。

### <a id="a-llm风险"></a>Q：系统最大的技术风险及缓解方式是什么？

**参考答案**：

LLM/模型服务常见风险包括高延迟、超时、限额、成本、结果不稳定和第三方服务故障。离线摄取链路适合用任务队列、批处理、并发控制、内容哈希缓存、有限重试和断点续跑；在线查询链路应设置超时、并发上限、缓存、熔断和可观测性。Reranker 失败时回退到 RRF 排名，必要时从 LLM Rerank 降级为 Cross-Encoder 或 None。分布式扩展还需同时处理状态共享、存储一致性和租户隔离。

### <a id="a-llm链路"></a>Q：在线与离线链路分别有哪些模型调用？

**参考答案**：

- **离线 Ingestion**：Transform 阶段包含 ChunkRefiner、MetadataEnricher、ImageCaptioner 三类 LLM/Vision LLM 调用；Embed 阶段调用 Dense Embedding 模型。
- **在线 Query**：Dense Route 调用 Query Embedding；Sparse Route 使用 BM25 关键词检索；精排可配置为 None、Cross-Encoder 或 LLM Rerank。
- **降级**：LLM Rerank 或 Cross-Encoder 失败/超时时回退到 RRF 排名；摄取增强失败应记录阶段错误并支持重试或跳过可选增强。
- **治理**：离线任务用队列、批处理、内容哈希缓存与并发控制；在线任务使用短超时、限流、熔断、结果缓存和业务优先级调度。

### <a id="a-可观测性"></a>Q：Query Trace 如何实现和展示？

**参考答案**：

Query Trace 的五个阶段是：`QueryProcess → DenseRecall → SparseRecall → Fusion → Rerank`。系统采用显式 `TraceContext` 调用，将结构化 Trace 写入 JSON Lines。各阶段应记录耗时、候选数量、分数分布，以及 `method`、`provider` 等字段。Dashboard 对比展示 Dense/Sparse 两路召回的候选、分数和排名，并展示 RRF 融合结果与 Rerank 前后的排名变化。Ingestion 的 `Load → Split → Transform → Embed → Upsert` 是另一条独立 Trace，不属于在线 Query Trace。

### <a id="a-幂等性"></a>Q：chunk_id 如何生成，为什么不用 UUID？

**参考答案**：

`chunk_id = hash(source_path + section_path + content_hash)`。

这是确定性哈希：相同来源、位置和内容会产生相同 ID，因此相同 Chunk 重复 Upsert 不会产生重复记录。UUID 每次随机生成，重复摄取会得到新 ID，并在向量库中累积重复 Chunk。源文件修改一行后，重新切分可能改变该行所在 Chunk 的内容哈希；如果切分边界发生偏移，后续受影响 Chunk 的内容与 ID 也可能变化，不能武断地认为只有一个 Chunk 变化。文件级还通过 SHA256 和 `ingestion_history.db` 避免未变更文件被重复处理。

---

## 三、项目经历真实性点评

本场未提供简历，因此以下判断仅针对候选人声称熟悉该项目的程度，不评价真实履历。

### 能自圆其说的部分 ✅

- **检索主链路**：Q3、Q5 能说明 Dense 向量召回、BM25 Sparse 召回、融合与 Rerank 的基本顺序。
- **成本分级思路**：Q3 提出高业务价值请求使用 LLM Reranker，其他请求使用 Cross-Encoder，并以 Jieba 支持关键词处理，具有实际工程取舍意识。
- **幂等方向**：Q7 在提示后能推导出用 Chunk 内容的 SHA256 形成稳定 ID，理解了确定性标识的大方向。

### 暴露出的掌握缺口 ❌

- **多租户设计停留在分布式存储**：Q1 未覆盖租户鉴权、数据隔离、配额和配置隔离。**严重性：中**。
- **离线 LLM 链路缺失**：Q3 没有提到 ChunkRefiner、MetadataEnricher、ImageCaptioner。**严重性：中**。
- **Trace 双链路混淆**：Q4 把 Ingestion 和数据库写入放进 Query Trace，经质疑后仍无法说明具体 Trace 字段。**严重性：高**。
- **幂等实现不熟悉**：Q6 直接回答“不知道”，Q7 仍未说出 `source_path + section_path + content_hash`。**严重性：高**。

### 改进建议

- 熟记两条 Trace：Ingestion 五阶段与 Query 五阶段，并能解释每阶段记录的耗时、数量、分数和排名变化。
- 理清模型调用边界：Embedding、Cross-Encoder、LLM Rerank 与摄取阶段三个 LLM Transform 的角色不同。
- 掌握 `chunk_id` 的完整构成、UUID 的缺陷，以及修改内容对切分边界和后续 Chunk 的影响。
- 回答系统设计题时先列“身份与隔离、状态与一致性、容量与可用性、成本与观测”四个维度，再展开具体技术方案。

---

## 四、综合评价

**优势**：

- 能描述 Hybrid Search 的基本流程，并知道 Dense、BM25、Fusion、Reranker 的顺序。
- 对服务高负载和模型成本有直觉，提出了业务分级和替代组件的方案。
- 在提示后可以从重复写入问题推导确定性哈希方案。

**薄弱点**：

- 项目架构掌握偏表面，容易把离线摄取、在线查询和存储写入混为一条链路。
- 对可观测性与幂等性这两个代码级设计缺乏准确记忆。
- 回答通常只有结论，较少解释机制、边界、故障场景和取舍；面对要求具体字段的问题仍停留在组件名称。

**面试官建议**：

优先画出项目的三张图并反复口述：Ingestion 数据流、Query 检索流、四路持久化关系。随后针对每个模块准备“输入、输出、核心算法、失败降级、代码位置”五项答案。下一轮练习应选择 CODE 风格，重点训练 TraceContext、chunk_id、DocumentManager 和 Factory 的实现细节。

---

## 五、评分

| 维度 | 分数（满分 10） | 评分依据 |
|---|---:|---|
| 项目架构掌握 | 4.5 | 能说出 Dense、Sparse、Fusion、Rerank，但混淆 Ingestion 与 Query Trace；多租户设计只覆盖存储扩展。 |
| 简历真实性 | 4.5 | 未提供简历，按项目熟悉度评估；主链路可描述，但核心实现经追问出现明显缺口。 |
| 算法理论深度 | 3.5 | 知道 Embedding、BM25、Cross-Encoder/LLM Rerank 的用途，但未解释融合、模型差异或算法机制。 |
| 实现细节掌握 | 3.0 | 不知道项目 `chunk_id` 生成方式，Trace 字段和离线 LLM 组件也未答出。 |
| 表达清晰度 | 4.5 | 回答简短直接，但结构和因果链不完整，多个问题未覆盖题目要求的全部部分。 |
| **综合** | **4.0** | 能描述表面概念，但关键实现追问暴露明显缺口，符合 3–4 分档上沿。 |

---

## 六、本场实际考察题目

1. 多租户改造范围与分布式存储
2. 系统最大技术风险与缓解策略
3. 在线/离线模型调用、限流、缓存与降级
4. Dashboard Query Trace 与双路召回展示
5. Query Trace 阶段与具体观测字段
6. `chunk_id` 的生成、UUID 与局部修改影响
7. 从幂等 Upsert 反推稳定 ID 设计
