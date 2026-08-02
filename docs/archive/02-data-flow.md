# 运行时数据流（一次 weekly run）

> 对应 PRD v4 §8.1（静态 DAG 范式）、§4.4（L2 解析契约）、§7.4（验收指标）。
> **动态视图**：数据如何从 input 流到 report，L1/L2/L3 在哪产生，控制变量如何贯穿。

```mermaid
flowchart TD
  START([周日定时 / CLI run --week N]) --> READ[读 run.yaml + targets.yaml + prompts.csv]
  READ --> STAMP["盖章两个控制变量<br/>prompt_set_version 提示词指纹<br/>rule_snapshot_version 规则快照"]
  STAMP --> MODE{模式}
  MODE -->|实验| EXP["锁定 sunhestia.com 13页<br/>full周=129 / core=45"]
  MODE -->|审计| AUD["自由 URL"]
  EXP --> COL
  AUD --> COL

  subgraph COL["① Collect — 3模型并发·各API QPM限速·stream"]
    M1["Qwen enable_search"] --> PARSE
    M2["豆包 web_search"] --> PARSE
    M3["智谱 web_search"] --> PARSE
    PARSE["L2解析 方案①<br/>结构化优先·文本兜底·品牌判定"] --> CON{置信}
    CON -->|structured| OK["存 L1+L2"]
    CON -->|inferred| LOW["低置信桶→报告附录"]
  end
  COL -. 失败/429 .-> RT["run日志·退避重试·标红不入分母"]
  RT --> COL
  OK --> DEDUP["L2 引用URL 去重 sha1"]
  DEDUP --> FET

  subgraph FET["② Fetch — 并发池+礼貌延迟"]
    FT["httpx+trafilatura 抽正文+meta"] --> JS{正文空}
    JS -->|有| L3OK["存 L3·跨周去重"]
    JS -->|无| JSO["JS-only·标不可分析·不入分母"]
  end

  L3OK --> ANA
  OK --> ANA
  subgraph ANA["③ Analyze — Kimi K3非被测 + 静态rules"]
    GEO["GEO 6维加权 0-100"]
    SEO["SEO 5支柱定性·不产复合分"]
    SEA["SEOAuditor 自审专属<br/>Lighthouse CWV + 结构特征"]
  end
  ANA --> SC["source_scores + run_scores"]
  SC --> BENCH["④ Benchmarker 3模型横向+自审↔竞品差值"]
  BENCH --> REC["⑤ Recommender 确定性gap→模板·按影响×成本"]
  REC --> REP["⑥ Reporter report.json固定Schema→Jinja2+ECharts"]
  REP --> DONE([reports/wN/report.html<br/>6节标准化·可diff·离线])

  STAMP -. 两变量贯穿全链·写进每条记录 .-> DONE
```

## 读图要点

- **六阶段**（① Collect → ② Fetch → ③ Analyze → ④ Benchmark → ⑤ Recommend → ⑥ Report），对应 DAG 节点。
- **控制变量在入口盖章**：`prompt_set_version`（提示词指纹）+ `rule_snapshot_version`（规则快照），虚线表示二者贯穿全链写进每条记录——这是 W1↔W7 可比性的机械保证。
- **两层"不入分母"**：采集失败/429、JS-only 来源都标红隔离，不污染主信号。
- **L2 双通道**：结构化优先（`search_results`/`web_search`），空则文本兜底（正则抽 URL，标 `inferred` 进低置信桶）。
- **确定性输出**：`report.json` 固定 Schema → Jinja2 模板 → 同输入同规则版本产字节级一致 HTML。
- **两层分母口径**（PRD §7.4/§8.1）：采集成功率分母 = 计划 prompt×model 数（全量 129 / 核心 45，失败计入）；mention/citation rate 分母 = 有效采集数。
