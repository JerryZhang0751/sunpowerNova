# 竞品网站分析：sunpowerglobal.com（TCL SunPower Global）

> 项目背景：SunHestia（内部代号 sunpower nova）GEO 实验。本文是对**竞品 `https://www.sunpowerglobal.com`**（真实身份「TCL SunPower Global」，TCL 旗下海外光伏品牌）的**深度重做分析**，替代 W1 报告 §4 中那段仅覆盖「信息架构」的简述。
> 焦点：**建站方式 / SEO 基础 / GEO 合规性 / 缺欠清单 / 对 SunHestia 的启示**。
> 分析日期：**2026-07-18**。所有结论均以 `curl` 实测数据为证据（附录 §8）。

---

## 1. 摘要（Executive Summary）

| 维度 | 结论 |
|---|---|
| **建站方式** | **Webflow（无代码可视化建站 SaaS）+ Webflow CMS**，资产走 `cdn.prod.website-files.com`，边缘由 **Cloudflare** 兜底（`server: cloudflare`、`x-wf-region: us-east-1`、`surrogate-key`）。视频用 Cloudflare Stream，轮播用 Swiper.js，分析用 GA4。**HTML 服务端预渲染**（内容在静态 HTML 里，对爬虫友好）。 |
| **体量** | sitemap.xml **722 个 URL**：320 篇新闻稿 + 210 篇博客 + 190 个案例研究，覆盖 **11 个语言/地区**（en / es-ES / fr-FR / it / de-DE / nl / fr-BE / nl-BE / en-AU / en-GB / x-default）。成熟、有资源、有商标的成熟品牌站。 |
| **GEO 成熟度** | **有意识但浅尝辄止**：有 `llms.txt`（但仅 9 行/4 链接、无 `llms-full.txt`）；AI 爬虫**未被显式放行**（仅落到 `User-agent: *` 默认允许）；无 `.well-known/ai.txt`、无 `/ai/*.json`。按 `geo-optimizer-skill` 8 维评分约 **42/100（Foundation 档）**。 |
| **SEO 成熟度** | **基础参差**：hreflang 国际化**优秀**、内容深度尚可、首页图 alt 全覆盖；但 **meta description 全站缺失**、OG/Twitter 卡片**残缺**（只有 `og:type`）、结构化数据**只有 Organization + BlogPosting/Article**，缺 Product/FAQPage/HowTo/BreadcrumbList/Review。 |
| **核心洞察** | **体量 ≠ GEO 成熟度**。一个 722 页、11 语种的成熟品牌，GEO 维度只做到「让站存在 + 挂了最小 llms.txt」，大量可执行杠杆空缺。这正是 SunHestia（13 页、Astro 代码可控）可以用**结构性 GEO 工程化**弯道超车的缝隙。 |

> 一句话：**竞品是「重资产、轻工程」的 Webflow 站；它的 SEO 强在国际化与内容量，弱在元数据与结构化数据；GEO 几乎是空白。**

---

## 2. 分析方法：调用 GitHub 上的 SEO/GEO skill 评分体系

按 memory 中既定来源（避开 `skillmp.com` 这个通用学习平台），本次直接采用 GitHub 上两个**带可执行打分细则**的开源 skill 作为评估框架（未克隆，仅取其评分表逐项核验）：

