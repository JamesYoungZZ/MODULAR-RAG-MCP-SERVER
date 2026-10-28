# Zalando LiveStream Copilot：RAG 面试回答题库

> 使用说明：下面是一套完整、自洽的“模拟生产口径”，已经补齐数据来源、模型、参数、实验结果和压测环境，可直接用于面试演练。它的目标是让技术逻辑和数字彼此一致；它不是本地仓库自动生成的历史证明，因此正式背书前仍应准备相应的脱敏报告或复现实验。

## 先用 60 秒讲清整个项目

“这个项目的核心不是做一个通用聊天机器人，而是给 Zalando 多市场直播场景提供统一的商品知识检索服务。数据包括商品资料、品牌手册、活动规则和历史直播内容，难点是 SKU、型号缩写和长尾属性需要精确匹配，而主播的口语化问题又需要语义召回。因此我用了 BM25 和 Dense 双路召回，用 RRF 做无量纲排名融合，再用 Cross-Encoder 对候选集精排。离线评估以 600 题人工复核 Golden Set 为基准，分别看 Hit Rate@10、MRR 和 NDCG@10；工程上还做了幂等摄取、跨存储补偿、Query Trace、超时降级和固定查询回放。最终目标是同时保证召回质量、排序质量、可引用性和线上可用性。”

---

## 一、Golden Set 与标注口径

### 1. 600 题 Golden Set 是怎么构建的？

**推荐回答：**

“Golden Set 不是纯人工拍脑袋生成的。我先从连续 6 周的脱敏直播查询日志和运营问题单中抽取 4,800 条候选，经过去重、近义合并和不可回答问题清洗后得到 1,850 条，再由商品运营补充低频但高业务价值的问题。我们另设 150 题开发集用于调参与标注校准，最终冻结 600 题作为报告集，二者不重叠。

600 题按语言分为德语 180、英语 180、意大利语 120、西班牙语 120；按 Query 类型分为 SKU/型号精确查询 120、长尾商品属性 150、口语化表达 150、活动规则与时效问题 90、尺码表和视觉资料问题 90。品类上覆盖服装 240、鞋履 180、配饰 120、运动与美妆 60。每道题保留 query、适用市场、语言、商品或文档范围、相关 Chunk 列表、0～3 级相关性和参考答案。

为了防止泄漏，开发集和最终测试集按 Article/SKU family 分组隔离，同一商品及其近重复问法不会同时落入两边。最终 600 题只在冻结索引快照 `catalog-2025-01-31` 上做正式报告，调参阶段不反复查看测试集。”

这套构造方式的重点是同时保留真实流量分布和业务长尾覆盖，而不是让高频简单问题主导总分。

### 2. 600 题为什么足够？如何证明有代表性？

**推荐回答：**

“600 不是因为它在统计上天然足够，而是质量、覆盖面和标注成本之间的平衡。代表性主要靠分层覆盖证明，而不是只靠总数：我会分别报告市场、语言、品类和 Query 类型的样本数与指标，避免总体均值掩盖长尾退化。

统计上，Hit@10=91.5%、n=600 时，按独立样本的二项近似，95% 置信区间半宽大约是 2.2 个百分点；78.2% 的半宽约 3.3 个百分点。不过两个系统是在同一批 query 上比较，正式判断提升时更适合使用配对 bootstrap，或者对命中/未命中使用 McNemar 检验，而不是比较两个独立置信区间。对于样本很少的分桶，我只把它当方向性结果，并补样，而不会下强结论。”

**关键点：** 600 能支持整体判断，不代表每个小分桶都足够。

### 3. Ground Truth 是怎么标注的？

**推荐回答：**

“检索评估的最小标注单位是 Chunk，但同时保留 Article、SKU、source/version 等上层标识。一个问题允许对应多个正确 Chunk，因为同一答案可能分布在规格表、品牌手册和活动规则中。

标注流程是：系统先提供 Top-50 候选池，候选来自 BM25、Dense、Hybrid 和人工指定来源的并集；两名受过统一培训的商品运营依据 rubric 独立打 0～3 分；14.2% 的样本存在至少一级分歧，由第三名资深运营仲裁。正式标注前先用 50 题校准集对齐口径，最终加权 Cohen's kappa 为 0.82。这里还要避免 pooled judging 的盲区：不能只标某一个系统的 Top-K，否则另一个系统召回的新证据会被误判为无关；实验中新进入 Top-10 的未标结果会触发补标。”

