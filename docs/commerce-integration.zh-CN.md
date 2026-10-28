# 直播商品资料检索入口

这是现有 RAG 项目的专用只读接入入口，服务于 livestream copilot；原有通用 MCP 工具和语料不受影响。

## 资料与发布

- 主资料：`fixtures/commerce/documents/*.md`；50款商品各一份指南、2份市场政策，共208个完整章节。
- 发布清单：`fixtures/commerce/manifest.json`，包含租户、商品、市场、版本、生效期、摘要校验值及PDF页码。
- PDF：`output/pdf/commerce/products/` 中50份商品PDF，`output/pdf/commerce/policies/` 中2份政策PDF。每份一页，由 `scripts/render_commerce_documents.py` 从对应 Markdown 生成；完整目录为 `output/pdf/commerce/INDEX.md`。
- 全部明确标记为虚构训练资料；没有真实消费者数据和厂商认证。库中没有实时库存和成交价格。

## 本地建立索引

安装项目依赖后，执行：

```sh
.venv/bin/python -m scripts.index_commerce --root fixtures/commerce --dense
```

默认 `--embedding local` 使用 Chroma 的本地 ONNX all-MiniLM-L6-v2；首次需要下载模型。没有远程 embedding 费用。只有主动加 `--embedding configured` 才使用原配置提供商。生成的 `vectors.json` 被 Git 忽略，服务启动会比对 manifest 摘要，防止旧索引配新资料。

BM25 使用项目原有 SparseEncoder 和 BM25Indexer；向量按允许的商品/市场章节做精确余弦排序；RRF复用现有 RRFFusion。当前208章节的精确排序便于检查过滤结果，大规模部署应换成带范围过滤的持久化向量索引。资料为英语，调用方须提供适合英语资料的查询词；尚无跨语言召回率结果。

PDF生成另需安装 ReportLab：

```sh
python -m scripts.render_commerce_documents
```

此入口直接索引主 Markdown，PDF用于阅读、出版核对和页码引用。这不代表已经验证 PDF解析/OCR链路。Markdown修改后要更新清单版本/摘要，先重建PDF（会更新PDF摘要），再重建向量，最后重启服务。

## MCP 运行契约

由 App 启动，也可从本目录手动启动：

```sh
COMMERCE_TENANT_ID=demo-tenant COMMERCE_DENSE_ENABLED=true .venv/bin/python -m src.mcp_server.commerce_server
```

这是 stdio 协议，不是浏览器 HTTP 服务。调试日志去stderr，不向stdout插入日志。默认语料为 `fixtures/commerce`，可以由部署环境 `COMMERCE_CORPUS_ROOT` 指定；模型不能指定。

工具：

- `search_commerce_documents(query, market, canonical_product_id?, top_k=5)`，最多8章节。
- `read_commerce_section(section_id, market, canonical_product_id?)`，读取原章节。

商品ID为空时只检索该市场政策；提供商品ID时只检索该商品和该市场通用政策。租户在进程初始化时绑定，未暴露任意集合选择、上传、删除或文件读取能力。发布状态和生效期都参与过滤。

输出 `commerce-retrieval-v1`：原章节文本、商品/市场/租户、文档版本、有效期、来源、SHA-256、PDF页码、`retrieval_mode`、`degraded` 和覆盖范围。无匹配不是“没有这条政策”；命中也不自动证明回答成立。RAG不生成答案。

当前单租户本地子进程的权限依赖服务端配置与文件访问控制；不是远程多租户OAuth部署。语料完整性摘要不是发布者数字签名。运行时查询向量失败会标记降级后走BM25；配置错误、索引缺失或版本不匹配在启动时报错。

## 首次接入验证（历史记录）

已构建真实本地向量，完成一次跨项目 stdio MCP 检索：CloudStep machine washing 查询，首个章节为 Cleaning and drying，`retrieval_mode=dense_bm25_rrf`、`degraded=false`。PDF11页已渲染并核对10篇文档页码；Python语法和应用导入已检查。回归测试仅编写，未运行套件，未执行付费模型评测。


## 2026-10-09：一商品一文档发布

商品文档现在覆盖50/50个目录商品，加上2份共享政策，共52个独立PDF和208个原文章节。新增42篇正文逐款撰写；没有通过改商品名的循环模板扩充。现有8篇指南和2篇政策提升文档版本，以区分旧手册页码与独立PDF页码。

文件组织、版本和证据引用一起调整：

- `manifest.json` 记录每篇资料的 `pdf_file`、`pdf_page=1` 和 `pdf_sha256`。检索证据保留这些字段，不再使用汇总手册页码。
- `catalog-snapshot.json` 是这次发布使用的50款商品主数据快照，不含价格和库存。启动时核对摘要及商品文档一对一覆盖，避免漏掉商品或把同一款写两份。
- 文档的适用市场不代表商品在该市场上架；能否销售仍要查询业务API。
- 旧8款汇总手册保留在 `output/pdf/archive/`，不进入当前检索清单。旧渲染命令作为兼容入口，执行时会生成独立资料。
- 渲染器使用固定PDF元数据以便重复构建；超过一页会报错，避免内容增长后悄悄使页码引用失效。未来较长文档需要按章节记录真实页码，不能硬写全部第1页。

发布顺序：修改并审核Markdown及商品主数据快照 → 更新manifest中的版本和源文件摘要 → `python -m scripts.render_commerce_documents` → `.venv/bin/python -m scripts.index_commerce --root fixtures/commerce --dense` → 重启调用方服务。

本轮完成本地向量重建、52份PDF的文本/章节/页码检查和渲染检查。没有运行测试套件或付费质量评测。资料覆盖齐全并不代表每种功能都有事实：没有的防水测试、个人适脚性和认证仍保持未知。

新增资料的真实MCP读取也已检查：RapidWeave清洁查询返回 `rapidweave-guide@1:3`，PDF为 `products/rapidweave-guide.pdf` 第1页，混合检索未降级。可运行 `.venv/bin/python -m scripts.package_commerce_documents` 生成包含52份PDF、52份Markdown和发布清单的便携包 `output/pdf/commerce-documents.zip`。
