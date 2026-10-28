# 从输入 URL 到看到完整页面，发生了什么

先建立全链路：

```text
输入 URL
→ 浏览器解析并检查缓存
→ DNS 解析
→ 建立 TCP/QUIC 连接
→ TLS 握手
→ 发送 HTTP 请求
→ CDN/网关/服务端处理
→ 返回 HTML
→ 浏览器解析 HTML
→ 下载 CSS、JS、图片、字体
→ 构建 DOM 和 CSSOM
→ 执行 JavaScript
→ React Render/Hydration
→ 请求业务数据
→ Layout
→ Paint
→ Composite
→ 页面可见、可交互、稳定
```

“页面加载完成”并不是一个单独时刻：

| 阶段 | 用户感受 |
|---|---|
| TTFB | 浏览器开始收到页面 |
| FCP | 第一次看到内容 |
| LCP | 首屏主要内容出现 |
| 可交互 | 点击、输入可以及时响应 |
| 视觉稳定 | 页面不再明显跳动 |
| `load` | 浏览器认为主要资源加载结束 |

`load` 事件不等于用户体验良好；一个页面可能触发了 `load`，但 JavaScript 长任务仍让用户点不动。

---

# 第一阶段：浏览器解析 URL

用户输入：

```text
https://example.com/dashboard?id=123#chart
```

浏览器解析：

```text
协议：https
域名：example.com
端口：默认 443
路径：/dashboard
查询参数：id=123
Fragment：chart
```

随后检查：

- 是否命中浏览器缓存
- 是否可从内存缓存读取
- 是否存在 Service Worker
- 是否可以使用 BFCache 恢复上一页面
- 是否需要 HSTS 强制 HTTPS
- 是否存在重定向

## 如何排查

在 Network 面板查看：

- 是否出现多次 301/302/307/308
- 是否显示 `from memory cache`
- 是否显示 `from disk cache`
- 是否由 Service Worker 响应
- 是否发生 HTTP → HTTPS 跳转
- 是否发生域名跳转或登录跳转

## 如何优化

- 避免不必要的重定向链
- 直接使用最终 HTTPS URL
- 正确配置静态资源缓存
- 对带内容哈希的静态资源长期缓存
- 谨慎设计 Service Worker
- 确保 SPA 路由不会先 404 再跳转
- 适当利用 BFCache，避免注册会破坏恢复能力的全局行为

坏例子：

```text
http://example.com
→ https://example.com
→ https://www.example.com
→ /login
→ /dashboard
```

每次跳转都可能增加网络往返。

---

# 第二阶段：DNS 解析

浏览器需要把：

```text
example.com
```

转换为 IP 地址：

```text
203.0.113.10
```

可能依次检查：

```text
浏览器 DNS 缓存
→ 操作系统 DNS 缓存
→ 本地网络/运营商 DNS
→ 权威 DNS
```

## 如何排查

Network Timing 中查看 DNS 时间。

也可以对比：

- 首次访问是否慢
- 刷新后是否明显变快
- 不同地区是否差异很大
- 多个第三方域名是否分别产生 DNS 查询

页面如果依赖很多域名：

```text
api.example.com
static.examplecdn.com
fonts.example.com
analytics.vendor.com
editor.vendor.com
```

每个新域名都可能产生额外 DNS 和连接成本。

## 如何优化

- 减少首屏依赖的域名数量
- 静态资源使用可靠 CDN
- 为确定会使用的关键域名添加 DNS 预解析
- 为最关键的跨域资源建立预连接
- 避免给大量不一定使用的域名全部预连接
- 检查全球 DNS 和 CDN 路由质量

```html
<link
  rel="dns-prefetch"
  href="//api.example.com"
/>

<link
  rel="preconnect"
  href="https://api.example.com"
  crossorigin
/>
```

`preconnect` 会提前进行更多连接工作，收益更大，成本也更高，因此只能用于真正关键的域名。

---

# 第三阶段：建立网络连接

## HTTPS over TCP

传统过程大致是：

```text
TCP 握手
→ TLS 握手
→ 安全连接建立
→ HTTP 请求
```

## HTTP/3

