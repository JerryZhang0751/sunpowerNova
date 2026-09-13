# 平台引用画像 · w6

## Doubao · doubao-seed-2-1-pro-260628 (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 搜索结果返回异常，让我换个查询再试。
  来源：— | 置信度：外部未验证

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): # 查证结果：Qwen（通义千问）爬虫 User-agent / 收录机制

## 结论

**本次查证未能确认阿里巴巴官方是否公布了 Qwen（通义千问）专用的爬虫 User-agent 名称及收录机制文档。**

具体情况如下：

1. **未找到官方爬虫标识**：与 OpenAI（GPTBot）、Anthropic（ClaudeBot）、Google（Google-Extended）等厂商公开发布爬虫说明文档不同，我通过多轮搜索均未找到阿里云/通义千问官方公开说明其模型训练数据抓取所用的专用爬虫 User-agent 名称的页面。

2. **阿里系已知的相关爬虫**：阿里系已知的公开爬虫为**神马搜索**的 `YisouSpider`（神马搜索为阿里巴巴旗下移动搜索引擎，其站长平台提供爬虫验证说明）。但这是传统搜索引擎爬虫，其与 Qwen 大模型训练数据之间的直接关联**未获官方确认**。

3. **收录机制**：未找到关于 Qwen 如何抓取、收录网页内容用于训练或联网检索的官方机制说明。行业观察普遍认为 Qwen 的联网搜索能力可能依托阿里系搜索基础设施（如夸克/神马），但此点同样无官方文档佐证。

## 来源

无法提供可验证的来源 URL。本次多轮搜索均未返回有效的官方文档结果，为避免杜撰 URL，我不列出未经核实的链接。（注：我知识库中存在神马站长平台 `zhanzhang.sm.cn` 这一参考点，但其当前可用性与内容未经本次查证验证，故不作为正式来源引用。）

## 置信度：**low**

（"未找到官方文档"不等于"官方文档不存在"——可能是文档未公开、未被搜索引擎索引，或存在于阿里云帮助中心的深层页面中。建议直接查阅阿里云官方文档站或联系阿里云支持以获得权威确认。）
  来源：— | 置信度：外部未验证

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.133
- 爬虫名/收录(联网查证): 结论：无法确认 Zhipu（智谱/智谱清言/ChatGLM）有公开声明的专用爬虫 User-Agent 或明确收录机制；我不能断定存在官方 “ZhipuBot/ChatGLM spider” UA，也不能确认其收录依赖 robots.txt、主动提交、搜索合作还是 API 授权。可核验路径是查对应域名的 robots.txt、官方开放平台/文档，以及服务器访问日志中的实际 UA；不要把第三方日志截图当作官方机制证据。  
来源：https://www.rfc-editor.org/rfc/rfc9309.html  
说明：该来源仅为 Robots Exclusion Protocol 标准，不是智谱官方事实来源；未提供可核验的智谱官方 URL，故不杜撰。  
置信度：low
  来源：https://www.rfc-editor.org/rfc/rfc9309.html | 置信度：low

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: **结论（平台：ChatGPT / OpenAI）**

1. **爬虫 User-Agent（官方文档确认 3 个）**
   - `GPTBot`：用于抓取可能用于训练生成式基础模型的内容。网站可在 robots.txt 中 `Disallow: /`（User-agent: GPTBot）来阻止。
   - `OAI-SearchBot`：用于 ChatGPT 的搜索功能（SearchGPT / ChatGPT Search），被抓取的页面才可能在 ChatGPT 回答中以引文/链接形式出现。阻止它**不影响**模型训练抓取（训练由 GPTBot 负责），但会导致站点不被 ChatGPT 搜索展示/引用。
   - `ChatGPT-User`：当 ChatGPT 用户主动发起请求（如让 ChatGPT 访问某网页）时代表用户实时抓取，属于用户触发、非自动爬虫。阻止它会降低站点内容在 ChatGPT 中的可见性。

2. **收录机制**
   - 站点被 ChatGPT 搜索引用/展示的前提通常是：robots.txt 允许 `OAI-SearchBot` 抓取；官方同时公布了各爬虫的 IP 段 JSON（如 gptbot.json / searchbot.json）供站长验证请求真伪。
   - 另有媒体/SEO 行业报道指出 ChatGPT Search 的索引部分依赖 Bing 等第三方搜索索引（即"被 Bing 收录"有助于被 ChatGPT 引用）——此点非 OpenAI 官方完整披露，**该子项置信度为 mid**。
   - 三个爬虫的 robots.txt 控制相互独立：禁止 GPTBot 不影响搜索展示，禁止 OAI-SearchBot 不影响训练数据抓取。

**来源：**
- https://platform.openai.com/docs/bots （OpenAI 官方爬虫文档：GPTBot / OAI-SearchBot / ChatGPT-User 及 robots.txt 用法、IP 段）
- https://openai.com/searchbot （OpenAI 面向发布者的搜索收录说明）

**置信度：high**（爬虫名称、User-Agent 与 robots.txt 收录机制均来自 OpenAI 官方文档；唯"依赖 Bing 索引"一说为行业报道，单项置信度 mid） [high]
- Gemini: **结论**

Gemini 没有独立的网页收录入口，其内容可见性建立在 Google 搜索体系之上：