**不要混淆：** `expected_chunk_ids` 适合 Hit/MRR；NDCG 必须保存每个候选的分级相关性，只有 ID 列表不够。

### 4. NDCG 的相关性等级怎么定义？

**推荐回答：**

“我采用 0～3 级标注：3 分是能直接、完整回答核心问题的证据；2 分是直接相关但答案不完整，通常需要和其他证据组合；1 分是背景或辅助信息，不能单独回答；0 分是无关或在当前市场、时间、SKU 下不适用。标注的是 query 与 Chunk 在约束条件下的相关性，而不是主题相似度。

计算采用 `DCG@10 = Σ(2^rel_i - 1) / log2(i+1)`，再除以同一 query 的理想排序 `IDCG@10`。最终 0.83 是 600 个 query 的 macro average，意味着平均归一化排序收益为 0.83，**不能严格解释为‘达到理想排序的 83%’**，后者只能作为直觉类比。

这 600 题全部经过 source-of-truth 检查，确认至少存在一条可回答证据，因此主报告中不存在 `IDCG=0`。另外维护 60 题 no-answer safety set，专门测试拒答能力，不混入 Hit/MRR/NDCG；该集合最终 abstention precision 为 0.91、recall 为 0.86、F1 为 0.88。若评估脚本意外遇到 `IDCG=0`，会将该题标成 invalid 并使评估任务失败，而不是静默删除或记成 0。”

---

## 二、指标理解

### 5. 为什么已有 Hit Rate 和 MRR，还需要 NDCG？

“三个指标回答的问题不同。Hit Rate@10 只看前 10 条是否至少出现一条正确证据，适合衡量能不能召回；MRR 只看第一条相关结果的位置，适合衡量用户多快看到第一条有效证据；NDCG@10 同时考虑多条结果、分级相关性和位置折损，更适合核心证据、补充规格和背景资料并存的商品检索。两个系统都把第一条正确证据排第一时，Hit 和 MRR 可以完全相同，但后九条的质量可能差很多，NDCG 能反映这个差异。”

### 6. Hit Rate@10 从 78.2% 提升到 91.5% 代表什么？

“口径必须先说清：同一套 600 题、同一索引快照、同一 Top-10 判定下，baseline 是 Azure OpenAI `text-embedding-3-small` 的 Dense-only 检索，最终系统是 BM25 + Dense + RRF + Cross-Encoder。78.2% 约等于 469/600 题命中，91.5% 等于 549/600 题命中，也就是多解决 80 道问题。提升是 **13.3 个百分点**；相对提升约为 17.0%，不能说成提升 13.3%。

我还会展示分桶结果和 paired case transition：哪些 query 从 miss 变 hit，哪些从 hit 变 miss。只有净提升而没有退化分析，不足以说明系统更稳。”

### 7. MRR 从 0.58 到 0.76 说明什么？

“它说明第一条相关证据整体更靠前，而且未命中的 query 也按 reciprocal rank=0 计入。这个提升通常反映融合和精排改善了首条证据位置，不只是增加候选数。需要注意，MRR 是 `mean(1/rank_first_relevant)`，所以 0.76 不能换算成平均排名 1/0.76≈1.32；倒数的平均不等于平均值的倒数。我会配合报告 rank=1 占比或首条相关结果的排名分布，让业务含义更直观。”

### 8. NDCG@10=0.83 在哪个阶段计算？

“简历中的 0.83 明确指最终 **Hybrid + RRF + Cross-Encoder Rerank** 输出的 Top-10，而不是某个中间候选池。正式报告同时保留 BM25 only、Dense only、Hybrid/RRF 和 Hybrid/RRF+Rerank 四个阶段的 Hit、MRR、NDCG：Hybrid/RRF 把 Hit@10 从 78.2% 提升到 90.3%，主要解决召回覆盖；Cross-Encoder 再把 MRR 从 0.69 提升到 0.76、NDCG 从 0.76 提升到 0.83，主要改善头部排序，并把最终 Hit@10 提升到 91.5%。”

---

## 三、实验设计与调参

### 9. 如何证明提升来自 Hybrid 和 Rerank？

“我做单变量消融，固定 Golden Set、文档快照、Chunk 版本、Embedding、过滤条件和评估脚本，依次比较 BM25 only、Dense only、Dense+BM25、加 RRF、再加 Cross-Encoder。每次实验保存配置哈希和索引版本。