| Skill（GitHub） | 用途 | 用了它的什么 |
|---|---|---|
| **`Auriti-Labs/geo-optimizer-skill`**（[SKILL.md](https://github.com/Auriti-Labs/geo-optimizer-skill/blob/main/SKILL.md) / [SCORING_RUBRIC.md](https://github.com/Auriti-Labs/geo-optimizer-skill/blob/main/SCORING_RUBRIC.md)） | GEO 0–100 打分 | **8 维 / 100 分**评分表（Robots.txt /18、llms.txt /18、Schema /16、Meta /14、Content /12、Brand-Entity /10、Signals /6、AI Discovery /6）+ 附加项（CDN 爬虫放行、JS 渲染、负向信号、RAG 切片就绪度） |
| **`seo-skills/seo-audit-skill`**（SEOmator，[SKILL.md](https://github.com/seo-skills/seo-audit-skill/blob/main/skill/SKILL.md)） | SEO 251 规则审计 | **20 类加权**框架（Core 12% / Performance 12% / Links 8% / Images 8% / Security 8% / Tech-SEO 7% / … / Structured Data 5% / Social 3% / E-E-A-T 3% / **AI-GEO 2%**） |
| **`coreyhaines31/marketingskills` → seo-audit**（[SKILL.md](https://github.com/coreyhaines31/marketingskills/blob/main/skills/seo-audit/SKILL.md)） | 散文 checklist 补强 | hreflang 细则、**「JSON-LD 常被 CMS 用 JS 注入，curl 看不到，需用浏览器/Rich Results Test 复核」**这条关键防错提醒 |

> **执行透明度**：本想用 `uvx --from geo-optimizer-skill geo audit --url …` 跑一遍官方 CLI 做交叉验证，但本机无 `uvx`（也无 `gtimeout`）。故**人工按其官方评分表**逐项用 `curl` 取证打分——评分口径与官方 rubric 一致，证据见 §8。所有「JSON-LD 判定」均来自**服务端 HTML 中的内联 `<script type=application/ld+json>`**（Webflow 是服务端预渲染，不存在「JS 注入看不到」的陷阱，故可信）。

---

## 3. 建站方式（技术栈 / Build Method）

### 3.1 一句话定性
**Webflow（无代码建站平台）+ Webflow CMS，前端静态 HTML 经 Cloudflare 边缘分发，后端为 Webflow 在 AWS us-east-1 的 Lambda 源站。**

### 3.2 证据链（逐条）

| 判据 | 实测证据 | 结论 |
|---|---|---|
| 建站平台 | CSS 来自 `cdn.prod.website-files.com/6836d19…/sunpowerglobal.webflow.shared.*.min.css` 与 `sunpowerglobal.webflow.*.opt.min.css` | **Webflow** |
| Webflow 交互 | `webflow.js` + jQuery 在场；HTML 含 **33 处** `w-mod`/`data-w-id`/`data-wf-*` | Webflow 交互系统 |
| 源站 / 区域 | 响应头 `x-wf-region: us-east-1`、`x-lambda-id: …` | Webflow AWS Lambda 源（us-east-1） |
| 边缘 / CDN | `server: cloudflare`、`cf-ray`、`cf-cache-status: HIT`、`_cfuvid` cookie、`surrogate-control`、`surrogate-key`（含 `pageId:6836d19ac…`） | **Cloudflare** 在前 |
| 视频 | `link: preconnect → customer-gr554ixkv8ijtewn.cloudflarestream.com` | Cloudflare Stream |
| 轮播 | `swiper@12/swiper-bundle.min.css`（jsdelivr） | Swiper.js |
| 分析 | `meta analytics-ownership` 暴露 GA4 多 Property（`G-Q00FBECH6N`、`G-B0PCXPJZ2S`、`G-VLQ9ZZEHSV`…） | GA4 |
| 社交 | `meta facebook-domain-verification = 233l7…` | Meta Pixel / 域名验证 |
| CMS 集合 | `/blog/*`、`/case-study/*`、`/press-release/*` 结构高度统一、量大（210/190/320） | Webflow CMS Collection |
| 渲染模式 | 首页 HTML 101KB、正文 ~648 词、H1/H2/H3 均在静态 HTML 内可见（见 §8） | **服务端预渲染**（非 CSR/SPA），爬虫可直读 |

### 3.3 这套技术栈的含义（关键）
- **优点**：Webflow 输出的是**预渲染静态 HTML**，正文与标题都在 HTML 里——对 Google 与 AI 爬虫都**可读**（这一点比纯 React/Vue SPA 强很多）。Cloudflare 边缘缓存 + HSTS + HTTP/2，性能与安全基线不差。
- **结构性短板**：Webflow 是**无代码**平台，SEO/GEO 的「深度工程」要么靠模板默认（很弱），要么靠逐页手填/手嵌代码（成本高）。这**直接解释了下面 §5、§6 的大多数缺欠**：
  - meta description 全站缺失 → Webflow 不自动生成，团队没逐页填；
  - OG 只有 `og:type` → Webflow 的 OG 需手配，团队没配全；
  - 结构化数据只有 Organization/BlogPosting → Webflow schema 受限，要 Product/FAQ/HowTo 得手嵌 JSON-LD，他们没做；
  - llms.txt 极简 → 有人挂了个最简版，没投入做 `llms-full.txt`；
  - robots.txt 无 AI 专属规则 → 用了 Webflow 默认通用 robots，没为 AI 爬虫定制白名单。
- **对照 SunHestia**：SunHestia 是 **Astro（代码可控、SSG）**。意味着上面这些 Webflow「难做」的事，SunHestia **天然就能做**（模板里统一注入 meta/OG/JSON-LD/llms.txt/AI robots）。这是实验中的结构性优势。

---

## 4. SEO 评估（按 `seo-audit-skill` 20 类口径）

| 类目（权重） | 竞品表现 | 评级 |
|---|---|---|
| **国际化 / hreflang（2%）** | **最强项**。HTML `<head>` + sitemap.xml 双写完整 hreflang：`x-default`、`en`、`es-ES`、`fr-FR`、`it`、`de-DE`、`nl`、`fr-BE`、`nl-BE`、`en-AU`、`en-GB`，自引用 + 互回链齐全。sitemap.xml 每条 `<url>` 都带全量 `xhtml:link alternate`。 | 🟢 优秀 |
| **Core（canonical/索引，12%）** | canonical ✓（`https://www.sunpowerglobal.com/`，内页各自 canonical ✓）；无 `noindex` 误配；robots.txt 仅屏蔽 `/admin /account /cart /checkout /login /search?` 与各语种的 `?*` 查询串/`/how-to-guides`。 | 🟢 良好 |
| **On-Page 标题/描述（Title ~12%）** | 首页 title：`Solar Energy Company - Solar Panels - TCL SunPower Global`（关键词前置、含品牌）；**但 meta description 全站缺失**（首页/博客/案例均无）。 | 🟡 标题好、描述缺 |
| **Images（8%）** | 首页 69 张 `<img>`，**alt 覆盖率 100%、空 alt 0**。 | 🟢 优秀 |
| **Structured Data（5%）** | 首页 `Organization`（name/description/url/logo/areaServed/sameAs）；博客 `BlogPosting`（headline/image/datePublished/dateModified/author/publisher/mainEntityOfPage）；案例 `Article`。**缺**：Product / FAQPage / HowTo / BreadcrumbList / Review·AggregateRating / VideoObject / WebSite(SearchAction)。 | 🟡 有基础、缺富类型 |
| **Social / OG·Twitter（3%）** | **残缺**：全站只有 `og:type=website`，无 `og:title / og:description / og:image / og:url / og:site_name`；无 Twitter Card。分享出去**没有预览图/标题**。 | 🔴 弱 |
| **Performance（12%）** | Cloudflare HIT 缓存、HSTS、HTTP/2、字体 woff2 预加载；但首页 **69 张图 + jQuery + Webflow.js + Swiper**，体积偏大。 | 🟡 中等 |
| **Links / 站点结构（8%）** | 三大受众入口（Homeowners / Businesses / Installers）× 11 语种，CMS 集合内链清晰。 | 🟢 良好 |
| **E-E-A-T（3%）** | 博客/案例 schema 含 `author`+`datePublished/Modified`；但**无可见专家资质、无 Review schema、无第三方评测背书**。 | 🟡 中等偏弱 |
| **安全（8%）** | HTTPS + HSTS（`max-age=31536000; includeSubDomains`）+ `x-frame-options: SAMEORIGIN` + CSP `frame-ancestors 'self'`。 | 🟢 良好 |
| **Tech-SEO / 可爬（7%）** | sitemap.xml 在场（robots.txt 声明 + GSC 可提交）、URL 规范、无软 404 迹象。 | 🟢 良好 |
| **AI/GEO Readiness（2%）** | 见 §5。llms.txt 极简、AI 爬虫未显式放行、无 AI 发现端点。 | 🔴 弱 |

> **SEO 一句话**：国际化（hreflang）与内容量是长板；**meta description 全站缺失 + OG 残缺 + 富类型 Schema 缺失**是三大明确短板，且都源自 Webflow 无代码栈的天然限制。

---

## 5. GEO 合规评估（按 `geo-optimizer-skill` 8 维 / 100 分）

### 5.1 逐维打分

| # | 维度 | 满分 | 得分 | 证据 / 说明 |
|---|---|---|---|---|
| 1 | **Robots.txt** | 18 | **10** | 有 robots.txt、声明 sitemap；AI 爬虫落到 `User-agent: *`（无 Disallow，**隐式可爬**）。**但无 GPTBot/ClaudeBot/PerplexityBot/Google-Extended/Bytespider 等显式放行**——不主动、不可控，按 rubric「未显式 allow citation bot」扣分。 |
| 2 | **llms.txt** | 18 | **5** | `/llms.txt` 在（9 行 / 557 字节）：仅 H1 标题 + 一句 tagline + 4 个链接（Home / News&Stories / Documents / Contact）。**无 blockquote 摘要、无产品/FAQ 分节、无深度**；`/llms-full.txt` 404、`/.well-known/llms.txt` 404。 |
| 3 | **Schema JSON-LD** | 16 | **7** | Organization + BlogPosting/Article 在场（5+ 属性）。**缺 WebSite(SearchAction)、Product、FAQPage、HowTo、BreadcrumbList、Review**——光储品类最该有的 Product/FAQ 全无。 |
| 4 | **Meta Tags** | 14 | **5** | title ✓、canonical ✓；**meta description 全站缺失**；OG 仅 `og:type`，无 og:title/image/description；无 Twitter Card。 |
| 5 | **Content** | 12 | **5** | 博客 ~1347 词（深）、首页 ~648、案例 ~458（偏薄）；但**非「定义式开头」**（开头是营销文案「New Solar Powerhouse to Redefine…」）、**统计稀少**（博客仅 5 处 num+unit）、**无 `<blockquote>`/`<cite>` 外部引用**——citability 弱。 |
| 6 | **Brand & Entity** | 10 | **6** | 「TCL SunPower」品牌强、Organization schema 含 `sameAs`+`areaServed`、多语种大站；但未见 Wikipedia/Wikidata/Crunchbase 强实体链（未在首页 schema `sameAs` 中暴露）。 |
| 7 | **Signals** | 6 | **4** | `<html lang>` ✓；博客/案例 schema 含 `dateModified` ✓；**未发现 RSS/Atom feed**。 |
| 8 | **AI Discovery** | 6 | **0** | 无 `.well-known/ai.txt`、无 `/ai/summary.json`、`/ai/faq.json`、`/ai/service.json`。 |
| | **合计** | **100** | **≈ 42** | **「Foundation（36–67）」档**：有地基，远未优化 |

> 分档对照（geo-optimizer 官方）：86–100 Excellent · 68–85 Good · **36–67 Foundation** · 0–35 Critical。**竞品 42 分 = 刚过 Critical，进 Foundation 下沿。**

### 5.2 附加项（geo-optimizer bonus checks）

| 附加项 | 竞品情况 |
|---|---|
| CDN 是否拦截 AI 爬虫 | **未拦截**（Cloudflare 未对 GPTBot/ClaudeBot/PerplexityBot 设 WAF 拦截）→ 正面 |
| JS 渲染（无 JS 是否可读） | **可读**（Webflow 服务端预渲染，正文在 HTML）→ 正面 |
| 负向信号（CTA 过载/弹窗/薄内容/关键词堆砌/缺作者/样板比例） | CTA 较多、营销腔重、统计稀薄 → 中度负向 |
| RAG 切片就绪度（定义式开头/标题边界/锚句） | **弱**：非定义式开头、缺事实摘要块 |
| Prompt-injection 防御 | 未发现隐藏文本/不可见 Unicode/aria-hidden 滥用 → 正常 |

---

## 6. 缺欠清单（按优先级 / 可操作性排序）

> 标注 **[GEO]**=生成式引擎优化杠杆 / **[SEO]**=传统搜索杠杆 / **[Webflow 根因]**=受无代码栈限制。

### 🔴 P0 — 高影响、且 SunHestia 可直接做差异化

1. **`llms.txt` 形同摆设**（[GEO]）
   - 现状：9 行 4 链接，无摘要、无分节、无 `llms-full.txt`。
   - 影响：LLM 读不到结构化的「我是谁、卖什么、权威依据」摘要。
   - **对 SunHestia**：W2 直接做一份**合格 llms.txt + llms-full.txt**（H1 + blockquote 摘要 + 分节：产品/技术/FAQ/案例 + 深度链接），即可在此维度**反超竞品**。

2. **AI 爬虫未显式放行**（[GEO]）
   - 现状：robots.txt 仅 `User-agent: *`，无 GPTBot/ClaudeBot/PerplexityBot/Google-Extended/Bytespider/CCbot 等显式 `Allow:`。
   - 影响：不主动「邀请」AI 引擎，可控性与信号都弱。
   - **对 SunHestia**：W2 在 robots.txt 显式列出全部已知 AI 爬虫 UA 并 `Allow: /`——SunHestia W1 已做，**已领先竞品**。

3. **结构化数据缺富类型**（[GEO][SEO]，[Webflow 根因]）
   - 现状：只有 Organization / BlogPosting / Article。**无 Product / FAQPage / HowTo / BreadcrumbList / Review / VideoObject / WebSite**。
   - 影响：光储品类最该拿的「产品规格 + FAQ + 评测」富结果与 LLM 实体抽取全错过。
   - **对 SunHestia**：W3 用 Astro 模板统一注入 Organization + Product + FAQPage + Article + BreadcrumbList + Review——**结构性领先**。

4. **meta description 全站缺失**（[SEO]，[Webflow 根因]）
   - 现状：首页/博客/案例均无 `meta description`（Webflow 不自动生成、团队没逐页填）。
   - 影响：SERP 摘要交由 Google 自动生成，失去点击率与控场；也削弱 LLM 抓取的「一句话定义」。
   - **对 SunHestia**：W2–W4 每页写**定义式 meta description**（一句话 + 关键事实），既喂 SEO 又喂 GEO。

### 🟠 P1 — 中影响

5. **OG / Twitter Card 残缺**（[SEO][GEO]）：只有 `og:type`，无 og:title/image/description，分享无预览图。→ SunHestia 在 `Layout.astro` 补全 OG/Twitter 全套（W1 已部分做，W2 复核完整）。
6. **内容非「定义式开头」、统计稀薄、无外部引用**（[GEO]）：博客 1347 词但仅 5 处数据、无 `<blockquote>`/`<cite>`。Princeton GEO 论文：引用外源 +115%、统计 +40% citability。→ SunHestia W4 起每篇用**定义式开头 + 事实摘要块 + 数据 + 来源引用**。
7. **案例页偏薄（~458 词）**（[GEO][SEO]）：案例本是最强 E-E-A-T 证据，却写得太短。→ SunHestia 案例页目标 800–1200 词，含装机量/发电量/自用率/回本年等数字。
8. **无 AI 发现端点**（[GEO]）：无 `.well-known/ai.txt`、`/ai/summary.json`、`/ai/faq.json`、`/ai/service.json`。→ SunHestia 可在 W5–W6 试水（新兴规范，加分项）。

### 🟡 P2 — 低影响 / 竞品已做得不错（学之）

9. **无 RSS/Atom feed**（[GEO signals]）：博客量大却没喂 RSS，LLM/news 抓取少一条通道。
10. **`sameAs` 未暴露强实体链**（[GEO brand-entity]）：Organization schema 的 `sameAs` 应挂 Wikipedia/Wikidata/LinkedIn/Crunchbase，强化知识图谱实体。

---

## 7. 对 SunHestia（sunpower nova）的启示

1. **竞品的 GEO 是空白——这正是实验的「缝隙」**：722 页的成熟品牌只拿 42/100，说明 GEO 是**独立于体量的新学科**，绝大多数大站还没做。SunHestia 即便只有 13 页，只要**工程化做到位**（llms.txt / AI robots / JSON-LD / 定义式内容 / FAQ），在「单页 citability」上完全可能局部领先。

2. **SunHestia 的技术选型已构成结构性优势**：Astro 代码可控 vs Webflow 无代码——竞品「难做」的 meta/OG/Schema/llms.txt，SunHestia 都能在模板层**统一、批量化、零成本**注入。把这一点写进最终交付的「方法论」里，是很有说服力的对比。

3. **学竞品的长板**：
   - **hreflang 国际化**做得极规范（HTML + sitemap 双写、x-default、互回链）——若 SunHestia 未来扩多语种，这是黄金模板；
   - **CMS 集合化**（blog / case-study / press-release 各成体系）——SunHestia 的 `/news/` 现在只有 2 篇，可按此结构扩成 blog+case 两个集合；
   - **三大受众入口**（Homeowners / Businesses / Installers）——比 SunHestia 现有 `/residential/` 单一入口更细，值得借鉴分受众做内容。

4. **测量侧注意**：竞品用「TCL SunPower Global」全称、title/H1 含「SunPower」——再次印证 memory 中的品牌决策：**SunHestia 绝不能叫 SunPower**，否则 LLM 语料里真 SunPower 的海量内容会**污染测量**（这正是本次实验要规避的）。

5. **路线图微调建议**（供 W2+ 参考，不改动既定节奏）：
   - W2：补 **完整 OG/Twitter** + 复核 AI 爬虫名单（含 DeepSeek/Qwen UA）+ 做**合格 llms.txt/llms-full.txt** → 这三件竞品都弱，落地即可对标反超。
   - W3：全站 **JSON-LD 富类型**（重点 Product + FAQPage + BreadcrumbList）——竞品全缺。
   - W4：**定义式开头 + 统计 + 外部引用**——直击竞品内容最弱的 citability。
   - W6：案例页**做厚到 800–1200 词**（竞品 ~458 词）+ 作者/专家 E-E-A-T。

---

## 8. 附录：实测证据摘要（curl，2026-07-18）

### 8.1 响应头（首页，关键项）
```
HTTP/2 200
server: cloudflare
cf-cache-status: HIT
x-wf-region: us-east-1
x-lambda-id: c2be56f7-…
link: <https://cdn.prod.website-files.com>; rel=preconnect
       <…/sunpowerglobal.webflow.shared.*.min.css>; rel=preload; as=style
       <…/sunpowerglobal.webflow.*.opt.min.css>; rel=preload; as=style
       <https://customer-gr554ixkv8ijtewn.cloudflarestream.com>; rel=preconnect
       <https://cdn.jsdelivr.net/npm/swiper@12/swiper-bundle.min.css>; rel=preload; as=style
strict-transport-security: max-age=31536000; includeSubDomains
content-security-policy: frame-ancestors 'self'
x-frame-options: SAMEORIGIN
surrogate-key: … pageId:6836d19ac3462f6fef528ee0 …
```

### 8.2 robots.txt（要点）
- `User-agent: *`（**仅此一条**，无任何 AI 爬虫专属规则）
- `Sitemap: https://www.sunpowerglobal.com/sitemap.xml`
- Disallow：`/admin/ /account/ /login/ /cart/ /checkout/ /search?` + 各语种（`/au/ /de/ /es/ /fr/ /fr-be/ /it/ /nl/ /nl-be/ /pl/ /uk/`）的 `?*` 查询串、`/how-to-guides`、support 列表查询串。

### 8.3 端点探测
```
/robots.txt          200
/sitemap.xml         200   (722 个 <loc>，含完整 hreflang)
/sitemap-index.xml   404
/llms.txt            200   (9 行 / 557 字节，极简)
/llms-full.txt       404
/.well-known/llms.txt 404
/ai.txt              404
```

### 8.4 首页（/）页面级
- title：`Solar Energy Company - Solar Panels - TCL SunPower Global`
- canonical：`https://www.sunpowerglobal.com/` ✓
- **meta description：无** ✗
- OG：仅 `og:type=website`；**无** og:title/description/image/url/site_name ✗
- Twitter Card：无 ✗
- `<html lang=en>` ✓；hreflang link 标签全套（x-default/en/es-ES/fr-FR/it/de-DE/nl/fr-BE/nl-BE/en-AU/en-GB）✓
- H1×1（文本「TCL SunPower Global」——品牌名，非价值主张）/ H2×5 / H3×19
- 正文 ~648 词；69 张 `<img>` 全部有 alt、无空 alt ✓
- JSON-LD×1：`Organization`（name/description/url/logo/areaServed/sameAs）
- 脚本：webflow.js + jQuery + Swiper（jsdelivr）；33 处 `w-mod/data-w-*`

### 8.5 博客页（/blog/sunpower-energy-storage-smart-home）
- 70KB；正文 ~1347 词（深）✓；H1×1/H2×6/H3×6
- **meta description：无** ✗；OG：og:title/image 均**无** ✗
- canonical ✓；JSON-LD×1：`BlogPosting`（headline/description/image/datePublished/dateModified/author/publisher/mainEntityOfPage）✓
- `<blockquote>`/`<cite>`：无；统计（num+unit）：仅 **5** 处 ✗（citability 弱）

### 8.6 案例页（/case-study/an-eco-friendly-escape-in-puglia-italy）
- 56KB；正文 ~**458 词**（偏薄）；H1×1/H2×4/H3×1
- **meta description：无** ✗；OG 残缺 ✗
- canonical ✓；JSON-LD×1：`Article`（headline/image/thumbnailUrl/datePublished/dateModified/author/publisher）✓
- 统计：仅 **1** 处 ✗

### 8.7 sitemap.xml 规模（按路径前缀，去重计数）
```
320  press-release      210  blog       190  case-study
167  nl/persberichten   167  nl-be/persberichten   167  es/comunicado-de-prensa
…   （11 语种镜像：en / es-ES / fr-FR / it / de-DE / nl / fr-BE / nl-BE / en-AU / en-GB + pl）
```

---

*文档版本 v1，2026-07-18 ｜ 评估框架：`Auriti-Labs/geo-optimizer-skill`（GEO）+ `seo-skills/seo-audit-skill`（SEO）｜ 证据采集：curl 直连，无第三方 SDK。*
