# 平台引用画像 · w2

## Doubao · doubao-seed-2-1-pro (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 搜索结果为空，我换个查询再试。
  来源：— | 置信度：外部未验证

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): **结论：**

关于 Qwen（通义千问）平台的爬虫 User-Agent 及收录机制，经多轮搜索查证，**目前无法确认**以下关键信息：

1. **爬虫 User-Agent**：阿里云/Qwen 官方未公布其专用爬虫的 User-Agent 字符串。搜索结果显示，阿里云安全产品有爬虫威胁情报库和 Bot 流量管理功能，但这属于其安全防护产品能力，而非 Qwen 自身爬虫的标识。

2. **收录机制**：未发现 Qwen 官方发布的网页收录标准、提交入口或索引机制说明文档。Qwen 作为大语言模型，其训练数据来源主要依赖大规模预训练语料库，而非传统的主动网页爬取收录模式。

**来源：**
- https://www.aliyun.com/product/security （阿里云安全产品页面，提及爬虫管理但未披露具体 UA）
- https://help.aliyun.com/document_detail/ （阿里云帮助文档，未检索到 Qwen 爬虫相关条目）

**置信度：low**
  来源：https://www.aliyun.com/product/security, https://help.aliyun.com/document_detail/ | 置信度：low

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): 
  来源：— | 置信度：外部未验证

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: 搜索返回为空，我换个查询再试： [外部未验证]
- Gemini: **结论：**

Gemini（Gemini Apps / Vertex AI 的 grounding）的爬虫与收录机制如下：

1. **无独立爬虫 UA 字符串**：控制 Gemini 抓取的产品令牌是 **`Google-Extended`**，但它只是一个 robots.txt 的 product token，**没有独立的 HTTP User-Agent 字符串**，实际抓取仍由现有 Google 爬虫（Googlebot 等）执行。在 robots.txt 中写 `User-agent: Google-Extended / Disallow: /` 即可阻止内容被用于改进 Gemini Apps 和 Vertex AI 生成式 API（含 grounding）。
2. **不影响 Google 搜索收录**：屏蔽 `Google-Extended` 不会将网站从 Google 搜索中移除，也不影响搜索排名；Gemini 本身没有独立的搜索索引，其联网回答（Grounding with Google Search）依赖 Google 搜索索引与 Googlebot 抓取。
3. **用户触发的实时抓取**：当 Gemini/Vertex AI 用户请求需要实时访问某页面时，会使用"用户触发抓取器"（user-triggered fetchers），其中包括 UA 为 **`Google-CloudVertexBot`** 的抓取器（受 `Google-CloudVertexBot` 令牌控制），这类抓取不遵守常规爬虫调度，而是按需发起。

**来源：**
- https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
- https://developers.google.com/search/blog/2023/09/google-extended

**置信度：high** [high]
- Perplexity: 结论：  
- Perplexity 官方文档列出两个与用户访问/索引相关的标识：`PerplexityBot`（indexing crawler，把网页索引进 Perplexity 搜索索引；完整支持 robots.txt 允许/禁止）和 `Perplexity-User`（user-driven fetcher，代表用户实时请求去抓取页面；官方说明其通常忽略 robots.txt）。UI/API 回答里的 citations 主要来自 `PerplexityBot` 索引；仅当索引无匹配时才用 `Perplexity-User` 实时抓取。  
- 收录机制：未见公开的“站长平台/主动提交收录”入口；收录本质依赖 `PerplexityBot` 抓取与索引，可用 robots.txt 控制。Perplexity 还发布过 robots.txt 示例（Allow/Disallow）。另有官方 “Search Domain Filters”（查询时 allowlist/denylist 域名，最多 20 个），它不是“提交收录”，而是搜索时的域名过滤；Search API 使用预构建索引、按子文档/片段级检索并实时排序。  
- 无法确认：是否存在“保证收录”或“提交 sitemap 后必收录”的机制，未见官方说明。

来源：  
- 来源：https://docs.perplexity.ai/guides/bots  
- 来源：https://docs.perplexity.ai/changelog/introducing-perplexity-robots-txt  
- 来源：https://docs.perplexity.ai/guides/search-domain-filters  

置信度：high [high]
- Claude: ## 结论

**Claude 的官方爬虫是 `ClaudeBot`**，由 Anthropic 运营。查证结果如下：

### 1. 爬虫 User-Agent
- **官方爬虫名称**：`ClaudeBot`（完整 UA 字符串形如 `Mozilla/5.0 ... ClaudeBot/1.0; +https://www.anthropic.com/claudebot`）。
- **屏蔽方法**：在网站 `robots.txt` 中添加：
  ```
  User-agent: ClaudeBot
  Disallow: /
  ```
  即可禁止 ClaudeBot 抓取网站内容。

### 2. 收录 / 检索机制
- **Claude 不维护传统搜索引擎式的"收录索引"**。其搜索功能（web search tool）是**按需实时检索**：
  - Claude 会根据对话判断是否需要搜索，生成查询词，调用搜索服务获取结果，并附带引用来源。
  - 开发者可通过 API 配置 `allowed_domains` / `blocked_domains` 来控制允许或禁止抓取的域名。
- **robots.txt 合规**：Claude 的网页抓取器会尊重目标网站的 robots.txt 指令（Anthropic 官方文档明确说明）。
- **网站端验证**：若想确认 Claude 是否能访问你的网站，可直接检查服务器日志中是否出现 `ClaudeBot` UA，或通过 `curl https://yourdomain.com/robots.txt` 检查 robots.txt 配置。

**来源：**
- https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- https://code.claude.com/docs/en/robots-txt

**置信度：high** [high]