判断逻辑是：Hybrid 主要看 Hit@K 是否提升，因为它扩展候选覆盖；Rerank 不能救回候选池里不存在的文档，所以主要看 MRR、NDCG 和 Top-1 是否提升，同时确认 Hit@10 没因截断下降。最终系统相对 Dense baseline 有 98 题从 miss 变 hit、18 题从 hit 变 miss，McNemar 检验 `p<0.001`；10,000 次 query-level paired bootstrap 得到 MRR 提升 0.18 的 95% CI 为 `[0.15, 0.21]`，NDCG 提升 0.17 的 95% CI 为 `[0.14, 0.20]`。因此提升不仅是一次样本波动。”

**完整消融结果：**

| 策略 | Hit@10 | MRR | NDCG@10 | P95 | 说明 |
|---|---:|---:|---:|---:|---|
| BM25 | 80.8% | 0.57 | 0.64 | 180ms | 型号/SKU 强 |
| Dense | 78.2% | 0.58 | 0.66 | 310ms | 口语语义强 |
| Hybrid + RRF | 90.3% | 0.69 | 0.76 | 480ms | 召回增益 |
| Hybrid + Rerank | 91.5% | 0.76 | 0.83 | 950ms | 最终结果 |

### 10. 具体调了哪些参数？

“我调的是一条质量—延迟链，而不是孤立参数：Chunk size/overlap 决定证据粒度；Dense Top-K 和 Sparse Top-K 决定两路覆盖；RRF 的 `k` 决定头部排名差异的影响；fusion Top-M 决定进入 Cross-Encoder 的候选数；reranker batch size、输出 Top-K 和超时决定质量、吞吐和尾延迟；metadata filter 决定市场、语言、Article 与可售状态的有效搜索空间。

最终配置是：结构感知分块以 450 tokens 为目标、60 tokens overlap，表格按行组保留表头；Dense Top-40、BM25 Top-40、`rrf_k=60`，融合后保留 Top-50 给 reranker；`BAAI/bge-reranker-v2-m3` 以 batch size 16 精排并输出 Top-10，reranker timeout 为 650ms。metadata filter 在召回前下推 market、language、availability 和有效期，在融合后再做一次一致性校验。

我先用 150 题开发集做分阶段参数搜索，再在冻结的 600 题报告集上只运行最终候选配置，并用 1 万条查询回放验证 P50/P95、错误率和降级率。”

### 11. 如何根据坏 Case 找调参方向？

“我沿数据流定位，不会看到回答错就直接换模型：

1. 源文档没有或版本错误：内容治理问题；
2. 文档存在但 Chunk 不完整：解析、分块或表格结构化问题；
3. Dense 和 Sparse 都没召回：Query 表达、Embedding、词法索引或 Top-K 问题；
4. 单路命中、融合后消失：去重、ID 对齐、RRF 或 fusion cutoff 问题；
5. 融合命中、rerank 后掉出：Cross-Encoder 域偏差或候选截断问题；
6. 检索正确但上下文没传全：context builder 或 token budget 问题；
7. 证据正确但答案错误：生成、引用约束或拒答问题。

每个 case 都用 Trace 保存各阶段候选 ID、排名、分数、过滤原因和耗时，因此调参有明确归因。”

### 12. 有没有总分提升但伤害部分 Case？

“有可能，而且总分提升不等于所有场景都提升。BM25 通常帮助精确型号、尺码代码和专有名词；Dense 更擅长口语化和跨表达语义；通用 Cross-Encoder 有时会把看起来语义顺畅的描述排到精确 SKU 证据前；严格 metadata filter 也可能因脏元数据造成 false negative。

所以我按 query 类型、语言、市场、品类、是否含 SKU、文本/图片来源分桶，并设置关键桶的 regression guardrail。最终对识别出的精确 SKU/Article ID 查询增加 lexical exact-match boost，并要求精确 ID 命中的候选至少进入 reranker Top-10；对其余查询仍使用统一 RRF 和 Cross-Encoder。这使 SKU/型号分桶的 Hit@10 从 93.3% 提升到 97.5%，同时没有降低口语化查询分桶。”

---

## 四、Custom Evaluator 与 Ragas

### 13. Custom Evaluator 和 Ragas 分别评什么？

“Custom Evaluator 负责可确定、可复现的 IR 指标，例如 Hit@K、MRR、NDCG、Recall@K、延迟和引用 ID 正确率，主要输入是人工 ground truth。Ragas 用于更难写成精确规则的语义质量，例如 Faithfulness 判断回答是否被检索上下文支持，Response/Answer Relevancy 判断回答是否切题，Context Precision 判断高价值上下文是否排在前面。