HTTP/3 基于 QUIC，使用 UDP，连接建立和丢包恢复机制与 TCP 不同。

无论采用哪种协议，跨地域距离都会影响握手时间。用户在亚洲、服务端在欧洲，物理网络往返无法被前端代码消除。

## 如何排查

Network Timing 查看：

- Initial connection
- SSL
- Stalled/Queueing
- 使用的 HTTP 协议
- 是否复用了已有连接
- 是否频繁创建新连接
- 同一域名下请求是否排队
- 不同地区的连接时延

## 如何优化

- 使用 CDN 或边缘节点
- 启用现代 HTTP 协议
- 开启连接复用和 Keep-Alive
- 减少首屏跨域请求
- 复用已有连接
- 谨慎使用 `preconnect`
- 避免将资源分散到过多域名
- 检查证书链和 TLS 配置
- 将服务部署到更接近用户的位置

---

# 第四阶段：发送 HTTP 请求

浏览器发送：

```http
GET /dashboard HTTP/1.1
Host: example.com
Cookie: ...
Accept-Encoding: br, gzip
```

请求可能经过：

```text
CDN
→ WAF
→ 负载均衡
→ API Gateway
→ Web Server
→ 应用服务
```

## 如何排查

重点观察：

- Request Headers 是否过大
- Cookie 是否被发送到所有请求
- 请求是否排队
- 是否出现跨域预检 OPTIONS
- CDN 是否命中
- 是否存在鉴权跳转
- 是否出现重复请求

## 如何优化

- 缩小 Cookie，限制 Domain 和 Path
- 静态资源域名尽量不携带业务 Cookie
- 减少不必要请求头
- 合理配置 CORS，避免无意义预检
- 合并重复请求
- 使用客户端请求缓存和去重
- 避免组件重复挂载导致相同 API 请求多次发送

---

# 第五阶段：CDN 和服务端处理

请求可能先命中 CDN：

```text
命中缓存
→ CDN 直接返回

未命中
→ CDN 请求源站
→ 源站处理
→ CDN 返回并可能缓存
```

源站内部可能执行：

```text
身份认证
→ 权限校验
→ 数据库查询
→ 调用其他微服务
→ 页面渲染
→ 返回 HTML
```

这里最重要的指标是 TTFB：从发出请求到收到第一个响应字节的时间。

## 如何排查

仅靠浏览器只能知道“等待响应很长”，不能知道服务端内部慢在哪里。

需要结合：

- CDN 命中率
- 服务端日志
- APM
- 分布式追踪
- 数据库慢查询
- 上游服务耗时
- Server-Timing 响应头
- 请求 ID

理想追踪：

```text
浏览器请求：1,200ms
├─ CDN：20ms
├─ Gateway：10ms
├─ Auth：30ms
├─ 应用服务：1,100ms
│  ├─ DB Query A：600ms
│  ├─ Service B：300ms
│  └─ Template Render：80ms
└─ 其他：40ms
```

## 如何优化

- CDN 缓存公开内容
- 服务端缓存高频数据
- 数据库增加合理索引
- 消除 N+1 查询
- 并行调用无依赖服务
- 为上游设置超时和降级
- 避免 SSR 等待非首屏数据
- 流式返回可以提前展示的区域
- 服务端开启压缩
- 避免返回远超首屏需求的数据
- 优化冷启动和连接池

---

# 第六阶段：接收 HTML

浏览器收到 HTML 后，不需要等待整个文件下载完成才开始解析；通常会边接收边解析。

服务端越早返回有效 HTML，浏览器越早发现后续资源。

## 如何排查

查看：

- HTML 的 TTFB
- Content Download 时间
- HTML 体积
- 是否经过压缩
- `<head>` 中是否有大量阻塞内容
- 关键资源是否很晚才被发现
- HTML 是否只是一个空的 root

典型 CSR HTML：

```html
<body>
  <div id="root"></div>
  <script src="/app.js"></script>
</body>
```

用户必须等 JS 下载、解析、执行并请求数据后，才看到真实内容。

## 如何优化

