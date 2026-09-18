# 供应商级并行采集 + news 文章章节导航 设计 spec

- 日期：2026-09-18
- 状态：已获用户批准（设计呈现 → 「没问题，继续」）
- 来源：用户提供完整方案文档 + 实现层定案补充（第二节）
- 提交基线：d071f85（main = origin/main）

## 0. 背景与目标

两项独立优化，各自独立提交：

1. **采集调度**：Qwen/Doubao/GLM 三家按供应商并行——一家等待响应或退避重试时，不占用另外两家的执行机会。
2. **站点导航**：全部 8 篇 news 文章增加统一章节目录（TOC），并为后续文章提供统一接入方式；news 列表页保持现状。

## 1. 范围与边界

| 模块 | 本次处理 |
|---|---|
| GEO Collect（collector.py） | 修改任务调度 |
| LangGraph 编排 | 保持节点顺序与质量门（不动） |
| Fetch / Snapshot | 检查导航对结构计数的影响（不改口径） |
| Assess / Research / RulesKeeper | 不修改算法与历史数据 |
| Generate | 保留现有人工发布边界（不扩展自动发布） |
| Astro 站点 | 新增布局与目录组件，8 篇文章接入 |
| Tests / CI | 增加与本次行为直接相关的验收 |

**不改动**：模型版本、提示词、评分规则、历史快照、文章事实内容；不自动运行生产周采集；不自动部署站点；不推送远端（时机由用户定）。

**工作树既有未跟踪/已修改文件**（`docs/ppt-*` 三目录、演讲文稿、`docs/SunPower Nova项目信息概览.html`、`geo-agent/scripts/gsc_page_impressions_probe.py`）一律不碰、不入提交；提交只显式 add 本方案涉及文件。

## 2. 现状核实（2026-09-18，全部成立）

- `geo-agent/src/geo/collect/collector.py:124,138`：jobs 按 `for m in models` 展开（全 qwen → 全 doubao → 全 zhipu），单一 `ThreadPoolExecutor(max_workers=3)` 一次全量 submit。
- `collector.py:135`：todo 整体先注册 `planned`（崩溃也在分母）；`collector.py:140-149`：`as_completed` 循环内即时 append `ok/failed`。
- `collector.py:43-53`：重试（3 次/8s，传输类才重试）发生在工作线程内 → 新设计下退避天然不阻塞他家。
- 质量门：`collection_health` per-model `min_success_rate`（门在 graph 侧 collect_node，本次不动）。
- 站点：8 篇文章 H2/H3 计数与方案表逐篇一致（3/0、3/0、8/4、4/9、5/7、5/6、9/6、6/7）；Header `position:sticky; height:64px`（global.css:62,73）；色板 `--c-*` 齐备；`prefers-reduced-motion` 钩子已有（global.css:319）。
- `.wrap` = `max-width: var(--maxw)` + padding 24px（global.css:54）；`.prose` 自身 `max-width:760px`（global.css:495）——两栏布局须避免嵌套收窄。
- `astro.config.mjs:13-18`：lastmod 只追踪 shared-chrome 四文件（Layout/Header/Footer/global.css）。
- CI site job（ci.yml:44-50）= `npm ci` → `astro check` → build；TOC 检查可作第四步接入。

## 3. 优化一：供应商级并行采集

### 3.1 设计

保留同步客户端与线程池，改为主循环补位调度器：

1. 沿用现有问题筛选、有效 L1 跳过（`skipped_exists`）、待采任务生成逻辑——**逐行不动**。
2. 发起任何请求之前，todo 全量写入 `planned` 清单（现状保持）。
3. todo 按供应商分成三个队列。
4. 初始为每个非空队列 submit 首条任务；主线程 `concurrent.futures.wait(..., return_when=FIRST_COMPLETED)` 等待任意完成。
5. 完成即由**主线程** append `ok` 或 `failed` 记录，随后 submit **同一家**下一条任务；该家队列空则不再提交。
6. 一家队列完成后，另外两家继续独立运行。
7. 全部结束后返回；每家成功率检查（≥95% 门）沿用现状，不动。

并发上限由结构保证：每家最多 1 个在途任务（调度器只在家内补位），总数最多 3（`max_workers=3` 兜底）。

### 3.2 必须保留的行为

