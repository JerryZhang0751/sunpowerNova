# 平台引用画像 · w7

## Doubao · doubao-seed-2-1-pro-260628 (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 首次搜索未返回有效结果，我换个关键词再查证。
  来源：— | 置信度：外部未验证

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): 结论：截至目前，我无法确认 Qwen（阿里巴巴通义千问）平台存在官方公布的、独立的爬虫 User-agent 字符串或专门的收录机制。阿里巴巴官方文档及主流技术社区均未披露类似 Googlebot、Bingbot 或 GPTBot 的特定爬虫标识符。

来源：无法提供具体 URL（经搜索，阿里巴巴官方帮助文档、Qwen 技术博客及主流爬虫数据库均未收录相关官方信息）

置信度：high
  来源：— | 置信度：外部未验证

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): **结论：**

1. **未找到智谱 AI（Zhipu AI / ChatGLM）官方公布的专用网络爬虫（crawler）User-agent 名称或 IP 段。** 智谱 AI 未像 OpenAI（GPTBot）或 Anthropic（ClaudeBot）那样在公开技术文档中披露其网络爬虫的标识信息。
2. **收录机制：未公开自动化爬虫收录通道。** 智谱 AI 未设立公开的网站提交入口或自动抓取索引机制。目前其模型知识主要来源于：
   - 自主训练的预训练语料（截止时间前已存在的公开网络数据）；
   - API 调用时用户提供的上下文内容；
   - 企业级合作中的定制化数据对接（需签订协议）。
3. ** robots.txt 限制：** 由于未找到官方爬虫标识，无法确认智谱 AI 是否会遵循特定的 robots.txt 规则。若需禁止其抓取，目前只能尝试屏蔽常见的通用爬虫标识，但无法保证有效性。

**来源：** 无法提供有效来源 URL。经检索，智谱 AI 官方技术文档（zhipuai.cn）、开发者文档（bigmodel.cn）及公开技术博客中均未披露爬虫 User-agent 或收录机制的具体信息。

**置信度：low**（因官方未公开相关技术细节，无法通过权威来源验证）
  来源：— | 置信度：外部未验证

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: 我需要联网查证 ChatGPT（OpenAI）的爬虫 User-Agent 与收录机制。让我搜索相关事实。 [外部未验证]
- Gemini: ## 结论

**Gemini（Google）的爬虫与收录机制可确认如下：**

1. **训练数据爬虫标识（User-agent token）：`Google-Extended`**
   - Google 于 2023 年 9 月 28 日公布，网站管理员可通过 robots.txt 使用 `Google-Extended` 这一 product token 来控制内容是否被用于训练 Gemini 模型（覆盖 Gemini Apps 及 Vertex AI 生成式 AI API）。
   - 屏蔽写法：
     ```
     User-agent: Google-Extended
     Disallow: /
     ```
   - 注意：`Google-Extended` 是一个用于 robots.txt 授权控制的产品令牌，不是一个拥有独立抓取行为的全新爬虫；抓取仍由 Google 既有爬虫体系执行。

2. **收录机制：Gemini 无独立收录索引，依赖 Google 搜索体系**
   - Gemini 回答中的实时信息检索基于 Google 搜索（Grounding with Google Search），内容的抓取与收录走 **Googlebot**（User-agent：`Googlebot`）及 Google 搜索的标准索引流程。
   - 屏蔽 `Google-Extended` **不影响**网站在 Google 搜索中的收录与排名（Google 官方明确说明二者相互独立）；反之，若不想被 Gemini 引用/检索到，需按 Google 搜索的标准控制方式（如 robots.txt 屏蔽 Googlebot、`noindex`、`nosnippet` 等）处理，但这会同时影响搜索可见性。

3. **相关其他令牌**：Google 另将 `GoogleOther` 等用于部分非核心索引用途；Gemini 训练控制的核心令牌即 `Google-Extended`。

**来源：**
- https://blog.google/technology/ai/an-update-on-how-we-help-web-publishers-control-their-content-appearing-in-google-ai-experiences-bard-vertex-ai/
- https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers

**置信度：high** [high]
- Perplexity: **结论**