- 压缩 HTML
- 尽早输出页面框架
- SSR/SSG 返回首屏内容
- 使用流式响应
- 将关键资源声明放得更早
- 不在 `<head>` 放大量同步脚本
- 不让服务端等待非关键区域
- 避免过大的内联 JSON

---

# 第七阶段：解析 HTML，构建 DOM

HTML Parser 将文本转成 DOM：

```html
<body>
  <main>
    <h1>Dashboard</h1>
  </main>
</body>
```

变成：

```text
Document
└── body
    └── main
        └── h1
            └── "Dashboard"
```

浏览器还有预加载扫描器，会尽早发现：

- CSS
- JavaScript
- 图片
- 字体预加载
- module preload

## 什么会阻塞 HTML 解析

普通同步脚本：

```html
<script src="/large.js"></script>
```

Parser 需要暂停，等待脚本下载并执行。

## 如何优化

对不要求立即执行的脚本使用：

```html
<script defer src="/app.js"></script>
```

模块脚本通常也具有延迟执行特性：

```html
<script type="module" src="/app.js"></script>
```

`async` 更适合不依赖页面解析顺序的独立脚本：

```html
<script async src="/analytics.js"></script>
```

区别：

- `defer`：解析完成后按顺序执行
- `async`：下载完成后尽快执行，不保证顺序
- 普通 script：可能阻塞 HTML Parser

分析脚本适合 `async`，依赖 DOM 和执行顺序的应用脚本通常更适合 `defer` 或 module。

---

# 第八阶段：下载 CSS 并构建 CSSOM

CSS 被解析成 CSSOM：

```css
.card {
  color: red;
}
```

浏览器需要 DOM 和 CSSOM 才能正确决定页面如何显示。

CSS 通常是渲染关键资源，过大的 CSS 或慢速 CSS 会延迟首屏绘制。

## 如何排查

查看：

- CSS 文件体积
- CSS 请求开始时间
- 是否跨域
- 是否有大量未使用 CSS
- 是否存在 `@import` 瀑布
- CSS 下载是否阻塞关键内容
- 运行时 CSS-in-JS 初始化成本
- 样式计算是否很慢

Coverage 可以帮助识别首屏未使用的 CSS。

## 如何优化

- 删除未使用 CSS
- 压缩 CSS
- 拆分路由级样式
- 避免 CSS `@import` 造成串行发现
- 关键 CSS 尽早加载
- 非关键样式延后
- 减少复杂选择器
- 控制 CSS-in-JS 的运行时成本
- 不要把整个组件库样式都打进首屏

---

# 第九阶段：下载和执行 JavaScript

JavaScript 的成本包括：

```text
下载
→ 解压
→ 解析
→ 编译
→ 执行
```

低端设备上，即使下载很快，大 Bundle 的解析和执行仍可能非常慢。

## 如何排查

### Network

检查：

- JS 传输体积
- 请求数量
- 是否命中缓存
- 是否存在重复依赖
- 是否加载了当前页面不需要的代码

### Performance

检查：

- Evaluate Script
- Compile Script
- Long Task
- 哪个函数占用主线程
- 应用启动期间是否存在连续长任务

### Bundle Analyzer

检查：

- 图表库
- 富文本编辑器
- 日期库
- 代码编辑器
- 整库导入
- 重复版本
- 调试代码
- 不必要 Polyfill

## 如何优化

- 路由级代码分割
- 重组件懒加载
- Tree Shaking
- 删除重复依赖
- 精确导入模块
- 非首屏功能延迟初始化
- 减少运行时配置转换
- 将重计算移到 Web Worker
- 使用缓存和内容哈希
- 控制第三方脚本

---

# 第十阶段：React 启动

根据架构不同，有两条路线。

## CSR

```text
HTML 中只有 root
→ 下载 JavaScript
→ 创建 React Root
→ 执行组件
→ 生成 DOM
→ 页面出现
```

## SSR + Hydration

```text
服务端已返回 HTML
→ 用户先看到内容
→ 下载 JavaScript
→ React Hydration
→ 绑定事件并恢复交互
```

SSR 可以让内容更早出现，但 Hydration 仍然有成本。

如果 Hydration 很慢，用户会感受到：