- `run_collection()` 调用接口与返回类型（`list[RunRecord]`）。
- 供应商键名 `qwen` / `doubao` / `zhipu`（CLIENTS 字典语义）。
- 原有模型、提示词、联网参数及引用解析语义（`_one` / `parse_l2` 不动）。
- 传输错误重试规则（`_collect_with_retry`：3 次/8s、传输类才重试）与配额/鉴权类错误的现有处理。
- 有效文件跳过、空文件或截断文件重采（`_l1_valid` 判据不动）。
- 单条任务完成立即落 manifest，不等整家完成。
- 一条失败不取消其他任务；失败不从质量门分母消失（planned 先注册语义不动）。
- 主线程汇总结果并写清单；工作线程只负责单条采集与对应 L1 保存。

### 3.3 日志

每任务开始/结束各一条 `log.info`：供应商、prompt_id、run、状态、单条耗时；整轮一条总耗时。不输出密钥或完整响应。

### 3.4 性能预期（诚实声明）

新方案保证跨供应商并行与相互隔离，**不保证固定倍数提速**。现状同一家可同时跑 3 个请求；改为每家 1 个在途后，若某一家明显更慢，总耗时也可能增加。验收记录实际耗时，不预宣称「提升三倍」。真实接口性能留待生产周实跑观察，本次不调用付费接口。

## 4. 优化二：news 文章章节导航

### 4.1 组件

- `site/src/layouts/NewsArticleLayout.astro`：包现有 `Layout`（title/description/path/ogImage/jsonLd/noindex 原样透传——canonical 语义 post-d071f85 不受影响）；新增 prop `toc: Array<{ id: string; text: string; depth: 2 | 3 }>`。内部两栏 grid：`<nav>`（TOC 列）+ 正文列（`<slot/>`）。
- `site/src/components/ArticleToc.astro`：渲染目录链接、当前位高亮脚本、移动端折叠。
- 页面迁移：`<Layout ...><section class="section"><div class="wrap prose">` → `<NewsArticleLayout ... toc={[...]}><div class="prose">`（`section/wrap` 上移进布局，避免双 max-width 嵌套收窄；`.prose` 760px 上限保留）。页面级 scoped `<style>`（表格/H3）因内容仍由页面组件渲染而继续生效。
- 目录数据 = 页面内显式 `{ id, text, depth }` 数组；正文对应 H2/H3 添加稳定 `id`。8 篇静态文章，不迁移 Markdown、不引 CMS、不加 HTML 解析依赖。

### 4.2 交互与样式

- 桌面端左目录、右正文两栏，沿用 SunHestia 颜色字体与正文风格。
- TOC 列 `position: sticky`，`top` 偏移避开 64px 顶部导航；过长独立滚动（`max-height` + `overflow-y: auto`）。
- H2 一级条目、H3 缩进；顺序与正文一致。
- 原生 `href="#章节ID"`：复制链接、刷新定位、前进后退均可用；不劫持滚动。
- 正文 `h2[id]/h3[id]` 设 `scroll-margin-top`（约 88px，含 header + 余量），跳转不被遮。
- 滚动高亮当前位：`aria-current="location"`；正确处理页顶、长章节间隙、文末。
- 移动端：正文上方可折叠「On this page」，用原生 `<details>` 实现——**禁 JS 可展开可跳转**；脚本只增强高亮。
- 键盘可操作、可见焦点（`:focus-visible`）；`prefers-reduced-motion` 下不启用平滑滚动。
- 打印隐藏目录、正文恢复单栏（`@media print`）。

### 4.3 实现注意事项

1. 目录位于正文 `<article>` 等价容器之外，`<nav>` 带可访问名称（aria-label）。
2. 目录标题不用 H2/H3（非 heading 元素），不增加正文标题计数。
3. GEO 抓取器统计整页 `ul/ol`：目录用 `<a>` + 样式缩进表达层级，**不用列表元素**；不改抓取与评分口径。
4. H1/H2/H3、表格、列表计数与修改前一致（构建产物 diff 验证）。
5. 保留各篇文章已有表格、局部样式、正文内容、日期、链接、canonical、OG 和 JSON-LD。
6. Astro scoped CSS 在组件嵌套后的作用范围须验证（slot 内容保持页面 scope；布局对 slot 内标题的作用用 `:global` 限定选择器）。
7. `astro.config.mjs`：新增 news 专属依赖组（NewsArticleLayout + ArticleToc 的 mtime 只计入 `/news/` 路径的 lastmod）；**不**加入 sharedChrome——目录组件变化不刷新全站其他页面。
8. 后续新增文章使用该布局并填写目录；Generate 发布功能维持 Markdown 归档，不扩展为自动建页。

