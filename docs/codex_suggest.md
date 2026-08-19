结论：**不建议按当前 P3 spec 直接实现**。整体方向可保留，但证据口径、评分迁移、编排和版本模型存在阻断问题；否则系统会“确定性地得到不可靠结论”。

## 阻断问题

1. **把“搜索结果”误当成“答案引用”**

   整合 spec 将各平台返回的 `search_results/tool_result` 统一命名为 `cited_sources`，[P1 又据此计算“被引特征”](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-13-p1-research-agent-design.md:86>)。但这些字段可能是模型检索过的候选来源，不代表最终答案引用了它们。阿里云官方文档也明确区分“搜索来源”和正文引用角标；xAI 同样区分“浏览过的全部来源”和“内联引用”。[阿里云文档](https://help.aliyun.com/zh/model-studio/web-search/)，[xAI 文档](https://docs.x.ai/developers/tools/citations)。

   W1 实际有 1,469 个来源记录，解析后的 134 个只是 **34 个唯一 URL 的重复出现**，其中被截断的 `youtube.com/watch` 单一 URL重复 14 次。因此 P3 的 `26/134` 不是 134 个独立样本。

   **建议：** 数据契约拆为 `retrieved_sources` 和 `answer_citations`；只有能映射到答案正文的引用才能驱动 RulesKeeper。证据门槛应基于规范化后的唯一页面/页面周，而不是引用出现次数。

2. **P1 明确禁止因果推断，P3 却直接用同一数据自动改规则**

   [P1 明确写明](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-13-p1-research-agent-design.md:104>)“被引源中 X% 有某特征”只是观察性相关，不能表述为“因此更易被引”；但 [P3](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md:57>)直接用这个比例激活信号，并在[权重公式](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md:68>)中提升相应维度。

   这缺少未被引用页面的对照基线。一个特征在被引页中常见，可能只是因为它在全网本来就常见。

   **建议：** 在具备同查询、同平台的未被引对照组并能计算 lift/odds ratio 前，规则只能保持 `draft/advisory`，自动权重迭代应关闭。

3. **“v1 语义零漂移”在数学上不成立**

   [P3 声称](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md:34>)移除 `about_page_present`、`author_schema` 不会改变 W1 分数；但当前 E-E-A-T 实际有四项，第四项是 `Organization/Person schema`，[代码在此](</Users/jerry/AiProject/sunpower nova/geo-agent/src/geo/assess/geo_scorer.py:61>)。

   W1 前三项均为 0，正是第四项贡献了 E-E-A-T 的 25 分。如果按 spec 只保留前三项，E-E-A-T 会从 25 降到 0，GEO 总分约从 47.6 降至 42.6，不可能通过 `test_v1_semantics_unchanged`。

   此外，`technical_geo` 的 YAML 列出 5 项，代码实际计算 4 项且含两个独立 crawler 信号；P3 也没有在 spec 中完整说明这次迁移。

   **建议：** 列出每个维度的旧公式→新 signal ID 一一映射，包括阈值、缺失值处理和输入类型；GEO 与 SEO 需要不同的 checker context，而不是统一宣称 `(src, brand, static)`。

4. **DAG 存在数据依赖倒置，且同周复跑会直接 no-op**

   P3 的顺序是：

   `snapshot → research → generate → assess`

   但 [P2 明确规定](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-16-p2-generate-agent-design.md:203>) `--suggest --week N` 读取 WN 的 `eval_report.json`，而该文件要到后面的 `assess` 才生成。生成节点只能读到旧文件或缺失文件。

   同时 P3 要求手动复跑和 W1 首次迭代，但[现有 checkpoint 逻辑](</Users/jerry/AiProject/sunpower nova/geo-agent/src/geo/orchestrate/graph.py:73>)发现 `w1` 已完成就直接返回；本机 SQLite 中确实已有完整 `w1` checkpoint。

   **建议：**

   `collect → fetch → snapshot → assess → research → generate → rules → report`

   或明确生成使用 `eval_report[wN-1]`。checkpoint 应使用 `week + pipeline_revision + run_id`，并提供语义明确的 `--resume`/`--force-new-run`。

5. **当前版本模型无法兑现“历史精确重算”和安全回滚**

   [P3](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md:85>)只归档 YAML 的成员和权重，checker 公式与阈值仍留在当前代码中。以后修改 checker 后，用 v1 YAML 调当前 checker，并不是重算 v1。

   回滚时直接把活动版本改回 `v1` 还会产生两个问题：

   - 当前最新版本可能尚未被归档；
   - 回滚后再次迭代会重新生成 `v2`，与原有不可变 `v2` 冲突。

   **建议：** 每个规则版本必须绑定 checker/schema 版本、代码提交和输入哈希。回滚应创建新单调版本，例如 `v4`，记录 `restores: v1`，而不是把现行版本号倒退。

6. **竞品评分使用了 SunHestia 自身的静态信号**

   当前实现给竞品调用 `score_geo` 时传入的仍是 SunHestia 的 `static_signals`，[代码在此](</Users/jerry/AiProject/sunpower nova/geo-agent/src/geo/assess/analyst.py:278>)，同时将竞品品牌信号全部置零。

   P3 新增的 `about_page_present` 又定义为检查 SunHestia 的 13 页列表；一旦激活，所有竞品都会因为 SunHestia 有 `/about` 而得到该信号。这与“同口径竞品标杆”相悖。

   **建议：** scorer 输入必须是每个被评分实体独立的 `SiteContext`；缺少竞品全站数据时，该信号应为 `unknown/not_applicable`，不能引用目标站数据或按 0 计。

7. **“动作→指标归因干净”不成立**

   [P3 声称](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-19-p3-ruleskeeper-design.md:101>)新规则下周生效可以保持归因干净，但下周分数同时受到：

   - 页面变化；
   - 模型/API变化；
   - 新评分规则和新权重；
   - 28 天滚动 GSC 窗口；
   - 搜索收录延迟。

   此外，新发布的 `/news/self-consumption-guide` 尚未加入 `targets.yaml`，后续静态自审不会覆盖它；发布归档也没有 `published_at`、线上 URL 或部署版本。

   **建议：** 报告同时维护“固定基线规则分”和“当前规则分”；发布记录增加 URL、部署时间和版本；GSC 使用非重叠窗口或日粒度数据。不要把观察性环比称为动作效果。

8. **唯一人工发布关口实际上可绕过**

   [P2 设计](</Users/jerry/AiProject/sunpower nova/docs/superpowers/specs/2026-08-16-p2-generate-agent-design.md:177>)声称只有 `pass/minor` 分支可归档发布，但当前 [`--mark-published`](</Users/jerry/AiProject/sunpower nova/geo-agent/src/geo/generate/run.py:90>)只阻止 `status: rejected`：

   - 未经过任何 review 的 draft 可以发布；
   - `validation: flagged` 的 draft 可以发布；
   - 没有校验最新 review verdict。

   **建议：** 建立明确状态机：`draft → reviewed_pass/reviewed_minor → published`；发布时强制检查最新 review、校验状态和部署 URL。若允许 flagged 发布，必须使用显式 override 并记录原因。