```text
页面已经显示
但点击没有响应
```

## 如何排查

使用 React Profiler 和 Performance 检查：

- 首次 render 时间
- Hydration 时间
- 哪些组件首次挂载最慢
- 是否挂载了不可见组件
- 是否在 render 中做重计算
- Context Provider 是否引发大范围渲染
- SSR 是否出现 hydration mismatch
- Strict Mode 是否让开发环境现象产生误导

## 如何优化

- 减少首屏组件数量
- 不挂载隐藏 Tab 和弹窗
- 图表、编辑器、画布按需加载
- 将局部状态下沉
- 避免 render 中处理超大数据
- 减少首屏 Provider 层和初始化逻辑
- SSR 只输出必要内容
- 避免服务端和客户端首屏结果不一致
- 把非关键交互延迟到页面可用之后
- 使用更细粒度的渲染和 Hydration 边界

---

# 第十一阶段：请求业务数据

很多 React 页面显示框架后，还会发起 API 请求：

```text
App mount
→ 请求用户
→ User 返回
→ 请求权限
→ Permission 返回
→ 请求项目
→ Project 返回
→ 请求 Dashboard
```

这是请求瀑布。

## 如何排查

Network Waterfall 中观察：

- 请求是否一个接一个开始
- 后一个请求是否真的依赖前一个
- 是否由嵌套组件 Effect 逐层触发
- 是否有相同请求重复发送
- API 是否返回过多数据
- 是否有慢接口
- 是否等待了非关键数据
- 是否缺少缓存

## 如何优化

### 并行请求

```tsx
const [user, config, projects] =
  await Promise.all([
    fetchUser(),
    fetchConfig(),
    fetchProjects()
  ]);
```

### 路由层统一预取

不要等组件逐层挂载后再请求。

### 服务端聚合

为高度稳定的首屏数据设计适当聚合接口。

### 缓存与去重

```text
先显示已有缓存
→ 后台重新验证
→ 更新新数据
```

### 分页和渐进加载

```text
先加载当前会话最近 30 条消息
→ 用户向上滚动
→ 再加载历史消息
```

### SSR/服务端预取

首屏必需数据可以在服务端获取，与 HTML 一起返回。

---

# 第十二阶段：图片和字体

## 图片

图片下载后还需要：

```text
解码
→ 确定尺寸
→ 绘制
```

## 排查

- 图片是否远大于显示尺寸
- 是否使用合适格式
- 首屏主图是否很晚才请求
- 是否错误地对首屏关键图使用懒加载
- 是否没有声明宽高导致布局跳动
- 图片解码是否阻塞主线程

## 优化

- 响应式图片
- 合理尺寸
- 现代格式
- CDN
- 压缩
- 非首屏图片懒加载
- 首屏关键图片提高优先级
- 设置 width/height 或 aspect-ratio
- 避免 Base64 内联大型图片

## 字体

字体可能导致：

- 文字暂时不可见
- 字体切换造成布局变化
- 大型中文字体下载缓慢

优化：

- 减少字重
- 字体子集化
- 使用系统字体作为合理降级
- 合理配置字体显示策略
- 只预加载真正关键字体
- 避免加载完整大型中文字体

---

# 第十三阶段：构建 Render Tree

浏览器结合：

```text
DOM + CSSOM
```

生成 Render Tree。

以下节点通常不会进入实际渲染树：

```css
display: none;
```

浏览器需要计算：

- 哪些节点可见
- 每个节点应用哪些样式
- 继承和层叠结果

## 如何排查

Performance 中关注：

- Recalculate Style
- 样式计算耗时
- DOM 节点数量
- 复杂选择器
- 一次 state 更新影响多少节点

## 如何优化

- 减少 DOM 数量
- 虚拟化长列表
- 避免极其复杂的 CSS 选择器
- 限制变化影响范围
- 不同时挂载所有隐藏页面
- 对独立复杂区域进行适当隔离
- 避免在根节点频繁切换影响整页的 class

---

# 第十四阶段：Layout

Layout 计算元素的位置和大小：

```text
x、y、width、height
```

修改这些属性经常触发布局：