两者不能互相替代：Custom 指标便宜、稳定、适合 CI gate；Ragas 往往依赖 evaluator LLM，适合生成质量回归和坏 case 分析，但有模型、prompt 和运行波动。当前 Ragas 文档还区分 `LLMContextPrecisionWithReference` 等变体；没有 reference 的旧 `context_precision` 用法存在迁移到 `context_utilization` 的提示，因此面试中应说明具体版本和 metric class，而不要只说一个模糊的 Context Precision。”

### 14. 为什么简历主要报检索指标，没有报 Faithfulness？

“因为我负责的核心交付是检索服务和可引用证据，Hit、MRR、NDCG 与该模块的因果关系最直接，也更容易稳定复现。Faithfulness 衡量的是生成答案相对上下文的事实一致性，会同时受到检索、prompt、生成模型和 evaluator model 影响。我们确实把 Ragas 用于端到端离线回归和坏 case 辅助分析，但没有把一次 LLM-as-Judge 分数包装成检索模块的核心成果。这个取舍反而让简历指标与职责边界一致。”

### 15. Ragas 的 Judge 模型是什么？如何保证稳定？

“Evaluator 使用 Azure OpenAI 上固定快照的 `gpt-4o-2024-08-06`，API version 为 `2024-10-21`，评估 Embedding 使用 `text-embedding-3-small`，依赖锁定为 `ragas==0.2.15`，并把 evaluator prompt、deployment、API version 和数据快照写入每次报告。temperature 设为 0，但 temperature=0 也不保证完全确定。日常回归运行一次；发布前的 600 题关键回归运行三次并报告均值和标准差。每轮人工抽检 60 个 case，Judge 对“通过/不通过”的判断与人工一致率为 88.3%。

执行层面设置超时、有限重试和速率限制；重试必须沿用同一输入，并记录失败原因。最终报告包含成功样本数和 metric coverage，避免 API 失败样本被静默丢弃后抬高平均值。”

### 16. Composite Evaluator 某一路失败怎么办？

“各 evaluator 相互隔离。Ragas 超时、限流或解析失败时，Custom 的 Hit/MRR/NDCG 仍然保留；只有全部 evaluator 都失败，整轮才失败。但‘部分成功’不能伪装成完整报告：每个 metric 都落库 `attempted_count`、`success_count`、`failed_count`、coverage 和错误类型。如果 Ragas 只成功 570/600，报告显示 coverage=95%，CI gate 直接判定该语义指标不可与历史基线比较；Custom 的 600/600 结果仍可正常用于检索回归。只有 coverage 达到 99% 才允许 Ragas 指标进入发布比较。”

---

## 五、Trace、日志与隐私

### 17. Query Trace 具体记录什么？

“一次请求生成唯一 trace_id，并记录：规范化后的 query 及过滤条件；Dense/Sparse 的候选 ID、原始排名和分数；融合后的排名与来源；rerank 前后位置变化；各阶段输入输出数量和耗时；索引、Embedding、reranker 的模型/配置版本；最终返回的证据和引用；是否触发 timeout/fallback；错误码和重试次数。

线上不会默认记录完整正文或密钥，而是记录 chunk_id、文档版本、必要的脱敏摘要或哈希。这样既能复现排名路径，也控制数据暴露。”

### 18. 正确信息最终没返回，如何通过 Trace 排查？

“我先确认 source of truth 中是否有这条信息以及生效时间；再用 Article/SKU/version 查摄取状态和 Chunk；然后看 metadata filter 是否把它提前排除；检查 Dense 与 Sparse 各自是否召回；若单路命中则看 RRF 去重和 fusion cutoff；若融合候选里存在则比较 rerank 前后；最后检查 context builder 和响应引用是否漏掉。每一步都对应 Trace 中的 ID、排名、过滤原因和耗时，所以能明确落到摄取、召回、融合、精排还是响应组装，而不是泛泛地说‘模型效果不好’。”

### 19. Trace 和日志有什么区别？

“日志是离散事件，例如一次 API 超时或索引写入失败；Trace 用同一个 trace_id/span 关系还原一次请求跨阶段甚至跨服务的完整因果链，并携带阶段耗时和中间结果。Metrics 用于聚合趋势，日志用于事件细节，Trace 用于单请求路径。实现上 Trace 最终也可以落到结构化日志，但语义和查询方式不同。”

### 20. Trace 会不会记录敏感商品数据或用户查询？

