# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-07-08 17:50:58  
**面试官风格**：FAST 速攻广度型  
**掷骰结果**：4  
**考察范围**：D1-D4（已学章节）；跳过 D1.5、D5-D10  
**评分**：7.5/10

---

## 一、面试记录

> ✅ 答对核心要点 | ⚠️ 方向正确但细节缺失 | ❌ 未能答出或方向错误

### 说明

首个按骰子抽到的问题“这个系统里有哪几类存储？它们各自负责什么？为什么不能只用一个存储？”与上一场面试重复，按防重复规则跳过，改问下一题。

### 方向 1：项目综述

| 轮次 | 问题 | 候选人回答（原文） | 评估 | 参考答案 |
|-----|------|-------------|------|---------|
| Q1 | 这套系统在什么情况下检索效果最差？结合你已学过的 D1-D4 说：可能是哪一段链路出问题，以及可以怎么缓解？ | 我理解的是 面试官想问我怎么调参<br><br>那么有哪几个阶段呢？<br>首先ingestion阶段，enricher阶段？chunking阶段？这里语义切分、parent-child chunking可能更好，还有调chunk size， overlap。向量生成阶段？存储阶段（应该不可能）？<br>混合检索阶段，首先dense检索，向量相似度，怎么调参？dense检索是算出score，sparse检索呢？crossencoder判断相关性，crossencoder可以优化成LLM判断，更贵但是效果更好 | ✅ | [→ 查看](#a-检索效果差) |

### 方向 2：项目表达

| 轮次 | 问题 | 候选人回答（原文） | 评估 | 露馅 | 参考答案 |
|-----|------|-------------|------|-----|---------|
| Q2 | 如果 Reranker 服务挂了，系统会有什么降级策略？用户能感知到吗？ | reranker是增强，如果挂了应该优雅降级，降级到混合检索的结果，用户不会感知，只是结果可能没有增强后的答案相关性高 | ✅ | 否 | [→ 查看](#a-reranker降级) |

### 方向 3：技术深挖

| 轮次 | 问题 | 候选人回答（原文） | 评估 | 参考答案 |
|-----|------|-------------|------|---------|
| Q3 | Cross-Encoder 和 Bi-Encoder 的区别是什么？为什么 Cross-Encoder 不能做粗排召回？ | cross encoder是把query和candidate一起放到模型里，做的是token level的交叉判断。Bi-Encoder我猜，应该是先走embedding模型，把chunk text放进数据库，再走向量数据库检索余弦相似度检索。所以cross会很慢，成本更高，但是更精准。 | ✅ | [→ 查看](#a-cross-encoder) |
| Q4 | RRF 融合公式是什么？为什么项目里用 RRF，而不是把 Dense 分数和 Sparse 分数直接加权平均？ | 积分 (1-rank(d))/平滑系数。因为两个分数基数不一样，尺度不一样，一个0-1，一个可能分数是几 | ⚠️ | [→ 查看](#a-rrf公式) |
| Q5 | RecursiveCharacterTextSplitter 是按什么规则切分的？`chunk_size` 和 `chunk_overlap` 分别影响什么？ | 先段落，再行，再句子，再词<br><br>chunk size影响检索效率，LLM模型的token占用，最终生成输出的无关答案长度，overlap主要是防止上下文被阶段带来的指代丢失，太大会增加成本，并且带来无关信息过多 | ✅ | [→ 查看](#a-recursive-splitter) |
| Q6 | QueryProcessor 在检索前主要做哪些预处理？它和 Dense Retriever / Sparse Retriever 的边界是什么？ | 它接受用户query，给dense retriver返回original-query因为dense需要语义完整性，给sparse返回用jieba分词处理的关键字 | ✅ | [→ 查看](#a-queryprocessor) |
| Q7 | ResponseBuilder、CitationGenerator、MultimodalAssembler 分别负责什么？为什么说 ResponseBuilder 不是 LLM 答案生成层？ | response builder主要是给用户构建可读的markdown。citation generator做的是组装源饮用，multilmodalassembler做的是图片的拼装和源饮用 | ⚠️ | [→ 查看](#a-response构建) |
| Q8 | LLM Reranker 相比 Cross-Encoder 有什么优劣？什么场景下你会选择用 LLM Rerank？ | 优势：做相关性判断更精确，更能识别复杂意图，更能回判断，是否真正回答了用户的问题<br>劣势： 成本高，不稳定，需要设计prompt，降级策略，需要处理模型的不稳定，<br><br><br>对于business value高的query，会做LLM，中低用cross-encoder甚至不做reranker | ✅ | [→ 查看](#a-llm-reranker) |

---

## 二、参考答案

### <a id="a-检索效果差"></a>Q: 这套系统在什么情况下检索效果最差？怎么缓解？

**参考答案**：
这题问的是**当前项目已经具备 Hybrid Search、RRF、Reranker 之后，仍然可能检索效果差的边界**，不是泛泛回答“RAG 可以加混合检索/精排”。当前项目已经做了这些增强，所以更好的回答应落在这些机制仍解决不了的场景：

1. **召回阶段没召到正确 chunk**：Reranker 只能重排候选，不能凭空找回未进入候选集的答案。比如 chunk 切分不合理、答案跨多个 chunk、query 关键词/语义都没有覆盖到正确片段时，Cross-Encoder 或 LLM Reranker 也救不了。
2. **Ingestion 源头信息损失**：PDF 表格、代码块、复杂排版、图片中的关键信息如果在 Load/Transform 阶段丢失或变形，后续 Dense/Sparse/Rerank 都只能基于错误内容工作。
3. **Chunking 颗粒度不适合当前语料**：`chunk_size` 太小会缺上下文，太大会引入噪声；`overlap` 太小会丢跨边界指代，太大会增加重复和无关信息。可以尝试 semantic chunking、parent-child chunking，或按文档类型调参。
4. **领域术语和中文表达不匹配**：Dense 对专有名词、缩写、代码名不一定稳；Sparse 依赖分词和关键词覆盖。即使做了 Hybrid，某些领域词表、同义表达、拼写变体仍可能召回不足。
5. **Query 本身过宽、歧义大或需要多跳推理**：当前检索链路更擅长找局部证据。如果问题需要组合多个 chunk、跨章节推理或业务判断，Top-K 里可能混入大量看似相关但不能回答问题的内容。
6. **Rerank 成本和稳定性约束**：Cross-Encoder 精排候选集太小可能漏掉正确答案，太大则延迟高；LLM Reranker 更能理解复杂意图，但成本高、输出不稳定，需要 schema 校验和 fallback。

候选人的回答把重点放在 chunking、semantic/parent-child chunking、`chunk_size`、`overlap`、Dense/Sparse、CrossEncoder/LLM Reranker 取舍上，方向是对的。更完整的表达可以补一句：**当前项目已经有 Hybrid/RRF/Reranker，因此真正的失败边界主要在召回前的信息损失、候选集没覆盖、chunk 颗粒度和复杂 query 上；精排只能改善排序，不能弥补召回缺失。**

---

### <a id="a-reranker降级"></a>Q: Reranker 服务挂了怎么降级？

**参考答案**：
Reranker 是增强模块，不应影响主链路可用性。失败、超时或返回格式异常时，系统应 Graceful Fallback 到 Hybrid Search / RRF 的原始排序结果，并记录 fallback metadata 或日志。用户通常不会看到错误，只是结果相关性可能低于精排后的结果。

---

### <a id="a-cross-encoder"></a>Q: Cross-Encoder 和 Bi-Encoder 的区别？为什么不能做粗排召回？

**参考答案**：

| | Bi-Encoder | Cross-Encoder |
|--|-----------|--------------|
| 编码方式 | Query 和 Document 分别编码为向量，算相似度 | Query 和 Document 拼接一起输入模型，联合建模 |
| Document 向量 | 可离线预计算 | 每对 Query-Chunk 必须实时推理 |
| 精度 | 较低，但快 | 更高，但慢 |
| 适合场景 | 大规模粗召回 | 小候选集精排 |

Cross-Encoder 不能做粗排，是因为如果对全量 chunk 逐对推理，复杂度和延迟不可接受。正确链路是先用 Dense/BM25 粗召回 Top-N，再用 Cross-Encoder 对小候选集精排。

---

### <a id="a-rrf公式"></a>Q: RRF 融合公式是什么？为什么不用线性加权？

**参考答案**：

$$Score_{RRF}(d) = \sum_i \frac{1}{k + Rank_i(d)}$$

在本项目里通常是：

$$Score_{RRF}(d) = \frac{1}{k + Rank_{Dense}(d)} + \frac{1}{k + Rank_{Sparse}(d)}$$

`k` 是平滑因子，常见经验值为 60。RRF 不直接融合原始分数，而是融合排名。原因是 BM25 分数和向量相似度分数量纲不同，直接加权平均需要归一化，还会引入额外权重超参；RRF 只依赖排名，更稳健。

---

### <a id="a-recursive-splitter"></a>Q: RecursiveCharacterTextSplitter 怎么切分？chunk_size / overlap 影响什么？

**参考答案**：
`RecursiveCharacterTextSplitter` 会按一组分隔符递归切分，通常优先保留较大的自然结构，比如段落、换行、句子、词等，直到满足 `chunk_size` 限制。

- `chunk_size`：控制单个 chunk 的最大长度。太小会丢上下文，太大召回不精确、占用更多 token、引入更多无关信息。
- `chunk_overlap`：控制相邻 chunk 的重叠上下文，缓解边界切断和指代丢失。太大会增加存储、embedding 和检索成本，也会造成重复信息。

---

### <a id="a-queryprocessor"></a>Q: QueryProcessor 做什么？边界是什么？

**参考答案**：
QueryProcessor 负责检索前预处理，包括 query 归一化、过滤器解析、关键词提取、jieba 分词等。它产出结构化的 `ProcessedQuery`。

边界：
- Dense Retriever 需要保留语义完整的 query，用于生成 query embedding。
- Sparse Retriever 更依赖关键词/token，用于 BM25 倒排索引检索。
- QueryProcessor 不负责真正召回，也不直接访问向量库或 BM25 索引；召回由 Dense/Sparse Retriever 完成。

---

### <a id="a-response构建"></a>Q: ResponseBuilder、CitationGenerator、MultimodalAssembler 分别负责什么？

**参考答案**：
ResponseBuilder 负责把检索结果组织成客户端可消费的响应结构或 Markdown 文本，包括结果排序、摘要展示、引用挂载等。它不是 LLM 答案生成层，不负责根据 context 生成自然语言答案，而是对已有检索结果做格式化与封装。

CitationGenerator 负责生成来源引用，如文件名、页码、chunk id、片段摘要等，增强可追溯性。

MultimodalAssembler 负责把多模态内容组装进响应，例如将命中的图片、caption、图片路径或 Base64 内容与文本结果对齐。

---

### <a id="a-llm-reranker"></a>Q: LLM Reranker 相比 Cross-Encoder 有什么优劣？

**参考答案**：
LLM Reranker 的优势是能理解更复杂的查询意图、业务规则和长文本上下文，也能通过 prompt 要求输出排序理由或 JSON 结构。适合高价值、复杂意图、多约束的问题。

劣势是延迟高、成本高、输出不稳定，需要 prompt 设计、JSON schema 校验、异常处理和 fallback。Cross-Encoder 更稳定、便宜、延迟可控，适合常规相关性精排。

实际选择上，可以对高价值或复杂 query 使用 LLM Rerank，对普通查询使用 Cross-Encoder，低价值或延迟敏感场景甚至只用 RRF 结果。

---

## 三、包装识别点评

本轮没有提供简历，因此不做具体简历包装真实性判断。

### 表现稳定点
- **Reranker 降级**：能说清 Reranker 是增强模块，失败后回退到 Hybrid/RRF，用户通常无感知。
- **Cross-Encoder vs Bi-Encoder**：能抓住“联合输入更准但更慢”和“Bi-Encoder 适合向量召回”的核心区别。
- **LLM Reranker 取舍**：能从效果、成本、稳定性、业务价值分层使用几个角度说明。

### 露馅风险
- **RRF 公式**：回答成了“(1-rank(d))/平滑系数”，公式错误。严重性：中。你知道不能直接加权平均，但必须把公式背准。
- **Response 构建**：知道大致分工，但“源饮用/引用”和多模态返回边界说得不够完整。严重性：低到中。
- **检索效果差的场景**：回答覆盖了当前项目的主要调参方向，尤其是 chunking、Dense/Sparse、CrossEncoder/LLM Reranker。更好的版本需要明确“当前项目已经有 Hybrid/RRF/Reranker，真正差的场景是这些机制仍解决不了的边界”。

---

## 四、综合评价

**优势**：
- D3/D4 新学内容吸收较快，能讲出 Hybrid/Rerank 的主链路和降级思想。
- 对工程取舍有意识，比如 LLM Reranker 只给高 business value query 用。
- Chunking 参数的回答比较实用，能提到 token 成本、无关信息、上下文丢失。
- Q1 对当前项目调参方向判断基本正确，提到了 chunking、semantic/parent-child chunking、Dense/Sparse 和 Reranker 取舍。

**薄弱点**：
- RRF 公式必须修正为 `sum(1 / (k + rank_i))`，不是 `(1-rank)/k`。
- 对“当前项目检索效果最差”这类开放题，需要突出已实现能力的边界：Hybrid/RRF/Reranker 已经存在，剩下主要是源头信息损失、候选集召回不到、chunk 颗粒度不适配和复杂 query。
- ResponseBuilder 不是生成答案，而是结果格式化、引用和多模态内容组装入口，这个边界还要讲得更准。

**面试官建议**：
下次准备时，把 D3/D4 各整理成“一句话职责 + 输入输出 + 失败降级 + 可调参数”。尤其是 RRF、QueryProcessor、Reranker fallback 这三个点，面试高频且容易被追公式和边界。开放题要先限定语境：如果面试官问“当前项目哪里差”，先说明项目已经做了哪些增强，再回答这些增强仍覆盖不到的失败边界。

---

## 五、评分

| 维度 | 分数（满分 10）| 评分依据 |
|-----|--------------|--------------------------------|
| 项目架构掌握 | 7.5 | 能按链路说到 Ingestion、Hybrid、Rerank；Q1 对调参方向判断基本正确，但没有明确强调当前项目已具备 Hybrid/RRF/Reranker 后的剩余失败边界。 |
| 简历真实性 | N/A | 本轮未提供简历，不评分。 |
| 算法理论深度 | 6.5 | Cross-Encoder、LLM Reranker 理解较好；RRF 公式错误扣分明显。 |
| 实现细节掌握 | 7 | QueryProcessor、Response 构建、chunking 都能说出核心边界，但细节还需更精确。 |
| 表达清晰度 | 7.5 | 多数回答方向正确，部分回答有“我猜”“应该”等不确定表达；Q1 是题目语境不够精准导致回答和评分出现偏差，已重新校正。 |
| **综合** | **7.5** | 已能覆盖 D1-D4 主链路，适合 FAST 广度面；主要扣分点集中在 RRF 公式和部分实现边界表达。 |
