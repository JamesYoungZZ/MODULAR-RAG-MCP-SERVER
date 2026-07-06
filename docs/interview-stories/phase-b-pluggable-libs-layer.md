# Phase B 面试讲述：可插拔 Libs 层

## 45 秒自然讲述版

> "这一阶段我主要做的是 RAG 系统里的可插拔 Libs 层。我的思路是先把核心能力抽象出来，比如 LLM、Embedding、Splitter、VectorStore、Reranker、Evaluator 这些模块，都定义统一的接口和工厂。这样上层的 ingestion 和 retrieval 流程就不需要关心底层到底用的是哪个厂商或者哪个实现。
>
> 在接口稳定之后，我补了几类默认实现：LLM 支持 OpenAI、Azure、DeepSeek 这种 OpenAI-compatible 接口，也支持本地 Ollama；Embedding 支持 OpenAI、Azure 和 Ollama；文本切分用了 LangChain 的 Recursive Splitter；向量库用了本地 Chroma；重排这块支持 LLM Rerank 和 Cross-Encoder Rerank；最后还加了 Azure Vision LLM，为后面的图片 caption 做准备。
>
> 这里最核心的设计决策就是把 provider 的差异都收敛到接口和 factory 里面，并且用配置来切换。这样后面业务流程只依赖稳定的抽象，不会被某一个 API 或厂商绑死。另外我在 rerank 失败时也设计了 fallback candidates，这样即使 LLM 或 cross-encoder 出问题，系统也可以退回原来的排序结果，而不是整个查询流程直接失败。"

## 面试追问：最难的点是什么

如果面试官问："这个阶段最难的点是什么？"，可以这样说：

> "我觉得最难的是在灵活性和可测试性之间找平衡。可插拔架构如果只写接口，很容易变成空架子，看起来设计很好，但其实跑不起来。所以我当时的做法是，每定义一个抽象，尽量都配一个能跑的默认实现，再配对应的测试。
>
> 比如外部 API 这块，我没有在单元测试里真的去调 OpenAI 或 Azure，而是 mock HTTP 请求，重点验证请求 payload、路由逻辑和错误处理是不是对的。Chroma 这块因为是本地向量库，我就用了临时目录做真实的 upsert 到 query 的 roundtrip 测试。这样既保证了架构是可扩展的，也能证明它不是只停留在接口设计上，而是真的可以跑通。"