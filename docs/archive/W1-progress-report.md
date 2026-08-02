# SunHestia（sunpower nova）GEO 实验 — W1 进展汇报

> 项目代号 **sunpower nova** ｜ 对外品牌 **SunHestia** ｜ 实验周期 **W1–W8（W1 起 2026-07-20 → 2026-09-15）**
> 本文档：**W0 准备期**（2026-07-18–19，建站+基础设施）+ **W1**（2026-07-20–07-26，对照周）阶段汇报，记录「竞对调研 → 竞品网站分析 → 自建独立站做 GEO 对比实验」全过程。
> 周节奏（2026-07-19 重校准）：每周周一二实施当周杠杆 / 周三五静默 / 周末测量；**当周只做当周工作，不提前做下周准备**。
> 状态日期：**2026-07-19**

---

## 1. 摘要（Executive Summary）

**为什么做**：生成式引擎（ChatGPT / Gemini / DeepSeek / Grok / Qwen）正取代部分传统搜索流量，光储这类高客单、长决策品类，能否在 LLM 答案里「被提及/被引用」直接影响获客。我们要验证一套 **GEO（Generative Engine Optimization）方法**是否可复现地提升命中率。

**做了什么**：选定原创品牌 **SunHestia**（规避与真「TCL SunPower」的商标碰撞与测量污染），用 **Astro + Cloudflare Pages** 自建 13 页英文独立站并上线（https://sunhestia.com），放开全部 AI 爬虫、提交 Google Search Console 与 sitemap，搭好 43 条固定 prompt × 5 模型的测量工具链。

**到哪了**：基础设施全部就位、站点可被爬取、测量体系可用。W1 严格保持「**对照纯净**」——只做让站存在并够被爬的基础设施，**不做**任何旨在提升 LLM 引用的内容/结构/权威优化（Schema、定义式开头、FAQ 银行、E-E-A-T、外链全部留到 W2+）。

**下一步**：唯一的 W1 剩余交付是**基线测量**（W1 为**全量周**，43 × 5 = 215）。分工已优化——人工只需在周末（7/25–7/26）于外部 LLM 跑剩余 4 模型 × 全量 43 prompt、把每条答案存成 `answers/w1-{模型}-{prompt_id}.md`；由我统一解析回填 `week-01.csv`、再跑 `aggregate.py` 汇总进 `dashboard.md`。新品牌 W1 预期 ≈0，正是对照原点。

**核心数字**：8 周实验 · 9-15 交付 · 43 条 prompt · 5 个模型 · 13 页站点 · 1 个原创品牌。

---

## 2. 背景与目标

### 2.1 什么是 GEO

GEO（Generative Engine Optimization）= 让内容更容易被生成式引擎（LLM + 搜索增强）**抽取、引用、推荐**的一组方法。区别于传统 SEO 针对「关键词排名」，GEO 针对「答案中的提及/引用率」，研究证实的有效杠杆包括：定义式开头句、结构化数据（Schema.org）、FAQ 与参考资料、E-E-A-T 信任信号、站外权威种子、时效与深度等。

### 2.2 实验目标

> **验证「sunpower nova」这套 GEO 方法，能否在 8 周内可复现地提升一个光储独立站在头部 LLM 答案中的被提及率 / 被引用率。**

交付物 = **可复现的 GEO 方法论 + 8 周前后对照数据**。

### 2.3 实验设计（严格周对周）

- **W1 = 对照组**：vanilla 站点，只做基础设施，不施加任何 GEO 内容优化 → 取基线。
- **W2–W8 = 实验组**：每周施加**一项** GEO 杠杆（周一二实施、周三五静默、周末重测）→ 形成杠杆归因。**测量混搭**：全量 215 行仅在 W1/W4/W8（基线/中期/终期），其余周核心 75 行（15 prompt × 5）。
- 固定 prompt 集（43 条）× 固定 5 模型 × 每周完全相同的提问 → 控制变量、降低 LLM 随机性。

### 2.4 交付定义（现实预期）

新站被索引需要数周，W1–W3 大概率 ≈0，真正变化最可能在 W6–W8（Schema、参考资料、尤其 W7 站外权威）之后。因此 **2026-09-15 交付的是「方法论 + 早期趋势信号」，不强求统计学强结论**。