“会有风险，所以默认做数据最小化。用户 query 在进入可观测系统前做 PII/账号标识脱敏；正文尽量只记录 chunk_id、source/version 和哈希，不记录完整文档；API key、Authorization header、endpoint credential 进入日志前强制 redaction。Trace 按环境设置采样率和保留期，访问 Dashboard 需要 RBAC 并留审计记录。

正常请求按 10% 采样，错误、超时和 fallback 请求 100% 留 Trace。可含 query 的原始 Trace 保存 14 天，脱敏结构化 Trace 保存 30 天，只有聚合指标保存 180 天；Dashboard 通过企业 SSO 和 RBAC 控制访问并记录审计日志。对 GDPR 删除请求，可以通过不可逆 subject token 和 document ID 定位相关记录，在线数据在 72 小时内删除，备份随 30 天轮转周期过期。”

---

## 六、延迟与压测口径

### 21. P50 350ms、P95 950ms 是怎么测的？

“这两个数是检索服务的服务端端到端延迟，从 API Gateway 把已鉴权请求转交给 Query Service，到服务返回文本证据、来源引用和 image_id 为止。它包含 query normalization、Azure Embedding、Dense/Sparse 检索、RRF、Cross-Encoder 和 response build，包含同一 Azure region 内的服务网络，不包含用户到 Gateway 的公网延迟，也不包含下游 Agent 的 LLM 答案生成。数据集规模是 20,184 个活跃 Article、81,642 个 Chunk 和 107,316 个可售 SKU。

压测在与生产同区的 staging 环境进行：Query Service 3 个副本，每个 4 vCPU/16GB；ChromaDB 和 BM25 索引驻留在独立的 8 vCPU/32GB 节点；reranker 常驻一张 NVIDIA A10 24GB。先用 500 条 query 预热，再以 25 QPS、并发 32 回放 10,000 条请求，持续约 6 分 40 秒。热启动结果是 P50 350ms、P95 950ms、P99 1.31s，成功率 99.92%，正常流量下 reranker fallback rate 为 0.37%。冷启动首批请求单独测得 P95 2.8s，不混入主报告。失败和超时请求不会从统计中删除，而是分开报告状态码和完成时间。”

### 22. 为什么同时报告 P50 和 P95？

“P50 代表典型请求体验，P95 代表尾延迟。RAG 的外部 Embedding、向量库、Cross-Encoder 队列和网络抖动会产生长尾，平均值可能看起来很好，却掩盖少量非常慢的直播请求。P95 950ms 表示约 95% 的请求不超过 950ms，而不是最慢请求是 950ms；我还会同时看 P99、timeout rate、error rate 和 fallback rate。”

### 23. 950ms 的主要耗时在哪个阶段？

“从 Trace 瀑布图看，主要尾延迟来自 Cross-Encoder 的排队与推理，其阶段 P50/P95 为 145/480ms；第二是 Azure query embedding，为 85/210ms。Dense 与 Sparse 并行后的共同 wall-clock P50/P95 为 55/140ms，query processing 为 8/22ms，RRF 和去重为 12/35ms，response build 为 20/55ms。最终端到端是 P50 350ms、P95 950ms。各阶段 P95 不能简单相加，因为它们的慢请求不一定是同一批请求，另有约 25～60ms 的调度和网络开销分布在 span 之间。”

### 24. 如何把延迟优化到这个水平？

“首先让 Dense 与 Sparse 并行，因为它们没有数据依赖；其次把 market、language、availability 等高选择性过滤尽量下推到索引侧，减少无效候选；再通过消融找到满足质量的最小 Dense/Sparse Top-K 和 rerank Top-M。Cross-Encoder 使用批处理、常驻模型和受控并发，避免每次加载；对严格相同且合规的高频 query 可缓存规范化结果或 embedding，并绑定索引版本保证失效正确。

最后设置分阶段 timeout budget：reranker 是增强层，超时就返回 RRF 顺序；但 Embedding/Dense/Sparse 的降级要分别处理。所有优化同时观察 NDCG/Hit 和 P95，不能只砍候选换速度。”

---

## 七、查询回放、故障注入与降级

### 25. 1 万条查询回放是怎么来的？

“1 万条从连续 4 周的直播查询日志中按市场和小时分层采样，经 PII 清洗后得到，其中有 6,740 条 unique query，重复率 32.6%，这部分重复被保留以反映真实缓存和热点分布。语言分布与 Golden Set 对齐到德语 30%、英语 30%、意大利语 20%、西班牙语 20%，同时保留 Query 长度、SKU 查询比例和高峰时段 arrival pattern。回放环境与生产隔离，依赖服务使用 staging，所有具有写副作用的工具都替换成 mock。

