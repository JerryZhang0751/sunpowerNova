# 平台引用画像 · w3

## Doubao · doubao-seed-2-1-pro (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 结论：可确认字节跳动/头条系公开网络爬虫 UA 常见为 `Bytespider`（早期/相关资料亦见 `Bytespider; ToutiaoSpider` 一类标识），robots 可通过 `User-agent: Bytespider` / `Disallow: /` 等方式封禁；但我未查到 Doubao 单独公开其“爬虫 User-agent 名单”或“收录/索引机制”的官方文档，因此 Doubao 是否使用独立 UA、具体如何触发收录与排名，无法确认。实务上应按字节系爬虫治理：用 robots.txt 管理 `Bytespider`，并结合日志中的真实 UA/IP 反查核验。

来源：https://darkvisitors.com/agents/user-agents/bytespider  
来源：https://github.com/sameermastan/robotstxt/blob/master/Bytespider.txt  
来源：https://www.petalsearch.com/terms?c=11109  

置信度：mid
  来源：https://darkvisitors.com/agents/user-agents/bytespider, https://github.com/sameermastan/robotstxt/blob/master/Bytespider.txt, https://www.petalsearch.com/terms?c=11109 | 置信度：mid

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 结论：无法确认。本次联网检索未返回可核验的公开来源，不能证实 Qwen（通义千问）官方公布了专属爬虫 User‑Agent，也不能证实存在面向站长的“主动收录/提交”机制。可审慎推断（非结论）：阿里系搜索侧已知 UA 为神马/UC 的 `YisouSpider`，但它不等同于 Qwen 大模型训练或问答引用爬虫；若要限制，只能在 robots.txt 中按已知 UA 处理，无法精准针对“Qwen 爬虫”。

来源：无（未获取到可核验 URL，按要求不杜撰链接）

置信度：low
  来源：— | 置信度：外部未验证

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): 结论：无法通过公开搜索确认智谱（Zhipu）官方爬虫的具体 User-agent 字符串及其收录机制细节。基于已有知识，智谱 AI 的网页爬取活动通常关联以下标识，但未经当前搜索验证：

**已知信息（待验证）：**
- **爬虫标识**：`ZhipuAI-Bot` 或 `ChatGLM-Spider`（出现于第三方网站日志分析）
- **用途**：用于 GLM 系列大模型的训练数据收集及联网搜索功能
- **收录机制**：未公开详细文档，推测采用通用网页爬取标准（遵守 robots.txt）

**无法确认项：**
- 官方是否公布爬虫 IP 段
- 是否有专门的站长平台提交入口（类似 Google Search Console）
- 具体的爬取频率控制参数

来源：无（本次搜索未返回有效结果）

置信度：low

**建议核实途径：**
1. 查看智谱AI官方文档（https://open.bigmodel.cn/）的"数据采集"或"合规说明"章节
2. 检查自身网站日志中 `Zhipu` 或 `ChatGLM` 相关请求头
3. 直接联系智谱技术支持获取 robots.txt 配置建议
  来源：https://open.bigmodel.cn/）的"数据采集"或"合规说明"章节 | 置信度：low

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: **结论：ChatGPT / OpenAI 的爬虫与收录机制（已查证）**

OpenAI 官方公开了三个独立的爬虫 User-Agent，分别对应不同用途，可通过 robots.txt 单独控制：

1. **GPTBot** — 用于抓取网页内容训练大模型（可能影响未来模型的知识，但不直接决定 ChatGPT 回答时是否引用你）。
   UA 标识：`GPTBot/1.1; +https://openai.com/gptbot`

2. **OAI-SearchBot** — 用于 **ChatGPT Search** 的搜索索引收录。这是决定你的网站能否出现在 ChatGPT 搜索/联网回答引用来源中的关键爬虫。它不参与模型训练。
   UA 标识：`OAI-SearchBot/1.0; +https://openai.com/searchbot`

3. **ChatGPT-User** — 用户实时提问触发的按需访问（browsing/插件类实时抓取），不做索引、不用于训练。
   UA 标识：`ChatGPT-User/1.0; +https://openai.com/bot`

**收录机制要点：**
- 三者相互独立：屏蔽 GPTBot **不会**影响 OAI-SearchBot 的搜索收录（OpenAI 官方明确说明）。
- ChatGPT Search 除自有索引外，还与第三方搜索（Bing）合作，因此 Bing 收录状态也会间接影响 ChatGPT 引用。
- OpenAI 公布了各爬虫的 IP 段（JSON 文件），可用于防火墙白名单校验。
- robots.txt 生效有缓存延迟（官方称约 24 小时内更新）。

**来源：**
- 来源：https://platform.openai.com/docs/bots
- 来源：https://openai.com/searchbot
- 来源：https://help.openai.com/en/articles/9237897-chatgpt-search

**置信度：high** [high]
- Gemini: I'll research the crawler user-agents and inclusion mechanisms for Google's Gemini platform. [外部未验证]
- Perplexity: **结论：**

Perplexity 官方文档确认其使用两个不同的 User-Agent 爬虫，且收录机制各异：

1. **PerplexityBot**
   - 用途：抓取并索引网页，用于维护 Perplexity 的网页索引，以便在搜索结果中将你的网站作为引用来源（citations）呈现。
   - 收录机制：属于**主动爬虫/索引**模式。页面需被 PerplexityBot 抓取并进入其索引后，才有机会在答案中被引用。
   - robots.txt：适用。发布者可以通过 `User-agent: PerplexityBot` + `Disallow` 来屏蔽；Perplexity 还公布了爬虫 IP 段供验证真伪（因有恶意爬虫伪装该 UA）。

2. **Perplexity-User**
   - 用途：支持 Perplexity 的用户端产品（如 Comet 浏览器助手），代表**具体用户的实时操作**去获取页面（即时代理式抓取，agentic retrieval）。
   - robots.txt：**不适用**（通常忽略 robots.txt），因为它不属于爬虫行为，而是用户触发的请求。

简言之：想让内容被 Perplexity 收录/引用，需允许 PerplexityBot 抓取；而 Perplexity-User 走的是"用户代理"通道，无法靠 robots.txt 拦截。

来源：https://docs.perplexity.ai/guides/bots
来源：https://developers.cloudflare.com/bots/concepts/bot/verified-bots/perplexity/
来源：https://incognitoland.com/posts/perplexitybot-ai-crawler-exposed

置信度：high（Perplexity 官方文档直接确认了两个 UA 的名称、用途及 robots.txt 行为） [high]
- Claude: **结论：**

- **爬虫 UA**：Anthropic 官方网页爬虫 User-agent 为 **`ClaudeBot`**（完整形式类似 `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)`）。此外，Claude 聊天中用户主动触发网页访问时使用的 UA 为 **`Claude-User`**（实时抓取，内容不用于训练）。
- **收录/抓取机制**：ClaudeBot 抓取公开网页，可能用于模型训练；它遵守 `robots.txt` 中的 Disallow 规则——站长需在 robots.txt 中显式禁止 `ClaudeBot` 才能阻止抓取。Anthropic 称会控制抓取频率、尊重网站负载。**没有面向站长的主动提交收录入口**（类似 Google Search Console 的提交机制不存在），网站被纳入训练数据取决于爬虫是否能发现并允许访问该页面。

**来源：** https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler

**置信度：high** [high]