1. **爬虫 User-Agent（Gemini 相关）**
   - `Google-Extended`：Google 为生成式 AI 提供的独立产品令牌，用于控制网站内容是否可被用于训练 Gemini 模型、Vertex AI 生成式 AI，以及 Gemini Apps 的"Google 搜索接地（Grounding with Google Search）"。在 robots.txt 中通过 `User-agent: Google-Extended` + `Disallow: /` 屏蔽。
   - `Gemini-Deep-Research` 与 `Gemini-Agent`：Gemini 面向用户的代理/深度研究功能所使用的爬虫令牌，会在用户触发任务时代表用户访问页面（类似 user-triggered fetcher）。
   - `Googlebot` 本身仍是 Google 搜索的抓取器；Gemini App 回答中引用网页主要通过搜索接地完成，底层依赖 Google 搜索索引。

2. **收录机制**
   - **无单独提交入口**：无法直接向 Gemini 提交网站。要让内容出现在 Gemini 回答/AI Overviews 中，需先被 Googlebot 抓取并纳入 Google 搜索索引（即遵守 robots.txt、可被抓取、符合搜索收录规则）。
   - **三层控制**：
     - 屏蔽 `Googlebot` → 内容不会进入 Google 搜索，也就不会出现在 Gemini 的搜索接地结果与 AI Overviews 中（这是从 AI 答案中"除名"的最彻底方式，但代价是失去搜索流量）。
     - 屏蔽 `Google-Extended` → 仅控制内容不被用于 Gemini/Vertex 的训练与 Gemini Apps 接地，**不影响** Google 搜索收录与排名。
     - 使用 `nosnippet` / `max-snippet` 等 meta 标签 → 可限制内容在 AI Overviews 等生成式展示中的摘要使用，同时保留搜索收录。
   - 补充：Gemini 官方文档（deepmind.google）本身也列出 `Google-Extended`、`Gemini-Deep-Research`、`Gemini-Agent` 三个 UA 供网站在 robots.txt 中配置。

**来源**
- https://blog.google/technology/ai/an-update-on-how-you-control-how-your-content-is-used-in-ai-products/
- https://developers.google.com/crawling/docs/crawlers-fetchers/overview-google-crawlers
- https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt
- https://deepmind.google/technologies/gemini/docs/robots-txt/
- https://developers.google.com/search/docs/appearance/ai-overviews

**置信度：high** [high]
- Perplexity: ## 结论

**Perplexity 的爬虫与收录机制（依据官方文档）**

1. **爬虫 User-Agent**：
   - 主索引爬虫：`PerplexityBot`，完整 UA 为 `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)`
   - 另有 `Perplexity-User`（用户提问触发的实时抓取），用于判断搜索结果相关性与抓取科学出版物，Perplexity 称其遵守 noindex 规则
   - 官方建议不要仅依赖 UA 字符串验证，应配合其公布的 IP 段校验

2. **官方 IP 列表**：Perplexity 在 `https://perplexity.ai/perplexitybot.json` 公开 PerplexityBot 与 Perplexity-User 的 IP 范围，供网站管理员识别合法爬虫流量

3. **收录/索引机制**：
   - 采用**实时索引**（indexing in real-time），持续抓取以发现新网页、补充搜索索引
   - **无人工提交入口**：没有 sitemap 提交或手动收录渠道，被抓取与否由爬虫调度决定
   - **遵守 robots.txt**：在 robots.txt 中 `Disallow` PerplexityBot 可阻止抓取；但被屏蔽的页面不会出现在其索引中，也就不会被引用为答案来源
   - 据第三方报道（Wired 等），Perplexity 曾被指使用未声明的爬虫绕过 robots.txt，官方文档对此未直接回应——此点存在争议

**实操建议**：若想被 Perplexity 引用，确保 robots.txt 未屏蔽 PerplexityBot；若想屏蔽，添加 `User-agent: PerplexityBot / Disallow: /` 并参考 IP 列表做服务器端封禁（以防仅屏蔽 UA 不够）。

**来源：**
- https://docs.perplexity.ai/guides/bots
- https://docs.perplexity.ai/guides/secure-ai-bot
- https://docs.perplexity.ai/guides/search-domain-filters
- https://docs.perplexity.ai/changelog/2025-01-08

**置信度：high**（爬虫 UA、IP 验证、robots.txt 机制均来自 Perplexity 官方文档；绕过 robots.txt 的争议部分为第三方报道，单独置信度 mid） [high]
- Claude: **结论：**

关于 Anthropic（Claude）平台的爬虫和收录机制，基于公开文档和权威来源，可确认以下事实：

1. **官方爬虫 User-Agent 字符串**：Anthropic 使用名为 **ClaudeBot** 的网络爬虫，其 User-Agent 标识为 `ClaudeBot/1.0`（或类似变体）。网站管理员可通过 robots.txt 文件中的 `User-agent: ClaudeBot` 指令控制其访问行为。

2. **收录/训练数据机制**：Anthropic 会爬取公开网络内容用于改进其 AI 模型训练，但具体收录策略（如频率、深度、去重规则）未完全公开。Anthropic 承诺尊重 robots.txt 指令，并提供 opt-out 机制（通过 robots.txt 禁止 ClaudeBot 访问）。

3. **排除指令**：若网站不希望内容被用于 Claude 训练，可在 robots.txt 中添加：
   ```
   User-agent: ClaudeBot
   Disallow: /
   ```

**来源：**
- https://docs.anthropic.com/en/docs/claude-bot （Anthropic 官方文档，详细说明 ClaudeBot 的 User-Agent 和 opt-out 机制）
- https://www.anthropic.com/legal/crawling-faq （Anthropic 法律 FAQ，解释爬虫行为和数据使用政策）

**置信度：mid** [mid]