## 5. 验收标准

### 5.1 采集（临时目录 + 模拟客户端，不调付费接口、不写生产周数据）

| 场景 | 必须通过的结果 |
|---|---|
| 三家均有多条任务 | 首批请求包含三家，不能全部属于一家 |
| 并发上限 | 每家最多一个在途任务，总数最多三个 |
| 某家请求被阻塞 | 另外两家可完成多条任务 |
| 某家正在退避重试 | 不阻塞另外两家继续采集 |
| 一条任务失败 | 失败立即记录，其余任务继续 |
| 部分 L1 已存在 | 只采缺失或无效记录 |
| 某家全部已完成 | 不再调用该家接口 |
| 全部任务已完成 | 不发起请求，保持续跑行为 |
| 多次 run、供应商子集 | 任务不遗漏、不重复 |
| 质量门 | 失败仍在分母中，低于 95% 仍阻断后续节点 |

并发测试用 Event/Barrier 同步 + 有界等待（不得仅靠短暂 sleep 或运行速度判断并发）。

### 5.2 站点

- **构建产物检查**（脚本 `site/scripts/check-news-toc.mjs`，零新依赖，接入 `npm run checktoc` 与 CI）：遍历全部 news 文章——目录存在、ID 唯一、所有链接命中对应标题、文字及层级顺序一致；无 JS 时目录已在静态 HTML 中；正文与元信息无意外修改（对照修改前构建产物 diff：仅新增 TOC 标记、heading id 与布局容器调整，文本/表格/列表/元信息零变化）。
- **浏览器检查**（预览关口）：覆盖短文、长文、含表格及多级标题文章；桌面/平板/手机宽度的吸顶、目录滚动、当前位、深链、前进后退、折叠、键盘、横向溢出。

导航相关 H1/H2/H3、表格、列表计数与修改前一致。目录文字仍可能影响文本抽取——部署后评分变化不得直接归因为内容质量提高。

### 5.3 回归

- Python 全量：`cd geo-agent && PYTHONPATH=~/pylibs312:src python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120`（EXIT=0）。
- 站点：`npm run check`（0/0/0）+ `npm run build` + `npm run checktoc`。
- 不以构建成功作为导航功能验收的替代。

## 6. 执行顺序与交付

1. 本 spec 提交（docs(spec)）。
2. 实施计划（writing-plans 产物）提交。
3. **采集调度 + 针对性测试 → 独立提交**（Python 全量绿后）。
4. 最长文章（home-solar-battery-deep-dive，9 H2/6 H3）建立导航样例 → 本地 build + 桌面/移动截图**预览给用户确认** → 通过后迁移剩余 7 篇。
5. 全量目录检查 + 回归 + 构建 → **站点独立提交**。
6. 交付：修改清单、测试结果、页面预览、尚未验证的真实接口性能说明。

提交策略：main 直接提交（近例 d071f85/a808ca8 模式），不推送、不部署；提交只显式 add 涉及文件。

## 7. 决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | 调度器 = 单池 + 主循环 FIRST_COMPLETED 补位（每家初始 1 条，完成即记录并补同家下一条） | 方案 §3.5 字面语义；对现有代码最小 diff |
| D2 | 移动端折叠用原生 `<details>` | 禁 JS 可展开的标准解 |
| D3 | TOC 检查 = 独立 Node 脚本扫 dist + CI site job 第四步 | 零依赖、真门禁（不以 build 成功替代） |
| D4 | lastmod news 专属依赖组，不进 sharedChrome | 目录组件变化不刷全站 lastmod |
| D5 | TOC 标记不用 ul/ol/heading | 守住 GEO 结构计数（方案 §4.3.3） |
| D6 | 预览关口 = 样例文章桌面+移动截图，用户确认后再迁移 7 篇 | 方案 §5.2 执行顺序 |
| D7 | spec+plan 先行各自提交；实现分两个独立提交；不推送不部署 | 本仓惯例 + 方案 §5 |
