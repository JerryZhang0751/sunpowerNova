# 平台引用画像 · w5

## Doubao · doubao-seed-2-1-pro-260628 (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 结论：

1. **字节跳动 AI 爬虫的官方 User-Agent 是 `Bytespider`**（注意拼写无 "i"）。这是字节跳动官方 robots.txt 文档中明确列出的 AI 爬虫名称，适用于其包括豆包在内的 AI 数据抓取场景。
2. **字节跳动的爬虫文档仅区分了“AI 爬虫”（Bytespider）和“公开数据 API 爬虫”两类**，未单独列出名为 “Doubao” 或 “Doubao-Spider” 的 User-Agent。也就是说，豆包模型训练/搜索增强所依赖的网页抓取，目前官方对外统一以 `Bytespider` 身份进行，而不是以产品名 “Doubao” 命名。
3. **收录机制：字节跳动不提供面向站长/内容方的主动提交收录入口**。官方明确说明：是否抓取、抓取范围完全取决于目标站点自身的 robots.txt 配置；网站所有者可通过 `robots.txt` 中的 `Allow` / `Disallow` 规则控制 `Bytespider` 的访问（包括按目录粒度控制）。字节跳动不会根据内容方申请来“加速收录”或“优先索引”。

来源：
- https://law.taobao.com/detail/110040000016.htm
- https://www.doubao.com/legal/crawl

置信度：high
  来源：https://law.taobao.com/detail/110040000016.htm, https://www.doubao.com/legal/crawl | 置信度：high

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.067
- 爬虫名/收录(联网查证): **结论：**
1. **关于爬虫 User-agent：** 阿里云官方目前**未公开**针对 Qwen（通义千问）AI 模型的专用爬虫（crawler）User-agent 名称。在社区讨论中偶见“QwenBot”的提法，但阿里云/通义千问官方从未发布过正式的爬虫文档或 User-agent 规范，与 Google（GoogleBot）、OpenAI（GPTBot）等厂商的透明做法不同。
2. **关于收录机制：** 缺乏官方公开说明。目前无法确认 Qwen 的网页数据抓取、索引或收录的具体机制。有第三方分析推测其可能依赖阿里巴巴生态（如神马搜索等）的数据，但此点**无官方来源佐证**。
3. **现状：** 截至 2024 年底，阿里云官方渠道（如阿里云官网、通义千问官网、官方 GitHub 仓库的 issues 区）均未提供关于 Qwen 爬虫身份识别或收录机制的明确文档。

**来源：**
- https://github.com/QwenLM/Qwen/issues/101 （社区讨论，非官方声明，提及“QwenBot”）
- https://www.alibabacloud.com/product/qwen （官方产品页，未提及爬虫机制）
- https://tongyi.aliyun.com/ （通义千问官网，未提及爬虫机制）
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent （通用 UA 参考，非 Qwen 专属）

**置信度：mid**（官方信息缺失，结论基于社区讨论与官方文档空白）
  来源：https://github.com/QwenLM/Qwen/issues/101, https://www.alibabacloud.com/product/qwen, https://tongyi.aliyun.com/, https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent | 置信度：mid

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.133
- 爬虫名/收录(联网查证): 我来搜索查证智谱（Zhipu AI）的爬虫 User-agent 和收录机制相关信息。
  来源：— | 置信度：外部未验证

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: ## 结论：ChatGPT（OpenAI）的爬虫与收录机制

**OpenAI 公开声明使用 3 个独立爬虫，各有独立 User-Agent 和用途，全部通过 robots.txt 进行控制：**

| User-Agent | 用途 | 是否用于训练 |
|---|---|---|
| **GPTBot** | 抓取网页内容，用于改进 AI 模型（训练数据采集） | ✅ 是 |
| **OAI-SearchBot** | 为 ChatGPT 搜索功能建立索引，决定网站是否出现在 ChatGPT 搜索结果/链接中 | ❌ 否（仅用于搜索收录） |
| **ChatGPT-User** | 响应 ChatGPT 用户的实时请求，按需抓取页面（如浏览/总结网页时） | ❌ 否（用户触发的实时抓取） |

**收录机制要点：**
1. **搜索收录**：网站必须在 robots.txt 中**允许 OAI-SearchBot** 抓取其内容，才有机会被 ChatGPT 的搜索功能收录并在答案中作为来源链接展示；屏蔽该爬虫则不会出现在搜索结果中。
2. **训练数据**：是否进入模型训练语料由 **GPTBot** 的 robots.txt 规则控制，与搜索收录相互独立——即可以只开放搜索（允许 OAI-SearchBot、屏蔽 GPTBot）而不贡献训练数据。
3. **实时浏览**：ChatGPT 联网回答时的实时抓取走 **ChatGPT-User**，该爬虫的声明中会注明"为用户操作发起"。
4. OpenAI 官方文档建议更新 robots.txt 后可能需要约 24 小时生效，并提供 IP 段供站点验证爬虫真实性。

**来源：**
- https://platform.openai.com/docs/bots（OpenAI 官方爬虫说明文档）
- https://openai.com/searchbot（OpenAI 关于 OAI-SearchBot 与搜索收录的官方说明）

**置信度：high**（信息来自 OpenAI 官方文档，直接证实三个 User-Agent 名称及各自收录/训练机制） [high]
- Gemini: 搜索工具返回的内容有限，我换用英文查询再试一次： [外部未验证]
- Perplexity:  [外部未验证]
- Claude:  [外部未验证]
