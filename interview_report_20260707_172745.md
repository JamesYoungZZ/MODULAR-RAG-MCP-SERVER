# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-07-07 17:27:45  
**面试官风格**：DEEP 深挖发散型  
**掷骰结果**：4  
**评分**：6.5/10

---

## 一、面试记录

> 评估标记：✅ 答对核心要点；⚠️ 方向正确但细节缺失；❌ 未能答出或方向错误。

### 方向 1：项目综述

| 轮次 | 问题（原文） | 候选人回答（原文） | 评估 | 参考答案 |
|-----|-------------|-------------------|------|---------|
| Q1 | 这个系统里有哪几类存储？它们各自负责什么？为什么不能只用一个？ | 三类存储。首先因为我们的架构是混合检索，那么embedding语义相似度，和BM25精确关键词匹配都需要。dense vector要存向量数据库，sparse 要存BM25 index，还有pdf里有时会有图片，那么图片存image storage | ⚠️ | [→ 查看](#a-存储协同) |
| Q2 | 你刚才说 dense vector 存向量数据库、sparse 存 BM25 index、图片存 ImageStorage。那它们之间靠什么字段打通？比如 BM25 召回了一个结果之后，系统怎么找到对应的 chunk 文本、metadata，甚至关联图片？ | 我们有一个归一化的chunk id，三者有统一的chunk id，找到chunk | ⚠️ | [→ 查看](#a-存储协同) |
| Q3 | 在 Ingestion 的 Stage 6 里，为什么要先 `VectorUpserter.upsert(chunks, dense_vectors)` 得到 `vector_ids`，再把这些 `vector_ids` 写回 `sparse_stats` 的 `chunk_id`？这一步从“存储层协同”的角度解决了什么问题？ | 为了保证id一致？sparse能拿到归一化的chnk id | ✅ | [→ 查看](#a-存储协同) |
| Q4 | 那为什么这个统一 ID 不直接沿用 `DocumentChunker` 生成的 `chunk.id`？项目里先有 `chunk.id`，后面 `VectorUpserter` 又重新生成存储 ID，这样设计你觉得有什么利弊？ | 不知道诶 | ❌ | [→ 查看](#a-幂等性) |

### 方向 2：项目经历深挖

| 轮次 | 问题（原文） | 候选人回答（原文） | 评估 | 露馅 | 参考答案 |
|-----|-------------|-------------------|------|-----|---------|
| Q5 | 如果让你从已学习的 D1/D2 范围里挑一个设计做改进，你会选哪个？范围限定在你学过的部分：`IngestionPipeline` 六阶段流程、`DocumentChunker`、Transform 链、Dense/Sparse 编码、Stage 6 存储协同都可以。请说明：1. 你想改哪里；2. 现在这样设计有什么问题或局限；3. 你会怎么改。 | chunking策略，我们为了成本和稳定性做了牺牲，我会选择semantic chunking，这样能实现真正的语义化 | ⚠️ | 否 | [→ 查看](#a-chunking改进) |
| Q6 | 如果把 recursive chunking 换成 semantic chunking，你会怎么落地？具体会新增或改哪些组件？另外，semantic chunking 会带来哪些成本、延迟和可复现性问题？ | 会新增embedding处理句子和段落，然后根据语义相似度做切分，这里会带来embedding模型调用的成本，并且根据厂商模型，参数的不同，效果也不一样，调参比较困难。 | ✅ | 否 | [→ 查看](#a-chunking改进) |
| Q7 | 如果你要说服团队把 semantic chunking 加进项目，你会设计什么评估实验来证明它比 recursive chunking 更好？请限定在 D2 已学范围内回答：你会控制哪些变量、观察哪些 ingestion 产物或统计指标？ | 我会观察chunk产物，看chunk有没有根据语义被切断的失败率，chunk的大小（有效内容占比），最终召回的跨chunk的答案占比， | ⚠️ | 否 | [→ 查看](#a-chunking改进) |

### 方向 3：技术深挖

| 轮次 | 问题（原文） | 候选人回答（原文） | 评估 | 参考答案 |
|-----|-------------|-------------------|------|---------|
| Q8 | Transform 链里现在是 `ChunkRefiner → MetadataEnricher → ImageCaptioner`。你觉得为什么要按这个顺序？如果顺序改成 `MetadataEnricher → ChunkRefiner → ImageCaptioner`，或者先做 `ImageCaptioner`，可能会带来什么问题？ | refiner是先清楚噪声，如果不先做的话，噪声可能会影响后续步骤 | ⚠️ | [→ 查看](#a-transform顺序) |
| Q9 | 如果先做 `ImageCaptioner`，再做 `ChunkRefiner`，可能会发生什么？特别是图片 placeholder、caption 文本、chunk metadata 之间的关系，哪里容易被破坏？ | 图片可能被噪声清除掉？图片这种确定性信息可能会被增强？ | ⚠️ | [→ 查看](#a-transform顺序) |
| Q10 | `MetadataEnricher` 为什么应该放在 `ChunkRefiner` 后面？如果先 enrich metadata，再 refine chunk text，会导致哪些 metadata 和正文不一致的问题？ | summary，tag之类的，可能噪声被清除，但增强后的还在 | ✅ | [→ 查看](#a-transform顺序) |

---

## 二、参考答案

### <a id="a-存储协同"></a>Q: Ingestion Stage 6 的存储协同怎么理解？

本项目摄取阶段至少涉及三类主要存储：

1. **Chroma / VectorStore**：存 dense vector、chunk text、metadata，用于语义向量检索和后续文本回查。
2. **BM25 Index**：存倒排索引、term frequency、doc length、postings，用于关键词精确匹配。它不保存完整 chunk metadata。
3. **ImageStorage / image_index.db**：保存图片文件路径、image_id、collection、doc_hash、page_num 等图片索引信息。

Stage 6 先调用 `VectorUpserter.upsert(chunks, dense_vectors)`，由 `VectorUpserter` 生成最终写入向量库的稳定 `vector_ids`。随后 pipeline 将这些 `vector_ids` 回填到 `sparse_stats["chunk_id"]`，再写入 BM25。这样 BM25 postings 中保存的 `chunk_id` 与 Chroma 中的向量记录 ID 对齐，保证稀疏索引和向量存储能指向同一份 chunk。

图片不是简单靠 chunk_id 直接查，而是通过 chunk metadata 中的 `image_refs` / `images` / `image_captions` 等字段关联到 `image_id`，再由 `ImageStorage` 根据 `image_id` 查文件路径。

---

### <a id="a-幂等性"></a>Q: 为什么不直接沿用 `DocumentChunker` 的 `chunk.id`？

`DocumentChunker` 的 `chunk.id` 是业务层 chunk 对象的标识，格式通常包含 `document.id`、`chunk_index` 和内容 hash。它的主要价值是让分块阶段可追踪、可调试、可复现。

`VectorUpserter` 重新生成存储 ID，通常基于 `source_path`、`chunk_index` 和 `chunk.text` 的 hash，用于向量库幂等 upsert。这样做的好处是：

- 存储层 ID 由最终要写入的文本内容决定，和向量库 upsert 语义绑定更紧。
- 即使上游 chunk 对象 ID 规则变化，存储层仍能保持自己的稳定写入策略。
- 内容变化时 ID 变化，重复摄取相同内容时 ID 不变，避免 UUID 式重复写入。

代价是系统里同时存在“业务 chunk ID”和“存储 chunk ID”，需要明确边界，并在 Stage 6 做 ID 对齐，否则 BM25、Chroma、图片 metadata 之间容易错位。

---

### <a id="a-chunking改进"></a>Q: Recursive chunking 与 semantic chunking 的权衡是什么？

当前 `DocumentChunker` 通过 `SplitterFactory` 使用 recursive splitter，优势是确定性强、成本低、速度快、可复现，适合稳定的 ingestion pipeline。局限是它仍然依赖规则和长度边界，可能把语义连续内容切断。

如果引入 semantic chunking，通常需要新增或扩展 splitter provider，例如：

- 新增 `SemanticSplitter`，对句子或段落先做 embedding。
- 根据相邻句段 embedding 相似度、主题突变点、最大 chunk size 等规则决定切分点。
- 在 `SplitterFactory` 和 `settings.yaml` 中加入新 provider 配置。

代价包括：

- 额外 embedding 调用成本和延迟。
- provider、模型版本、阈值参数变化会影响切分结果。
- 可复现性弱于 deterministic recursive splitter。
- 需要新增评估实验，观察 chunk 语义断裂率、chunk 长度分布、有效内容占比、图片/metadata 保真度等 ingestion 产物质量。

---

### <a id="a-transform顺序"></a>Q: 为什么 Transform 顺序是 `ChunkRefiner → MetadataEnricher → ImageCaptioner`？

`ChunkRefiner` 应该先执行，因为它负责清理 PDF 转换噪声、规整文本、减少语义断裂。如果先做 metadata 或 image caption，再让 refiner 改写正文，会导致增强结果基于旧文本生成，后续正文却已经变了。

`MetadataEnricher` 放在 refiner 后面，是为了让 `title`、`summary`、`tags` 基于清理后的最终文本生成。否则会出现 metadata 仍描述旧噪声、旧标题、旧主题，但 chunk text 已被修改的情况。

`ImageCaptioner` 放在后面，是因为它依赖 chunk text 中的图片 placeholder 和 chunk metadata 中的图片引用。如果先生成 caption，再做 refiner，可能破坏 placeholder、caption 上下文，或让 caption 与原 chunk/image metadata 对应关系错位，最终造成 embedding 文本、metadata、图片引用不一致。

---

## 三、简历包装点评

本场没有提供简历，因此不判断具体简历包装真实性。

### 包装合理

- 你能围绕已学范围说明存储层大类、semantic chunking 的改进动机，以及 Transform 顺序的部分原因。如果简历只写“参与 Ingestion Pipeline 设计与优化”，目前表达可以支撑一部分。

### 露馅点

- **“深入掌握存储层协同 / 幂等 ID 设计”** → Q4 无法解释 `DocumentChunker.chunk.id` 与 `VectorUpserter` 存储 ID 的区别。严重性：中。
- **“深入掌握多模态 Transform 链”** → Q9 对 `ImageCaptioner` 与 placeholder、metadata、caption 对齐关系解释不稳。严重性：中。

### 改进建议

- 把 `DocumentChunker._generate_chunk_id()` 和 `VectorUpserter._generate_chunk_id()` 两套 ID 规则对比背熟，并能讲出为什么 Stage 6 要回填 `vector_ids`。
- 复习 Transform 三步的输入输出：`ChunkRefiner` 改正文，`MetadataEnricher` 改 metadata，`ImageCaptioner` 依赖 image refs 并写 caption 相关字段。
- 回答设计改进题时，用“现状 → 问题 → 改法 → 成本 → 验证指标”的结构，会更像真实项目经历。

---

## 四、综合评价

**优势**：

- 对 D2 的大方向有理解，能说出三类存储、Dense/Sparse 双路、图片存储的基本分工。
- 能主动提出 semantic chunking 作为 recursive chunking 的改进方向，并说出 embedding 成本、provider 差异、调参困难。
- Q10 对 metadata 与正文不一致的问题抓到了核心：summary/tags 可能基于旧噪声生成。

**薄弱点**：

- 存储层 ID 设计理解不够细，尤其是业务 chunk ID 与存储 vector ID 的边界。
- 多模态链路的细节还偏模糊，placeholder、image_refs、image_id、caption 与 metadata 的关系需要再过一遍源码。
- 有时回答会漂到未学习范围或泛概念，比如删除不一致问题时转成了 Dense 语义检索失效。

**面试官建议**：

下一轮建议不要急着扩展到 D3。先把 D2 的每个阶段都按“输入、输出、写哪些字段、下游怎么用”画成表。重点补两个点：Stage 6 的 ID 对齐，以及 Transform 链每一步对 `Chunk.text` 和 `Chunk.metadata` 的具体影响。

---

## 五、评分

| 维度 | 分数（满分 10） | 评分依据 |
|-----|----------------|----------|
| 项目架构掌握 | 7 | 能讲出三类存储和 D2 主流程，但跨阶段字段对齐讲得不够完整。 |
| 简历真实性 | 7 | 未提供简历；按项目经历表达看，基础参与可信，但“深入设计”支撑不足。 |
| 算法理论深度 | 6 | semantic chunking 的权衡能讲到成本和稳定性，但评估实验还不够严谨。 |
| 实现细节掌握 | 5.5 | `chunk_id` 两套生成逻辑、多模态 metadata 关系掌握不稳。 |
| 表达清晰度 | 7 | 回答简洁，方向多数正确，但经常缺少完整因果链和代码字段名。 |
| **综合** | **6.5** | 已掌握 D1/D2 的基本概念，面试可过基础追问；源码细节和设计权衡需要继续打磨。 |
