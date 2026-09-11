<div align="center">

# ☀️ SunPower Nova

**从“建设一个网站”，到“打造一套可复现、可持续自我迭代的 GEO 工程”。**

以 SunHestia 为真实运行载体，持续采集 AI 回答、还原引用证据、诊断内容差距、生成受控草稿，并用下一周的数据检验调整效果，让 GEO 在证据驱动下不断自我迭代。

[SunHestia](https://sunhestia.com) · [项目成果](#outcomes) · [闭环流程](#workflow) · [快速开始](#quick-start) · [文档地图](#docs)

![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.12-3776AB?logo=python&logoColor=white)
![Astro](https://img.shields.io/badge/Astro-5-BC52EE?logo=astro&logoColor=white)
![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-1C3C3C)
![System](https://img.shields.io/badge/System-Iterative_GEO-F5A623)

</div>

> [!IMPORTANT]
> SunPower Nova 是一套由真实数据和证据驱动、能够持续自我迭代的 GEO 工程。它不是一次性的内容优化项目，也不是商业增长归因系统。模型提及率、引用率、GEO 分和 SEO 分用于定位问题、驱动下一轮行动，不能直接解释为自然曝光、转化或收入增长。

## 为什么做 SunPower Nova

用户获取信息的入口正在从传统搜索扩展到生成式搜索。对一个新品牌而言，问题不再只是“网页能不能被搜索到”，还包括：

- AI 是否能理解品牌与产品；
- AI 是否会在相关问题中提到品牌；
- AI 是否愿意把品牌页面作为答案来源引用；
- 内容调整之后，这些变化能否被持续测量和复核。

SEO 为内容建立**可抓取、可理解、可信**的基础；GEO 在此之上，提高优质内容进入 AI 答案并获得提及与引用的机会。

传统 GEO 工作往往依赖人工提问、复制答案和主观判断。搜索候选、品牌复述与真实引用容易混在一起，模型、提示词、网页和规则的变化也会让周与周无法比较。SunPower Nova 要解决的，就是把这项工作从一次性优化升级为一套有原始证据、有质量门、有版本记录，并能持续学习和自我迭代的工程闭环。

<a id="outcomes"></a>

## 项目交付了什么

项目由两个互补部分组成：

| 部分 | 角色 | 主要产物 |
| --- | --- | --- |
| [`site/`](site/) | 真实运行载体与内容阵地 | SunHestia 英文静态站、产品与住宅方案页面、知识内容、结构化数据 |
| [`geo-agent/`](geo-agent/) | GEO 自我迭代的工程底座 | 模型采集、证据解析、来源抓取、快照、评估、研究、生成、规则迭代与周报 |

截至 2026-09-11 的仓库快照：

| 已交付资产 | 当前状态 |
| --- | ---: |
| SunHestia 静态页面 | 19 页 |
| GEO 闭环功能环节 | 8 个 |
| 正式 HTML 周报 | W1–W5，共 5 份 |
| GEO / SEO 规则版本 | `geo-seo-v1`–`geo-seo-v6`，共 6 个版本 |
| 通过事实校验与人工审核的发布归档 | 5 篇 |
| W5 核心采集 | 45 / 45 条有效 |

这些数字证明的是站点、工程系统和持续迭代资产已经形成，不等同于品牌增长已经被证明。

### 同一套闭环服务四类工作

| 角色 | 获得的支持 |
| --- | --- |
| 运营 / 项目负责人 | 从周报查看采集质量、模型提及、答案引用、GEO / SEO 诊断与优先动作 |
| 内容负责人 | 从真实来源样本中获得选题、格式建议、草稿和事实核对清单 |
| 技术维护者 | 通过断点续跑、失败隔离、输入快照、版本化、测试与 CI 维持稳定运行 |
| 决策者 | 区分确定性事实、代理指标、观察性相关与证据不足的结论 |

## 系统如何组成

| 层级 | 组成 | 职责 |
| --- | --- | --- |
| 运行载体 | SunHestia 官网 | 承载品牌、产品、FAQ、资源与 GEO 优化内容，也是持续观察和迭代的对象 |
| 数据与执行 | GEO Agent | 把真实模型回答和网页来源转化为可计算、可复现的数据 |
| 知识与规则 | Knowledge + Rules | 保存品牌事实、内容 Playbook、平台画像和 GEO / SEO 规则版本 |
| 质量与治理 | Tests + CI + 人工关口 | 约束工具调用、外部 URL、数字事实、回归风险和最终发布责任 |

网站因此不只是一个静态交付物，而是 GEO 工程的真实运行载体：它接收外部模型反馈、承接内容动作、沉淀知识，并持续进入下一轮验证与迭代。

<a id="workflow"></a>

## 从真实回答到下一轮验证

当前实现由 8 个 LangGraph 节点组成。主线是自动周迭代；虚线表示下一周反馈，以及 DAG 之外的人工审核与独立发布。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/workflow-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/readme/workflow-light.svg">
  <img src="docs/assets/readme/workflow-light.svg" alt="SunPower Nova 周迭代流程：观察、诊断、行动、学习四个阶段依次覆盖 Collect、Fetch、Snapshot、Assess、Research、Generate、RulesKeeper 和 Report；生成的草稿经过人工审核后独立发布到 SunHestia。">
</picture>

1. **采集 Collect**：用固定问题集调用 Qwen、Doubao、Zhipu 的官方联网能力，保留回答原文和调用元信息。
2. **抓取 Fetch**：标准化不同平台的来源字段，并抓取允许访问的外部页面。
3. **快照 Snapshot**：冻结当周来源、GSC 和站点信号，避免未来重算读取已经变化的输入。
4. **评估 Assess**：分别计算品牌、引用、GEO 六维和 SEO 五项指标，不合成一个失真的总指标。
5. **研究 Research**：从回答、来源正文和查询中归纳页面类型、内容格式、平台差异与主题缺口。
6. **生成 Generate**：依据 Playbook 与品牌事实库生成草稿，并校验数字声明与结构化数据。
7. **规则 RulesKeeper**：根据样本量、覆盖率、跨平台证据和连续周次决定规则是否晋升或调整权重。
8. **报告 Report**：输出中文 HTML 周报，公开采集质量、诊断结果、降级事件和规则变化。

草稿不会自动上线。只有通过事实校验和人工审核的内容，才会独立发布到 SunHestia，并在下一周重新进入采集与评估。

### 一条数据如何保持可追溯

| 层级 | 位置 | 保存内容 |
| --- | --- | --- |
| L1 | `geo-agent/data/raw/w{N}/` | 回答原文、模型元信息、耗时与用量 |
| L2 | L1 记录中的 `l2` | `cited_sources`、`retrieved_sources`、品牌与竞品派生字段 |
| L3 | `geo-agent/data/sources/w{N}/` | 来源正文、页面结构、语义信号与降级状态 |
| Snapshot | `geo-agent/data/snapshots/w{N}/` | 当周 GSC 与站点静态快照 |
| Analysis | `geo-agent/data/analysis/w{N}/` | 评估、来源研究与规则迭代结果 |
| Report | `geo-agent/reports/w{N}/report.html` | 面向人工复核与决策的周度仪表盘 |

## 当前数据说明了什么

W5 的结果更适合被看作一次诊断，而不是一张成绩单：

| 指标 | W5 观测 |
| --- | ---: |
| 采集完成率 | 100%，45 / 45 条有效 |
| GEO 诊断分 | 43.3 / 100 |
| SEO 诊断分 | 49.9 / 100 |
| Doubao / Qwen / Zhipu 表面品牌提及率 | 均为 13.3% |
| Doubao / Qwen / Zhipu 答案引用率 | 0% / 6.7% / 13.3% |

目前可以确认：核心采集链路能够完整运行，站点已具备基本的机器可读性，系统也能定位内容可信度、外部权威和平台覆盖等短板。

目前不能确认：13.3% 的表面提及率不等于非品牌问题中的自然发现；GEO / SEO 诊断分不等于流量或收入；来源中常见的列表、规格卡或定义段属于观察性线索，缺少同查询、同平台的对照数据时不能宣称因果关系。

## 可信度不是来自一张图表

- **采集质量门**：每个模型有效记录率低于 95% 时阻断后续节点，不能用残缺数据生成完整结论。
- **引用口径**：检索候选与答案实际引用分开保存，避免把“搜到”误写成“引用”。
- **历史可比性**：固定问题集并保存指纹；回答、来源、站点信号和规则版本按周冻结。
- **规则证据门**：候选规则至少需要 30 个唯一“页面—周”样本、15% 覆盖率和两个平台支持；权重调整还要求连续两周方向一致。
- **事实边界**：`brand.yaml` 是内容生成的事实源；数字声明必须映射到事实锚点，禁用价格和未经证实的节省比例。
- **人工发布关口**：自动流程只生成草稿；最新审核为 `pass` / `minor` 后才能进入发布归档。
- **外部输入安全**：模型返回的 URL 被视为不可信输入，抓取前进行协议、公网地址和连接目标校验。
- **降级可见**：抓取、语义解析、GSC、Research 预算等异常进入产物与报告，不静默伪装成正常零值。

系统的价值不仅是能自动修改规则，也包括证据不足时能够克制地不修改规则。

## 从 0 到 1 的建设路径

1. 建立原创品牌 SunHestia、英文官网与可测量的运行基线。
2. 打通采集、解析、抓取、GEO / SEO 评分和报告的最小链路。
3. 接入 Research，从真实来源中形成内容 Playbook 与平台画像。
4. 接入 Generate，增加品牌事实库、数字校验和人工审核关口。
5. 接入 RulesKeeper，以证据门槛管理规则晋升、版本和回滚。
6. 补齐断点续跑、失败隔离、URL 安全、原子写入、依赖锁与 CI。

每个阶段先形成可验证的产物，再扩展下一层能力，避免一次堆出无法复核的“大而全”系统。

<a id="quick-start"></a>

## 快速开始

### 环境要求

| 组件 | 要求 | 用途 |
| --- | --- | --- |
| Python | 3.11 或 3.12 | GEO Agent 管线与测试 |
| Node.js | 20+ | Astro 站点检查与构建 |
| SQLite | Python 自带 | LangGraph checkpoint |
| 网络代理 | 可选 | 无法直连 GSC 或外部站点时通过配置启用 |

### 安装并验证 GEO Agent

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r geo-agent/requirements.lock
python -m pip install --no-deps -e geo-agent

cd geo-agent
python -m pytest
```

普通测试不需要 API 密钥；依赖网络或真实模型的测试会自动跳过。

### 检查并构建 SunHestia

```bash
cd site
npm ci
npm run check
npm run build
```

构建产物位于 `site/dist/`。部署步骤见 [`site/DEPLOY.md`](site/DEPLOY.md)。

### 配置真实周迭代

> [!WARNING]
> 真实周迭代会调用外部模型和 GSC、写入当周数据，并可能产生费用。首次运行前必须核对周号、规则版本、API 配额、代理和本地数据备份。

在 `geo-agent/.env` 中配置所需凭据。该文件与 GSC 私钥已被 Git 忽略，不应提交到仓库。

```dotenv
DASHSCOPE_API_KEY=
ARK_API_KEY=
BIGMODEL_API_KEY=
MOONSHOT_API_KEY=
GSC_KEY_FILE=/absolute/path/to/gsc-service-account.json
```

关键配置：

| 文件 | 负责内容 |
| --- | --- |
| [`geo-agent/run.yaml`](geo-agent/run.yaml) | 周号、运行模式、范围、次数、规则版本与 provider |
| [`geo-agent/run.yaml.example`](geo-agent/run.yaml.example) | 参数说明与无凭据示例 |
| [`geo-agent/targets.yaml`](geo-agent/targets.yaml) | 站点 URL、评估页面、品牌词与当前代理 |
| [`geo-agent/targets.yaml.example`](geo-agent/targets.yaml.example) | 可移植的直连配置示例 |

确认配置后，在 `geo-agent/` 中运行：

```bash
python -m geo.orchestrate.graph --week 5
```

| 参数 | 行为 |
| --- | --- |
| `--week N` | 显式选择生产周；测试保留 `900–999`，生产入口会拒绝该区间 |
| `--next-week` | 完成后原子递增 `run.yaml` 中的周号 |
| `--force-new-run` | 忽略同周 checkpoint，从头运行并再次调用付费接口 |

默认情况下，同周完整运行会跳过，部分运行会从 checkpoint 继续。不要把 `--force-new-run` 当作日常选项。

## 当前验证快照

以下结果仅代表 2026-09-11 的本地代码快照：

| 检查 | 结果 |
| --- | --- |
| GEO Agent 离线回归 | 582 passed，2 skipped；仍有现存依赖弃用等 warnings |
| Astro 静态检查 | 0 errors，0 warnings，0 hints |
| Astro 静态构建 | 19 pages built |

这些检查证明当前代码回归与站点构建通过，不单独构成真实 API、线上可用性或业务效果的验收。

## 仓库结构

```text
sunpowerNova/
├── geo-agent/
│   ├── src/geo/
│   │   ├── collect/       # 模型采集与 L2 解析
│   │   ├── fetch/         # 来源页面、GSC 与站点信号
│   │   ├── assess/        # GEO / SEO 评分与差距诊断
│   │   ├── research/      # 来源研究、Playbook 与平台画像
│   │   ├── generate/      # 选题、草稿、校验与人审状态
│   │   ├── rules/         # 证据门槛、权重和版本迭代
│   │   ├── report/        # Jinja2 + ECharts 中文周报
│   │   ├── orchestrate/   # LangGraph 周迭代入口
│   │   └── shared/        # 配置、模型、存储与公共客户端
│   ├── input/             # 冻结问题集
│   ├── knowledge/         # 品牌事实、Playbook 与平台画像
│   ├── content/           # 草稿、发布归档与审核记录
│   ├── rules/             # 当前规则、历史版本与 changelog
│   ├── tests/             # 离线回归、负向用例与黄金锁
│   └── data/ · reports/ · state/   # 本地运行与迭代产物，不入 Git
├── site/                  # SunHestia Astro 静态站点
├── docs/
│   ├── superpowers/specs/ # 设计文档
│   ├── superpowers/plans/ # 分阶段实现计划
│   └── archive/           # 历史设计与 W1 人工资料
└── .github/workflows/     # Python 与 Astro CI
```

<a id="docs"></a>

## 文档地图

| 想了解什么 | 从这里开始 |
| --- | --- |
| 面向汇报的项目叙事、价值与结果边界 | [SunPower Nova 项目演讲汇报文稿](docs/SunPower-Nova项目演讲汇报文稿.md) |
| 项目目标、总体架构与评分口径 | [整合设计 v1.1](docs/superpowers/specs/2026-07-29-sunpower-nova-integration-design.md) |
| Research Agent | [P1 Research 设计](docs/superpowers/specs/2026-08-13-p1-research-agent-design.md) |
| Generate Agent 与人工发布关口 | [P2 Generate 设计](docs/superpowers/specs/2026-08-16-p2-generate-agent-design.md) |
| RulesKeeper 与规则版本 | [P3 RulesKeeper 设计](docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md) |
| W4 后续问题与修复 | [W4 修复设计](docs/superpowers/specs/2026-09-05-w4-bugfixes-design.md) · [GSC 传输修复](docs/superpowers/specs/2026-09-06-gsc-transport-fix-design.md) |
| 对应实现步骤与验收计划 | [`docs/superpowers/plans/`](docs/superpowers/plans/) |
| 站点构建与 Cloudflare Pages 部署 | [`site/DEPLOY.md`](site/DEPLOY.md) |
| 早期方案和人工 W1 资料 | [`docs/archive/`](docs/archive/) |

---

**SunPower Nova 的长期价值，不是某一周的分数，而是持续回答两个问题：下一步该做什么，为什么这样做；至于做完以后是否有效，还需要在未来的持续运行与数据积累中得到验证。**