- width
- height
- margin
- padding
- top/left
- 字体尺寸
- DOM 结构

## 强制同步布局

```tsx
element.style.width = "200px";
const height = element.offsetHeight;
element.style.width = "300px";
const newHeight = element.offsetHeight;
```

在写入和读取布局之间反复切换，可能迫使浏览器立即重新计算。

## 如何排查

Performance 中查看：

- Layout
- Forced Reflow
- Layout Shift
- 具体触发调用栈
- 一次布局影响的节点数

## 如何优化

- 批量读取，再批量写入
- 避免循环中交替读写布局
- 图片和图表提前预留尺寸
- 虚拟化大型列表
- 限制 DOM 规模
- 动画优先使用 `transform`
- 避免用 JavaScript 持续查询和修改布局
- 尽量让布局变化局限在局部区域

---

# 第十五阶段：Paint

Paint 将元素绘制成像素，包括：

- 文字
- 背景
- 边框
- 阴影
- 图片
- 渐变

## 如何排查

Performance 和 Rendering 工具查看：

- Paint 时间
- Paint flashing
- 哪些区域被反复重绘
- 是否存在超大绘制区域
- 阴影、模糊等效果是否昂贵
- Canvas 是否频繁全量重绘

## 如何优化

- 缩小重绘区域
- 避免大面积高频样式变化
- 减少昂贵视觉效果
- Canvas 只重绘变化区域
- 图表更新进行批处理
- 对复杂内容按需展示
- 避免每个 token 引发整个消息列表重绘

---

# 第十六阶段：Composite

浏览器可能把页面划分成多个图层，合成线程将它们组合成最终画面。

`transform` 和 `opacity` 动画通常更容易只经过合成，而不重新 Layout 和 Paint。

## 如何排查

- Layers 面板
- Composite Layers 耗时
- 是否创建过多图层
- 动画是否触发 Layout/Paint
- GPU 内存是否过高

## 如何优化

- 动画优先使用 `transform` 和 `opacity`
- 不要到处滥用 `will-change`
- 避免创建大量独立图层
- 控制超大图层尺寸
- 将高频动画与主内容隔离

`will-change` 不是免费优化，它会消耗额外内存。

---

# 第十七阶段：Effect、订阅和增量内容

React Commit 后还可能执行：

- `useLayoutEffect`
- 浏览器绘制
- `useEffect`
- API 请求
- WebSocket/SSE 连接
- 埋点
- 第三方组件初始化

如果把大量初始化工作放在首屏 Effect 中，即使内容已经出现，也可能堵塞主线程。

## Agent 产品中的典型问题

```text
首屏完成
→ 建立 SSE
→ 加载全部历史消息
→ 解析全部 Markdown
→ 为每段代码进行高亮
→ 初始化图表
→ 渲染 Tool JSON
```

用户会看到页面，但操作卡顿。

## 如何优化

- 首屏只加载最近消息
- 历史消息按需加载
- SSE 事件缓冲和批处理
- 已完成消息缓存 Markdown 结果
- 代码高亮延迟处理
- Tool JSON 默认折叠
- 图表进入视口再初始化
- 非关键埋点延迟
- CPU 密集任务放 Worker

---

# 如何系统排查：完整流程

## 第一步：稳定复现

确定：

- 哪个页面
- 哪类用户
- 哪个地区
- 什么设备
- 什么网络
- 首次访问还是二次访问
- 登录前还是登录后
- 是否有缓存

分别测试：

```text
冷缓存 + 慢速网络 + 中低端 CPU
热缓存 + 正常网络
真实线上用户环境
```

---

## 第二步：判断是后端慢还是前端慢

### HTML TTFB 很长

优先查：

- CDN
- Gateway
- SSR
- 数据库
- 上游服务
- 服务端缓存

### HTML 很快，内容很晚出现

优先查：

- JS Bundle
- CSR 启动
- CSS
- 首屏 API 瀑布
- React 初次渲染
- 图片和字体

### 内容出现但不能操作

优先查：

- JavaScript Long Task
- Hydration
- 图表或编辑器初始化
- 大数据计算
- 第三方脚本

