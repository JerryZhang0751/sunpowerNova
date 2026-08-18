# 平台引用画像 · w1

## Doubao · doubao-seed-2-1-pro (字节 Ark)
- 引用偏好(数据,n=15): mention=0.133 citation=0.0
- 爬虫名/收录(联网查证): 结论：

Doubao（豆包）没有面向全网公开文档的独立公开爬虫名/收录机制；可核实的事实是，豆包由字节跳动推出，页面明确提示其内容由 AI 生成、仅供参考，并自称“全能 AI 助手”。同时，字节跳动的搜索基础设施与头条系搜索高度相关；在字节跳动/头条体系内，网站收录通常依赖头条搜索站长平台提交与爬虫抓取，而不是一个单独标注为“DoubaoBot”的公开 UA 机制。就公开可核验资料而言，我无法确认豆包对外公布了独立的 crawler User-agent 名称，也无法确认存在专门的“豆包收录入口”。

来源：https://www.doubao.com/  
来源：https://zhanzhang.toutiao.com/  
来源：https://zhanzhang.toutiao.com/page/1  
来源：https://www.doubao.com/chat/

置信度：mid
  来源：https://www.doubao.com/, https://zhanzhang.toutiao.com/, https://zhanzhang.toutiao.com/page/1, https://www.doubao.com/chat/ | 置信度：mid

## Qwen · qwen3.7-plus (阿里 DashScope)
- 引用偏好(数据,n=15): mention=0.133 citation=0.133
- 爬虫名/收录(联网查证): 结论：Qwen（通义千问）官方文档**未公开独立的爬虫 User-agent 名称**或针对 AI 训练的专项收录机制。作为阿里巴巴旗下产品，其网页数据获取主要依托阿里生态体系，可能涉及以下可查证途径：

1. **阿里云爬虫标识**：阿里云官方文档披露了 `AliyunSecBot`（安全检测）和 `YisouSpider`（神马搜索，阿里旗下移动搜索）等爬虫，但未明确这些爬虫的数据是否直接用于 Qwen 大模型训练。
2. **Robots 协议遵循**：阿里云文档提及爬虫遵循 robots.txt，但未列出 Qwen 专用的爬虫名称（如 GPTBot、ClaudeBot 这类明确标识）。
3. **API 数据接入**：Qwen 主要通过 API 接口获取实时数据，而非依赖传统网页爬虫收录。

来源：
- https://help.aliyun.com/zh/security-center/user-guide/aliyun-security-crawler (AliyunSecBot 官方说明)
- https://help.aliyun.com/document_detail/200000.html (阿里云爬虫 robots 协议规范)
- https://qianwen.aliyun.com/ (Qwen 官方页面，无爬虫相关技术文档)

置信度：low（官方未公开具体爬虫名称，以上仅为关联性推断）
  来源：https://help.aliyun.com/zh/security-center/user-guide/aliyun-security-crawler, https://help.aliyun.com/document_detail/200000.html, https://qianwen.aliyun.com/ | 置信度：low

## Zhipu · glm-5.2 (BigModel)
- 引用偏好(数据,n=15): mention=0.133 citation=0.133
- 爬虫名/收录(联网查证): **结论：无法确认。**

我本次无法完成有效的联网检索，因此**不能提供经核实的智谱（Zhipu AI）爬虫 User-Agent 名称或官方收录机制文档**。为了避免误导，我不会凭记忆给出未验证的 UA 字符串（如 "ChatGLM-Spider" 之类的说法在公开资料中并无可靠的官方文档佐证，我不应杜撰）。

已知可参考的公开信息（未经本次核实，仅供参考）：
- 智谱官网域名为 `zhipuai.cn` / `bigmodel.cn`，其 robots.txt 可公开访问查看，这是确认官方爬虫声明最直接的一手来源。
- 国内大模型厂商（如字节、百度、月之暗面）通常会在帮助文档或 robots.txt 中公布爬虫 UA，但智谱是否已公开类似文档，我本次无法验证。

**建议的自行核实途径：**
1. 访问 `https://www.zhipuai.cn/robots.txt` 和 `https://open.bigmodel.cn` 查看官方声明；
2. 在服务器日志中检索包含 "zhipu"、"chatglm"、"glm" 等关键词的 User-Agent；
3. 查阅智谱开放平台帮助中心/开发者文档中的合规与爬虫说明。

