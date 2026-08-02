# 系统架构图（分层组件）

> 对应 PRD v4 §8（多 Agent 架构）、§9（技术栈）、§4（数据模型）。
> **静态视图**：谁是什么组件、数据存哪、规则库与密钥如何横切。

```mermaid
flowchart LR
  subgraph IN["输入 / 配置"]
    RUN["run.yaml<br/>week·models·mode·scope<br/>rule_snapshot_version"]
    TGT["targets.yaml<br/>实验=13页 / 审计=自由"]
    PR["prompts.csv 冻结<br/>→ prompt_set_version"]
    ENV[".env 密钥<br/>采集3家 + MOONSHOT"]
  end

  subgraph EXT["外部依赖"]
    Q["Qwen·DashScope<br/>原生搜索"]
    D["豆包·Ark<br/>原生搜索"]
    Z["智谱·BigModel<br/>原生搜索"]
    K["Kimi K3·Moonshot<br/>分析层-非被测"]
    WEB["被引来源 URL<br/>+ sunhestia.com"]
  end

  subgraph RULES["规则库·静态快照"]
    GR["geo-rules.yaml v1<br/>6维加权 0-100"]
    SR["seo-rules.yaml v1<br/>5支柱定性"]
  end

  subgraph DAG["LangGraph 静态 DAG (Coordinator)"]
    direction TB
    C["Collector<br/>L1 答案 + L2 引用解析"]
    F["Fetcher<br/>L3 正文+meta·JS-only标记"]
    A["Analyst×N<br/>GEO6维+SEO定性+来源属性"]
    SA["SEOAuditor<br/>Lighthouse+结构特征<br/>自审专属"]
    B["Benchmarker<br/>3模型对比+自审↔竞品差值"]
    REC["Recommender<br/>确定性 gap→模板"]
    REP["Reporter<br/>Jinja2 + ECharts"]
    C --> F --> A --> SA --> B --> REC --> REP
  end

  subgraph STORE["本地存储"]
    L1[("L1 raw/wN/model/pid.json<br/>答案+元信息")]
    L3[("L3 sources/sha1<br/>正文+meta 跨周去重")]
    AN[("analysis/wN/<br/>scores + report.json")]
    SQL[("runs.sqlite<br/>checkpoint+日志")]
    HTML["reports/wN/report.html<br/>标准化 可diff"]
  end

  RUN --> C
  TGT --> C
  PR --> C
  Q --> C
  D --> C
  Z --> C
  C --> L1
  C --> F
  WEB --> F
  F --> L3
  K --> A
  GR --> A
  SR --> A
  WEB --> SA
  A --> AN
  SA --> AN
  B --> AN
  AN --> REP
  REP --> HTML
  DAG -.状态/续跑.-> SQL
```

## 读图要点

- **四类外部依赖**：3 家采集 API（Qwen/豆包/智谱，原生搜索）+ Kimi K3（分析层，非被测，避免自评偏差）+ 抓取目标（被引来源 + sunhestia.com 自审）。
- **静态 DAG 七节点**：Collect → Fetch → Analyze → SEOAudit → Benchmark → Recommend → Report。条件分支仅「实验/审计模式」「全量/核心」。
- **规则库只读**：`geo/seo-rules.yaml@v1` 是静态快照，Analyst 运行时读取，不在链路里修改（迭代延后）。
- **三层本地存储**：L1 答案、L3 正文+meta（跨周 sha1 去重，不存 raw.html）、analysis 中间产物；`runs.sqlite` 横切做 checkpoint/续跑去重。
- **密钥横切**：`.env`（采集 3 家 + MOONSHOT）被各节点读取，为保持清爽不画数据流边。
- **两个控制变量**（`rule_snapshot_version` / `prompt_set_version`）贯穿全链写进每条记录——见 [02-data-flow.md](02-data-flow.md)。