---

## 3. 竞对调研（✅ 已完成）

调研对象为竞品 **sunpowerglobal.com**（真实身份为「TCL SunPower」）。四项结论直接锁定了后续计划方向：

| # | 调研结论 | 对计划的影响 |
|---|---|---|
| 1 | **skillmp.com 是通用学习平台，并非 GEO skill 来源** | GEO 战术库来源改为：GitHub [`awesome-generative-engine-optimization`](https://github.com/amplifying-ai/awesome-generative-engine-optimization) + [Google 官方 AI 优化指南](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) + [Profound 10 步框架](https://www.tryprofound.com/resources/articles/generative-engine-optimization-geo-guide-2025) + 本地 `andrej-karpathy-skills-main`（SKILL.md 写法范本） |
| 2 | **竞品是真实「TCL SunPower」商标**，同名有商标/版权风险；且 LLM 会把「我们」与真 SunPower 混淆，污染测量数据 | 对外品牌改用**原创自造词**；「sunpower nova」仅作内部项目/GEO 工具代号保留 |
| 3 | **GEO 测的是固定 prompt 集下的被引用率**，无现成第三方数据 | 自建 43 条 prompt 集 + 每周手动跑 5 模型记录；W6 起接 Profound/Otterly 免费档交叉验证 |
| 4 | **新站索引滞后数周**，对照周必然 ≈0 | 9/15 交付**方法论 + 早期趋势**，不追求强结论；把站点尽快上线、尽早进索引 |

---

## 4. 竞品网站分析（✅ 已完成）

> 📌 **深度重做版见 [`competitor-analysis-sunpowerglobal.md`](../../report/competitor-analysis-sunpowerglobal.md)**（2026-07-18）——含建站方式（Webflow+Cloudflare）、SEO 20 类评估、GEO `geo-optimizer-skill` 8 维打分（≈42/100）、缺欠清单与对 SunHestia 的启示。本节为初版摘要，仅记录 IA 骨架。

仅参考竞品的**信息架构（IA）作为结构参考**，文案与视觉**全部原创**，规避版权风险。提炼出的页面骨架：

```
Home / Products（光伏 + 储能，突出自发自用）
  / Residential Solutions / About / Contact
  / FAQ / News-Blog / Technical Resources / Legal
```

这一步同时确认了两点：① 光储品类站点需要「产品 + 住宅方案 + 资料库 + 信任页」的标准结构才能被 LLM 当作可信引用源；② 必须用原创品牌才能得到干净的对照测量 → 引出品牌决策。

---

## 5. 关键决策（✅ 已完成）

| 维度 | 决定 | 理由 |
|---|---|---|
| **品牌** | 对外用 **SunHestia**（Sun + Hestia 希腊家灶女神，温暖/家居/有故事）；内容全原创 | 见下方「为何不用 SunPower」 |
| **市场/语言** | **英语起步**（UK / 泛欧单语种），后续再扩 | 控制变量，避免多语种稀释早期信号 |
| **测量方式** | **手动固定 prompt 集 + 后期接 SaaS 工具** | 先用零成本手动跑通方法论，W6 起接工具交叉验证 |
| **实验节奏** | **严格周对周**：W1 对照 / W2–W8 每周一 lever | 杠杆可归因、对照可复现 |
| **对照纯净性** | W1 只做「让站存在并能被爬」的基础设施 | 没有可测对象一切免谈；但绝不施加 GEO 内容优化 |

**为何不用 SunPower（品牌决策核心）**
- **商标/版权风险**：sunpowerglobal.com = 真「TCL SunPower」商标，同名直接碰撞。
- **测量污染**：LLM 训练语料里已有大量真 SunPower 内容，若同名，模型会把两者混淆，无法得到「我们的优化是否生效」的干净信号。
- **品牌候选 8 选 1**（语义方向：太阳/光 + 储能/电 + 家，自造词以提高 `.com` 可用性）：

| 候选 | 语义 | 调性 |
|---|---|---|
| HelioVault | Helio(太阳) + Vault(安全储能) | 科技、可靠 |
| SolKraft | Sol(太阳) + Kraft(力量，日耳曼语感) | 力量、欧洲本地感 |
| VoltHaus | Volt(电) + Haus(家，德语) | 直白、德语市场友好 |
| **SunHestia ✅** | Sun + Hestia(希腊家灶女神) | 温暖、家居、有故事 |
| LumenVault | Lumen(光) + Vault(储能) | 清晰、科技 |
| SolarNest | Solar + Nest(巢/家) | 亲切、住宅感 |
| Voltiva | 造词自 volt | 简短、品牌化 |
| HelioHearth | Helio + Hearth(壁炉/家) | 温暖、高端 |

经 `.com` 可用性筛查，**SunHestia** 为唯一可注册者（8 选 1）→ 已在 **Cloudflare Registrar** 注册 sunhestia.com。

---

## 6. W1 执行（✅ 已完成）

### 6.1 技术栈

| 项 | 选型 | 版本/说明 |
|---|---|---|
| 框架 | **Astro**（SSG，内容优先，对 AI 爬虫友好的静态 HTML） | `astro ^5.0.0`（5.0.0） |
| Sitemap | **@astrojs/sitemap** | `^3.2.0`（3.2.0），排除 `/draft/` |
| 托管 | **Cloudflare Pages**（免费档） | 全球边缘，对欧洲/AI 爬虫可达性好 |
| 站点 URL | `site = https://sunhestia.com`（`astro.config.mjs`） | canonical / OG / sitemap 已全部指向自定义域 |

### 6.2 站点内容（13 页，全原创英文）

| # | 路径 | H1 | 内容主题 |
|---|---|---|---|
| 1 | `/` (index) | Your roof. Your power. Your storage. | 首页 hero：面向欧洲房主的光伏+储能价值主张 |
| 2 | `/products/` | Solar generation, storage and control | 三大产品：LiFePO4 电池 5–15 kWh、单晶组件 400–450W、混合逆变器 |
| 3 | `/residential/` | Built for the home you own | 独栋住宅方案，自发自用，用例：热泵/EV/家电/备电 |
| 4 | `/about/` | About SunHestia | 使命：自发自用优先、按需配容不过量；四项核心价值观 |
| 5 | `/contact/` | Request a quote | 询价表单（姓名/邮箱/国家/房屋信息） |
| 6 | `/faq/` | Frequently asked questions | 6 条 FAQ：系统组成/电池配容/屋顶适配/安装周期/质保 |
| 7 | `/resources/` | Technical resources | 资料中心：规格书/安装指南/质保条款/自发自用指南 |
| 8 | `/news/` | News & stories | 文章索引（链 2 篇） |
| 9 | `/news/lifepo4-home-batteries/` | Why we use LiFePO4 for home batteries | 技术文：磷酸铁锂的长循环寿命/热稳定/无钴供应链 |
| 10 | `/news/what-is-self-consumption/` | What is self-consumption, and why does it matter? | 科普：自发自用经济学，为何优于上网、储能如何放大它 |
| 11 | `/legal/imprint/` | Imprint | 法律落款（公司地址/VAT 占位，待按所在国补充） |
| 12 | `/legal/privacy/` | Privacy policy | 隐私政策（表单数据收集 + 用户权利） |
| 13 | `/legal/terms/` | Terms of use | 使用条款（信息性、不构成要约） |

> 组件：`Layout.astro`（含 canonical/OG/Twitter meta）、`Header.astro`（粘性导航 + 高亮当前路径）、`Footer.astro`（多栏）；样式 `global.css`（琥珀 + 深蓝「太阳能」主题设计系统）。内容经抽查为原创、有真实独立 H1 与正文。

### 6.3 上线过程与踩坑对策

站点代码与构建产物就绪后，上线链路遇到三个卡点，均已解决：

**① 部署认证：wrangler login CSRF 失败**
- 现象：`wrangler login` 报 `No CSRF value available in the session cookie`（OAuth localhost 回调在代理/VPN 下被丢 CSRF）。
- 对策：改用 **Cloudflare API Token**（彻底绕开 OAuth）。Token 权限 = `Account→Cloudflare Pages→Edit` + `User→User Details→Read` + `Zone→DNS→Edit`（Zone Resources = **All zones**），TTL 至 2026-09-30。
- 用法：内联 `CLOUDFLARE_API_TOKEN=$(cat site/.cf_token)` + 显式 `CLOUDFLARE_ACCOUNT_ID`（token 缺账户列举权限，需手动带）。
- 安全：token 存 `site/.cf_token`，已加入 `.gitignore`，**永不入库**；用完可在面板 Revoke。

**② 自定义域名：Pages API 不自动建 DNS 记录**
- 现象：`POST /accounts/{acct}/pages/projects/sunhestia/domains` 把 sunhestia.com 挂进项目成功，但报 `CNAME record not set`（Pages API 不会自动建 DNS）。
- 对策：经 API 建 apex CNAME：`POST /zones/{zone_id}/dns_records` → `type=CNAME, name=@, content=sunhestia.pages.dev, proxied=true`（Cloudflare apex CNAME flattening）。
- 域名注册此前一度未成功（显示 Inactive / Requires DNS setup），用户重新注册后状态 Active，zone 可读。
- 结果：证书由 **Google Trust Services** 签发，sunhestia.com 全端点 200 上线。

**③ GSC 验证 + sitemap 提交**
- 验证：DNS TXT（apex，`proxied=false` 必须 DNS-only，Google 才能直读）。期间发现一条带引号的畸形重复 TXT 记录，已删除，保留正确一条。
- sitemap：`https://sunhestia.com/sitemap-index.xml` 提交成功。

**关键 ID（备查）**

| 项 | 值 |
|---|---|
| Account ID | `519bf361c99c4b762bca276ca174da70` |
| Zone ID（sunhestia.com） | `fac124e0cbc45799b32bbb532b0c2c74` |
| Pages 项目 | `sunhestia`（sunhestia.pages.dev） |
| API Token | `site/.cf_token`（gitignored，不入库） |
| GSC 验证 TXT | `google-site-verification=US3gSS7ZOZQBIVy6QoYKsBH2dKJ5pRm1mVmwFn_hobE` |

**线上验证（已通过）**：`https://sunhestia.com` 在 `/`、`/robots.txt`、`/sitemap-index.xml`、`/products/`、`/faq/` 均返回 200；首页 H1「Your roof. Your power. Your storage.」在静态 HTML 中可见；canonical = `https://sunhestia.com/`。

### 6.4 对照纯净性核查（W1 做了 vs 没做）

| 维度 | W1 做了吗 | 说明 |
|---|---|---|
| 部署上线 + 自定义域 + HTTPS | ✅ 做了 | 让站存在、可被爬 |
| `robots.txt` 放开全部 AI 爬虫 | ✅ 做了 | GPTBot / ClaudeBot / Claude-SearchBot / PerplexityBot / Google-Extended / Bytespider / CCBot / Applebot-Extended / cohere-ai 等 |
| sitemap-index.xml | ✅ 做了 | 提交 GSC |
| GSC 域名属性验证 | ✅ 做了 | DNS TXT |
| Schema.org JSON-LD | ❌ 留 W3 | — |
| 定义式开头句 / LLM 友好结构 | ❌ 留 W4 | — |
| FAQ 银行 / 对比页 / 术语表 | ❌ 留 W5 | — |
| E-E-A-T 强化（作者/评价/认证） | ❌ 留 W6 | — |
| 站外权威种子（外链/提及/目录） | ❌ 留 W7 | — |
| `llms.txt` | ❌ 留 W2 | — |

> 结论：W1 站点内容是「朴素但真实」的 vanilla 版本，未施加任何 GEO 优化 → 符合对照组定义。

---

## 7. 测量体系（✅ 已完成）

### 7.1 固定 prompt 集（43 条，欧洲房主视角，7 类）

| 类别 | 代码 | 条数 | 示例 |
|---|---|---|---|
| 品类型 category | C | 8 | `What is the best home solar panel and battery storage system in 2026?` |
| 自用/场景 scenario | S | 6 | `Solar panel with battery for self-consumption — is it worth it?` |
| 决策型 decision | D | 8 | `How to size a home solar battery` |
| 成本 cost | K | 5 | `How much does a home solar battery system cost in Europe?` |
| 对比 comparison | M | 6 | `Top residential solar companies in Europe 2026` |
| 品牌品牌 brand | B | 4 | `SunHestia solar reviews` |
| 地区 geo | G | 6 | `Best solar panel and battery system for a home in Germany` |
| **合计** | | **43** | 存 `geo-measurements/prompts.csv`，每周完全相同 |

### 7.2 模型（5 个，均开启 web/search，中国区可达）

| 模型 | 默认版本 | 联网模式 |
|---|---|---|
| ChatGPT | gpt-5.5 | search |
| Gemini | gemini-3.5-flash | grounding |
| DeepSeek | deepseek-v4-pro | 联网搜索 |
| Grok | grok-4.3 | 内置实时 |
| Qwen | qwen3.7-plus | 联网搜索 |

> **模型集修订（2026-07-18）**：因 Claude / Perplexity / Google AI Overviews 在中国区不可达，改为 **ChatGPT / Gemini / Grok + DeepSeek / Qwen**（国产双模型补位）。版本随官方更新可在 `week-XX.csv` 的 `model_version` 列覆盖记录。

### 7.3 工具链（`geo-measurements/`）

| 文件 | 作用 |
|---|---|
| `prompts.csv` | 43 条冻结 prompt 题 |
| `schema.md` | 字段定义 + 跑测协议 + **分工（人工存答案 / 助手解析）+ 解析规则** |
| `generate_week.py` | 生成预填好的 `week-XX.csv`（**全量周** 43×5=215 / **核心周** 15×5=75，按周号自动判断：W1/W4/W8 全量，其余核心） |
| `fill_row.py` | 助手读完答案文件后，把判读结果写进 `week-XX.csv` 对应行（拒绝覆盖已填行，除非 `--force`） |
| `aggregate.py` | 读 `week-XX.csv` → 算每模型与总体的提及率/引用率/平均位次/SOV/情感，并定位被提及的 prompt |
| `answers/` | 人工保存的模型答案 `w{N}-{模型}-{prompt_id}.md`（解析的唯一输入与审计底稿） |
| `dashboard.md` | 滚动趋势看板（W1→W8 各模型折线，W1 为基线） |

### 7.4 派生指标定义

- **提及率** = 提到 SunHestia 的 prompt 数 ÷ 总 prompt 数
- **引用率** = 含指向 sunhestia(.com\|.pages.dev) 可点击链接的 prompt 数 ÷ 总数
- **平均引用位次** = 被引用时的平均排名（1 = 第一个来源）
- **Share of Voice** = SunHestia 提及数 ÷ 同答案中所有品牌提及总数
- **情感** = 提及里 pos / neu / neg 占比

每条记录字段：`date | week | prompt_id | model | model_version | run | mentioned(Y/N) | cited_with_link(Y/N) | citation_position | sentiment(pos/neu/neg) | competitors_mentioned | raw_answer_link | notes`

---

## 8. W1 完成状态总览

### ✅ 已完成

- [x] 选定原创品牌 **SunHestia** + 注册 sunhestia.com（Cloudflare Registrar）
- [x] Astro 站点脚手架 + Cloudflare Pages 部署（`sunhestia.pages.dev`）
- [x] 绑定自定义域 sunhestia.com（apex CNAME via API）+ HTTPS 证书
- [x] 撰写 **13 页** 全原创英文内容
- [x] 技术基础设施：`sitemap-index.xml` / `robots.txt` 放开 AI 爬虫 / **GSC 域名验证** / **sitemap 提交**
- [x] 写定 **43 条** 固定 prompt 集（`prompts.csv`）
- [x] 测量工具链：`schema.md` + `generate_week.py` + `aggregate.py`（已通过空数据冒烟测试）+ `dashboard.md`

### ⏳ 未完成（非阻塞 / 可选）

- Bing Webmaster Tools 提交（可从 GSC 一键导入，喂 Copilot；W2 顺手做）
- W1 基线数据本身（待下条人工任务产出）

### 👤 需人工处理（W1 唯一人工项）

- **基线测量（只需跑 + 存答案，W1 为全量周 215 行）**：剩余 4 模型 × 全量 43 prompt，在**外部 LLM** 中开 web/search 跑、把每条答案存成 `answers/w1-{模型}-{prompt_id}.md`。（ChatGPT 43 条已于 7/19 跑完；我无法直接操作 ChatGPT/Gemini/DeepSeek/Grok/Qwen，必须人工执行；文件齐了发我，由我解析回填 `week-01.csv`、再 `aggregate.py` 汇总。）

---

## 9. 下一步：基线测量操作指引（👤 需人工处理）

**你只需做两件事——跑 prompt、存答案；判读与填表由我完成。**

**人工（你）：**

1. **取题**：打开 `geo-measurements/prompts.csv`，取**全部 43 条 prompt** 原文（W1 为全量周）。核心周（W2/W3/W5/W6/W7）才只取核心 15 条：`C01, C04, S01, S02, D01, D04, K01, K03, M01, M03, B01, B02, G01, G02, G05`
2. **跑模型**（5 个，均**开启 web/search**，用**无上下文的新会话**逐条粘贴原文，不改写）：
   ChatGPT(gpt-5.5,search) / Gemini(gemini-3.5-flash) / DeepSeek(deepseek-v4-pro) / Grok(grok-4.3) / Qwen(qwen3.7-plus)
3. **存答案**：每条答案**原文**存成 `answers/w1-{模型}-{prompt_id}.md`，例如：
   - `answers/w1-Qwen-C01.md`
   - `answers/w1-DeepSeek-C01.md`

   规范：模型名用规范大小写 `ChatGPT / Gemini / DeepSeek / Grok / Qwen`（我按文件名精确匹配行）；一个 model×prompt 一个文件；存完勿改（它是审计底稿）。
4. **文件齐了告诉我**（可分批，存几条发几条）。

**我（助手）：**

5. 逐个读 `answers/w1-*.md`，按 `schema.md`「解析规则」判读各字段（mentioned / cited_with_link / citation_position / sentiment / competitors_mentioned / notes），用 `fill_row.py` 回填 `week-01.csv` 对应行——每行一条命令，命令本身即审计记录。
6. 跑 `python3 aggregate.py 1` → 算出各模型提及率/引用率/平均位次/SOV/情感，填进 `dashboard.md`。

> **解析口径（我会严格遵守）**：`mentioned` 只认字面 "SunHestia"/"sunhestia.com"；`competitors_mentioned` 只收光储产品品牌（不含 EnergySage/Consumer Reports 等评测平台），哪怕我们没被提也填（喂养 SOV）；`citation_position`/`sentiment` 在未提及时留空；品牌类 prompt（B01–B04）模型复读不算提及，notes 标注"查无/编造/有实料"。
>
> **进度**：ChatGPT 43/43 + 4 模型各 C01 已解析回填（**47/215**，均 mentioned=N；多模型偏美国市场内容，SunHestia 未出现——符合新站基线）。剩余 168 行（4 模型 × ~42）留待 **W1 周末 7/25–7/26** 跑。
>
> **现实预期**：W1 全 0 完全正常、且就是我们要的数据点。真正的变化看 W6–W8。

---

## 10. W2–W8 杠杆路线图（预告）

| 周 | 杠杆 | 关键动作 | 产出 |
|---|---|---|---|
| W2 (7/27–8/2) ·核心75 | 技术 GEO 地基 | 核对 AI 爬虫名单、加 `llms.txt`/`llms-full.txt`、确认服务端预渲染、补 canonical/OG/`hreflang` | `week-02.csv` |
| W3 (8/3–8/9) ·核心75 | 结构化数据 | 全站 JSON-LD：Organization / Product / FAQPage / Article / BreadcrumbList / Review | `week-03.csv`（Rich Results Test 通过） |
| W4 (8/10–8/16) ·全量215 | LLM 内容重构 | 定义式开头句、强化 H2/H3 与列表/表格、每节顶部事实摘要 | `week-04.csv` |
| W5 (8/17–8/23) ·核心75 | FAQ + 参考资料 | FAQ 银行（对齐 prompt 句式）、对比页 / 术语表 / 选购指南 | `week-05.csv` |
| W6 (8/24–8/30) ·核心75 | E-E-A-T + 工具双轨 | 作者/专家简介、评价/案例、认证；接入 Profound/Otterly 免费档交叉验证 | `week-06.csv` |
| W7 (8/31–9/6) ·核心75 | 站外权威（最关键、最难） | 目录/Bing 提交、社区与外链（r/solar、HN、客座内容） | `week-07.csv` |
| W8 (9/7–9/13) ·全量215 | 时效性 + 深度 + 收尾 | 带日期新闻、扩薄内容页、强内链；最终测量 | `week-08.csv` |
| 9/14–9/15 | 缓冲 + 交付 | 整理 `report/`：方法论 + scorecard + W1↔W8 对比 + 杠杆归因 + 风险 | 9/15 交付 |

---

## 11. 附录

### 11.1 完整文件清单

```
annualReport/
├─ README.md                       # 项目概览 + W1 状态
├─ site/                           # Astro 独立站源码
│  ├─ astro.config.mjs             # site = https://sunhestia.com
│  ├─ package.json                 # astro 5.0.0 + @astrojs/sitemap 3.2.0
│  ├─ public/
│  │  ├─ robots.txt                # 允许全部 AI 爬虫
│  │  └─ favicon.svg
│  ├─ src/
│  │  ├─ layouts/Layout.astro      # SEO meta（canonical/OG/Twitter）
│  │  ├─ components/{Header,Footer}.astro
│  │  ├─ styles/global.css         # 琥珀+深蓝主题设计系统
│  │  └─ pages/                    # 13 页（见 §6.2）
│  ├─ .cf_token                    # Cloudflare API token（gitignored，不入库）
│  ├─ .gitignore                   # 含 .cf_token
│  └─ DEPLOY.md                    # Cloudflare Pages 部署指南
├─ geo-skills/
│  └─ README.md                    # 战术库索引（W2–W8 每 lever 一份 SKILL.md）
├─ answers/                        # 人工保存的模型答案 w{N}-{模型}-{prompt_id}.md（解析输入）
├─ geo-measurements/
│  ├─ prompts.csv                  # 43 条冻结 prompt
│  ├─ schema.md                    # 字段定义 + 跑测协议 + 分工 + 解析规则
│  ├─ generate_week.py             # 生成 week-XX.csv
│  ├─ fill_row.py                  # 把判读结果写进 week-XX.csv 对应行（助手用）
│  ├─ aggregate.py                 # CSV → 指标汇总
│  ├─ dashboard.md                 # 滚动趋势看板
│  └─ week-01.csv                  # W1 测量表（助手按 answers/ 解析回填）
└─ report/
   └─ W1-progress-report.md        # 本文档
```

### 11.2 风险与现实预期

- **索引滞后**：W1–W3 大概率全 0，delta 多在 W6–W8 才可能浮现 → 9/15 交付方法论 + 早期趋势。
- **随机性**：LLM 答复波动 → 多次跑（取众数）+ 固定 prompt + 记模型版本。
- **归因难度**：低权威新站 8 周内未必被引用；W7 站外权威是真正解锁但 solo 难度大，尽力争取 1–2 条真实外链/提及。
- **法律**：原创品牌 + 原创内容已规避主要风险；**严禁**逐字复刻竞品文案/图片。

### 11.3 端到端验证（当前状态）

- [x] 站点线上可访问（https://sunhestia.com 全端点 200，H1 在静态 HTML 可见）
- [x] canonical = `https://sunhestia.com/`，sitemap-index.xml 可达，robots 放开 AI 爬虫
- [x] GSC 域名验证通过 + sitemap 提交成功
- [x] 测量脚本可运行（`aggregate.py` 空数据冒烟通过，exit 0）
- [ ] W1 基线数据（待人工测量）
- [ ] Google `site:sunhestia.com` 有结果（索引需数周，非 W1 可控）

---

*文档版本：W1 checkpoint，2026-07-19（周节奏重校准：W1 起 7/20、周一二实施/三五静默/周末测量、全量 W1/W4/W8 + 核心 75 其余）｜ 计划全文见 `~/.claude/plans/geo-gpt-claude-grok-gmini-compressed-marshmallow.md`*