需先如实说明：本次会话中多次调用联网搜索均未返回可用的检索内容，因此以下信息来自我的训练知识，**未经本次联网实时核验**，请谨慎对待。

基于训练知识，关于 Perplexity 的爬虫与收录机制：

1. **官方声明的爬虫 User-Agent**：Perplexity 公开文档中声明了两个 UA：
   - `PerplexityBot`：用于搜索索引的常规爬虫，声称遵守 robots.txt。
   - `Perplexity-User`：由用户实时提问触发的抓取（fetch），官方称其代表用户行为，因此不完全受 robots.txt 约束。
2. **IP 验证**：Perplexity 据称在其官网公布爬虫 IP 段（JSON 文件），供网站管理员核验爬虫真伪。
3. **收录机制**：Perplexity 是"答案引擎"，结合自有索引 + 实时抓取（RAG 模式）。被收录/引用的主要途径包括：允许 PerplexityBot 抓取、站点被其索引、以及 Bing 等第三方索引（有报道称其部分依赖 Bing 索引）。
4. **争议（重要背景）**：2024 年 6 月 Wired 和开发者 Robb Knight 的调查显示，Perplexity 被指控使用未公开的爬虫（来自 AWS IP、伪装 UA）绕过 robots.txt 抓取声明禁止的网站。即"官方声明的机制"与"实际行为"之间存在争议。

**来源（来自训练知识，本次未能联网核验，请自行确认 URL 是否仍有效）**：
- https://docs.perplexity.ai/guides/bots （Perplexity 官方爬虫文档）
- https://www.perplexity.ai/hub/legal （法律/合规信息页）
- https://www.wired.com/story/perplexity-is-a-bullshit-machine/ （Wired 2024 年 6 月调查报道）
- https://rknight.me/blog/perplexity-ai-is-lying-about-its-user-agent/ （Robb Knight 的实测分析）

**置信度：mid**（核心事实与多方公开报道一致，可信度较高；但本次未能实时联网核验，URL 有效性和文档最新内容无法确认，且 Perplexity 的爬虫政策可能在 2024 年争议后有更新） [mid]
- Claude: **结论：**

⚠️ 先说明：本次会话中我**无法实际执行联网检索**（当前环境未提供可用的搜索工具），以下内容来自我的训练数据（存在知识截止时间），未能做实时验证，故整体置信度不宜给 high。

关于 Claude（Anthropic）的爬虫与收录机制，据训练数据：

1. **主要爬虫 User-Agent：**
   - `ClaudeBot` — Anthropic 最主要的网页爬虫，用于抓取可能用于模型训练的公开网页内容，官方声明遵守 robots.txt。
   - `anthropic-ai`、`Claude-Web` — 早期使用过的 User-Agent，现多被视为旧标识。
   - `Claude-User` — 当 Claude.ai 用户在对话中触发网页抓取（如用户粘贴 URL）时使用的 UA，与用户主动行为绑定，而非批量抓取。
   - `Claude-SearchBot` — 随 Claude 联网搜索功能（约 2025 年）新增的搜索相关爬虫（此项我对确切名称把握度较低，需以官方文档为准）。

2. **收录/屏蔽机制：**
   - 网站可通过 robots.txt 屏蔽训练抓取：
     ```
     User-agent: ClaudeBot
     Disallow: /
     ```
   - Anthropic 官方建议：屏蔽 `ClaudeBot` 可阻止内容被用于训练；是否屏蔽 `Claude-User` 会影响 Claude 用户能否让模型读取该站内容。
   - 2024 年曾有 iFixit、Freelancer 等站点公开抱怨 ClaudeBot 高频抓取的新闻报道，侧面印证其在公开网络大规模抓取。

**来源：**
- https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler （Anthropic 官方支持文档，训练数据中确认存在，但本次未能实时打开验证其当前内容）
- https://darkvisitors.com/agents/claudebot （第三方 AI 爬虫名录，收录 ClaudeBot 相关 UA 信息，未实时验证）

**置信度：mid**（核心 UA 名称 ClaudeBot / robots.txt 屏蔽机制把握较高；Claude-SearchBot 及最新政策细节未经实时查证，建议以 Anthropic 官方文档当前版本为准） [mid]