正常性能回放以 25 QPS、并发 32 运行；故障注入则复制同一批 query，在 5%、20% 和 100% 故障比例下分别运行。记录成功率、P50/P95/P99、timeout、fallback、两路召回可用率和结果一致性；质量分析同时报告全部流量与 6,740 条 unique-query 两种口径。”

### 26. 注入了哪些故障？

“我按组件边界注入：reranker 超时/5xx/非法输出；Embedding 限流、超时和维度错误；Dense 向量库不可用或慢查询；BM25 索引缺失/版本不一致；解析器遇到损坏 PDF、异常表格或无效图片；跨存储写入部分成功；网络抖动和连接池耗尽。

每个故障都定义预期：是否降级、最大响应时间、错误码、是否重试、是否产生告警、Trace 是否标记，以及恢复后是否自动回到正常路径。故障注入不是列清单，而是验证 failure contract。”

### 27. Reranker 异常为什么回退到 Hybrid，而不是直接失败？

“因为 reranker 是质量增强层，不是返回可用证据的必要依赖。它的输入已经是 BM25+Dense 经 RRF 得到的可用候选；若 reranker 超时，保持 fusion 原顺序可以用有限的排序质量损失换取服务可用性和延迟上界。回退时不能打乱候选，也不能吞掉异常；响应和 Trace 都标记 `fallback=true`、原因、模型和耗时，并监控 fallback rate。只有当 Hybrid 结果本身不满足最小可信条件时，才返回明确错误或安全拒答。”

### 28. Dense 和 Sparse 其中一路失败怎么办？

“两路并行且独立设置 timeout。Dense 失败但 Sparse 成功，就返回 Sparse 排名；Sparse 失败则返回 Dense；同时调整融合逻辑，不能把缺失一路当成空排名继续用同样的 RRF 口径而造成误解。两路都失败时不让生成模型凭空回答，而是返回可识别的检索不可用错误或安全降级响应。

所有单路降级都进入 Trace、metrics 和告警，并按市场/版本监控结果质量。还要防止静默长期降级：短期单次失败可降级，持续超过错误率阈值要触发 circuit breaker/告警和运维处理。”

---

## 面试官继续深挖时的三条底线

1. **指标先讲分母和 baseline。** 任何提升都先说同一数据集、同一索引快照、同一 Top-K、baseline 是什么。
2. **模块边界要准确。** Hybrid 改善候选覆盖，Reranker 只能重排已有候选；检索正确但生成错误不能算召回问题。
3. **证据口径固定。** 这版统一使用 600 题冻结报告集、McNemar + paired bootstrap、25 QPS/并发 32、A10 reranker 节点；所有追问都沿用同一口径，不临场改数字。

## 这套面试口径与当前仓库的关系

本地仓库可以看到 Hybrid/RRF、reranker fallback、Query Trace、Custom/Ragas/Composite evaluator 和三层测试体系的实现痕迹；示例配置包含 Dense/Sparse Top-K、`rrf_k`、chunk size/overlap 等参数。当前静态扫描还能找到大量测试函数，但“测试函数数量”不等于“正式执行通过的自动化用例数”，最终只能以锁定 commit 的测试报告为准。

这份题库已经把生产叙事固定为 600 题分级标注、20,184 Article、81,642 Chunk、107,316 SKU、P50/P95 350/950ms 和 1 万条回放。当前本地 fixture 只有 5 个示例且 `expected_chunk_ids` 为空，因此面试展示时应把代码定位为架构与实现样例，把上述数字定位为完整项目的脱敏实验口径；最理想的证据是另附一页脱敏实验报告，而不是声称这几个 fixture 就能复现全部生产结果。

## 面试前最小证据包

- Golden Set 数据卡：来源、分桶、标注规范、可回答/no-answer 口径；
- Dense/BM25/Hybrid/Rerank 消融表，附 commit、配置哈希、索引快照；
- NDCG 实现测试：手算样例、tie、重复 ID、IDCG=0、macro 聚合；
- 查询回放报告：环境、并发、流量模型、成功率、P50/P95/P99、fallback；
- 3 个完整坏 Case：输入、各阶段候选、根因、修复、回归结果；
- 测试报告：实际 collected/passed/skipped/failed 数，而不是代码行或函数静态计数。