---

## 第三步：阅读 Network Waterfall

按照时间顺序问：

1. 有没有重定向？
2. DNS、连接和 TLS 是否慢？
3. HTML TTFB 是否慢？
4. CSS/JS 是否很晚才开始下载？
5. 哪些资源阻塞首屏？
6. 是否存在大 Bundle？
7. 是否存在请求瀑布？
8. 图片或字体是否过大？
9. 是否命中缓存？
10. 是否有重复请求？

---

## 第四步：检查主线程

在 Performance Timeline 中查找：

- 连续长任务
- Script Evaluation
- JSON parsing
- Recalculate Style
- Layout
- Paint
- 第三方脚本
- React 初始化
- 图表、编辑器或 Markdown 处理

判断：

```text
网络空闲但页面仍然卡
→ 很可能是 CPU/主线程问题
```

---

## 第五步：检查 React

通过 Profiler 回答：

- 首次挂载哪些组件最慢？
- 哪些不可见组件被提前挂载？
- 哪个 state 更新导致大范围渲染？
- Context 是否包含高频数据？
- 是否重复计算派生数据？
- 长列表是否全部进入 DOM？
- 图表 props 是否每次产生新引用？
- 流式 token 是否引发整页重渲染？

---

## 第六步：真实用户监控

本地测试不能代表：

- 海外用户
- 弱网用户
- 低端设备
- 冷缓存
- CDN 特定节点
- 真实数据规模

前端埋点至少关联：

```text
页面
地区
设备
网络
版本
用户类型
TTFB
关键内容出现时间
交互延迟
布局偏移
接口耗时
错误
```

再结合 Request ID 和分布式追踪，实现：

```text
前端慢请求
→ Gateway
→ 服务
→ 数据库/下游
```

---

# Agent 数据平台的完整首屏设计

推荐分层加载：

```text
第一层：立即展示
导航、标题、输入框、基础布局

第二层：并行加载
用户权限、会话列表、Agent 基本配置

第三层：渐进加载
当前会话最近消息、引用和 Tool 状态

第四层：按需加载
历史消息、图表、工作流编辑器、代码高亮

第五层：空闲加载
调试面板、非关键埋点、低频资源
```

不要把“所有资源加载完成”当作首屏目标。正确目标是：

> 优先让用户看到并操作核心功能，非关键内容在不阻塞交互的前提下渐进到达。

---

# 面试中的 2 分钟回答

> 从用户输入 URL 开始，浏览器会先解析 URL，检查缓存、Service Worker 和重定向；随后进行 DNS 解析，建立 TCP 或 QUIC 连接和 TLS 安全连接，再发送 HTTP 请求。请求可能经过 CDN、网关和负载均衡，最终由服务端完成鉴权、查询和页面渲染并返回 HTML。  
>
> 浏览器边接收边解析 HTML，构建 DOM，同时由预加载扫描器发现 CSS、JavaScript、图片和字体。CSS 被解析成 CSSOM，JavaScript则经历下载、解析、编译和执行。对于 React CSR，必须等应用 JavaScript 启动后才能生成主要 DOM；对于 SSR，HTML 可以先显示，但之后仍需要 Hydration 恢复交互。组件还可能发起业务数据请求，最终浏览器将 DOM 和 CSSOM 转成 Render Tree，依次完成样式计算、Layout、Paint 和 Composite。  
>
> 排查时，我首先用真实用户数据确定是内容出现慢、交互慢还是页面不稳定，再查看 Network Waterfall，判断问题位于重定向、DNS、连接、TTFB、资源下载还是 API 瀑布。如果网络完成后仍然卡顿，就用 Performance 检查 JavaScript 长任务、Layout 和 Paint，并用 React Profiler 定位慢组件和大范围重渲染。  
>
> 优化遵循关键路径原则：服务端降低 TTFB，静态资源使用 CDN 和缓存，减少首屏 JavaScript，路由级拆包，消除请求瀑布，优化关键图片和字体，避免挂载不可见重组件，大列表虚拟化，CPU 密集工作放到 Worker。最后用相同环境复测，并通过线上监控确认真实用户确实受益。