**来源：** 无法提供（本次未能成功检索到可验证的官方页面，故不列任何 URL，以免杜撰）

**置信度：low**
  来源：https://www.zhipuai.cn/robots.txt`, https://open.bigmodel.cn` | 置信度：low

## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）
- ChatGPT: 结论：ChatGPT（OpenAI）相关爬虫/抓取主要有三类 UA，需要在 robots.txt 中分别管理：OAI-SearchBot（用于搜索索引/让网站可能出现在 ChatGPT search 结果中）、ChatGPT-User（用于 ChatGPT 用户在对话中触发/自定义动作时的实时访问，不用于训练抓取、也不自动进入搜索索引）、GPTBot（用于抓取可能用于改进模型的内容；封禁它不等于封禁搜索收录）。因此，若目标是“被 ChatGPT 搜索收录/引用”，关键是允许 OAI-SearchBot 抓取并提供可被抓取的公开页面；若只想避免被训练使用，则重点封禁 GPTBot，但需注意这并不会直接等同于退出 ChatGPT 搜索索引（OpenAI 文档对“训练数据移除”与“搜索索引”是分开描述的）。

来源：https://platform.openai.com/docs/bots  
来源：https://platform.openai.com/docs/bots/echoes  
来源：https://platform.openai.com/docs/bots/overview.md  

置信度：high [high]
- Gemini: **结论：**

Gemini 没有独立命名的专属网络爬虫，其内容获取依赖 Google 搜索体系，核心机制如下：

1. **AI 训练控制令牌：Google-Extended**
   - Google 于 2023 年 9 月推出了独立的 robots.txt 令牌 `Google-Extended`，网站可通过以下方式禁止内容被用于训练 Gemini 及 Vertex AI 模型：
     ```
     User-agent: Google-Extended
     Disallow: /
     ```
   - 注意：Google-Extended 是一个"控制令牌"，它本身**不抓取网页**（无独立爬虫 IP 行为），而是作为信号告诉 Google 不要使用已通过其他途径获得的内容进行 AI 训练。

2. **搜索索引爬虫：Googlebot**
   - Gemini 的回答（尤其是带引用来源的实时回答）依赖 Google 搜索索引，该索引由 `Googlebot` 抓取建立。被 Googlebot 收录是内容出现在 Gemini 答案中的主要前提。
   - 其他相关 UA 还包括 `GoogleOther`（用于研发等非搜索索引的抓取）等。

3. **收录机制：无独立提交入口**
   - 不存在"向 Gemini 提交收录"的单独通道；网站被 Gemini 引用的路径是：被 Googlebot 正常抓取索引 → Gemini 在回答时通过检索（RAG）调用搜索结果。
   - 因此优化方向与传统 SEO 一致：保证可抓取性、结构化数据、内容质量等。

**来源：**
- 来源：https://developers.google.com/search/blog/2023/09/google-extended
- 来源：https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers

**置信度：high** [high]
- Perplexity: **结论：**  
Perplexity 平台的内容爬取和收录机制如下：  
1. **爬虫 User-agent：** Perplexity 使用两个公开的爬虫标识——`PerplexityBot`（用于网页索引）和 `Perplexity-User`（用于用户实时请求时获取页面内容）。网站可通过 robots.txt 屏蔽 `PerplexityBot` 来拒绝被索引。  
2. **收录机制：** Perplexity 没有公开的网站主动提交收录渠道（如 Google Search Console）。其索引主要依赖自身爬虫对公开网页的抓取，同时可能通过用户搜索行为触发对特定页面的实时抓取与临时分析。官方强调对 `robots.txt` 的尊重，未提供其他主动收录方式。  

**来源：**  
- https://docs.perplexity.ai/docs/bot （Perplexity 官方文档，说明 Bot 行为与 User-agent）  
- https://docs.perplexity.ai/docs/crawler （官方关于爬虫机制的说明）  
- https://www.searchviu.com/en/perplexity-ai-crawler/ （第三方对 Perplexity 爬虫行为的分析）  
- https://www.onely.com/blog/perplexity-ai-crawler/ （关于 Perplexity 收录机制与 SEO 影响的解读）  

**置信度：high** [high]
- Claude: 前两次搜索返回内容为空，我换个查询再试。 [外部未验证]
