# src/geo/research/kimi.py
from __future__ import annotations
import json, logging, re
from geo.shared.config import settings
from geo.research.models import FeatureAggregates, PlaybookConclusion

log = logging.getLogger("research.kimi")
_SYS_SYNTH = (
    "你是 GEO 研究 agent。只能依据所给的 FeatureAggregates（JSON）与少量真实回答片段归纳结论。"
    "输出 JSON {conclusions:[{id,category(format|source|platform|problem_space),conclusion,"
    "sample_n,cited_n,platforms,confidence(high|mid|low),action,examples[],bucket_key}]}。"
    "纪律：sample_n 必须等于所给数据，不得改写或杜撰；不得编造 URL；低样本标 low。"
    "若 category 为 format，bucket_key 必须设为以下之一：comparison_table|qa|list|definition|spec_card。"
)

def _kimi_chat(messages: list[dict], tools: list | None = None, timeout: int = 120) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    kwargs = dict(model="kimi-k3", messages=messages, temperature=1)  # kimi-k3 强制 temp=1
    if tools: kwargs["tools"] = tools
    if not tools: kwargs["response_format"] = {"type": "json_object"}
    r = c.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""

def synthesize(aggregates: FeatureAggregates, examples: list[dict], *, chat_fn=_kimi_chat) -> list[PlaybookConclusion]:
    user = "AGGREGATES:\n" + json.dumps(_agg_to_dict(aggregates), ensure_ascii=False) + \
           "\nEXAMPLES:\n" + json.dumps(examples[:5], ensure_ascii=False)
    try:
        raw = chat_fn([{"role":"system","content":_SYS_SYNTH},{"role":"user","content":user}])
        data = json.loads(raw)
    except Exception as e:
        log.warning("synthesize failed (%s); returning []", e)
        return []
    sample_bound = aggregates.coverage.l3_resolved or 0
    out = []
    for c in data.get("conclusions", []):
        try:
            sn = int(c.get("sample_n", 0))
            if sn > sample_bound: sn = sample_bound      # refuse invented sample_n
            out.append(PlaybookConclusion(
                id=c["id"], category=c.get("category",""), conclusion=c.get("conclusion",""),
                sample_n=sn, cited_n=c.get("cited_n"), platforms=c.get("platforms",[]),
                confidence=c.get("confidence","low"), action=c.get("action",""),
                examples=c.get("examples",[]), bucket_key=c.get("bucket_key","")))
        except Exception as e:
            log.warning("skip malformed conclusion %r: %s", c, e)
    return out

def _agg_to_dict(a: FeatureAggregates) -> dict:
    return {"week":a.week,"coverage":a.coverage.__dict__,
            "formats":[b.__dict__ for b in a.formats],"sources":a.sources,
            "platforms":a.platforms,"problem_space":a.problem_space}

_SYS_WEB = (
    "联网搜索查证 AI 平台的爬虫名/收录机制等外部事实。"
    "回答格式：先给结论，再列「来源：<url>」（至少一个），最后「置信度：high|mid|low」。"
    "查不到就如实说无法确认，禁止杜撰 URL。"
)

def _parse_web_answer(text: str) -> dict:
    sources = re.findall(r"https?://\S+", text or "")
    conf = "外部未验证"
    m = re.search(r"置信度[*_]*[:：]\s*(high|mid|low|外部未验证)", text or "", re.I)
    if m: conf = m.group(1).lower()
    if not sources and "无法确认" in (text or ""): conf = "外部未验证"
    return {"answer": (text or "").strip(), "sources": sources, "confidence": conf}

_WEB_TOOLS = [{"type": "builtin_function", "function": {"name": "$web_search"}}]

_NUDGE = ("请继续完成查证：如需可再调用搜索，最终按格式给出结论+来源URL+置信度。")

def _drive_web_search(create, messages: list[dict], *, max_rounds: int = 10) -> str:
    """kimi-k3 $web_search 工具循环：模型发起 tool_call → arguments 原封不动回传(role=tool)
    → 服务端执行联网搜索 → finish_reason=stop 终答。
    偶发缺陷（2026-08-18 探针实测）：模型想续搜/搜索无果时 API 返 stop+空 content，
    此时注入催答消息（保留 tools 让它可继续搜）直至出实质终答；超 max_rounds 轮返空。"""
    msgs = list(messages)
    for _ in range(max_rounds):
        r = create(model="kimi-k3", messages=msgs, temperature=1, tools=_WEB_TOOLS)
        ch = r.choices[0]
        m = ch.message
        tcs = getattr(m, "tool_calls", None)
        if ch.finish_reason == "tool_calls" and tcs:
            msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                {"id": t.id, "type": "function",
                 "function": {"name": t.function.name, "arguments": t.function.arguments}}
                for t in tcs]})
            for t in tcs:
                msgs.append({"role": "tool", "tool_call_id": t.id, "name": t.function.name,
                             "content": t.function.arguments})   # 原样回传，服务端执行
            continue
        if (m.content or "").strip():
            return m.content
        msgs.append({"role": "user", "content": _NUDGE})   # 空终答 → 催答（可继续搜）
    log.warning("web_search loop exceeded %d rounds; giving up", max_rounds)
    return ""

def _web_search_chat(messages: list[dict], tools=None, timeout: int = 180) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    return _drive_web_search(c.chat.completions.create, messages)

def web_search_verify(items: list[dict], *, chat_fn=None) -> dict:
    # 官方协议（platform.kimi.com/docs/guide/use-web-search，2026-08-18 探针实测）：
    # builtin_function/$web_search → 模型返 tool_calls → arguments 原样回传(role=tool)
    # → 服务端执行搜索 → 终答。旧 builtin_tools schema 被 API 400 拒。
    tools = _WEB_TOOLS
    out = {}
    for it in items:
        plat, fact = it["platform"], it.get("fact","crawler_and_inclusion")
        user = f"平台：{plat}\n查证：{fact}（爬虫 User-agent / 收录机制）"
        try:
            raw = (chat_fn or _web_search_chat)(
                [{"role":"system","content":_SYS_WEB},{"role":"user","content":user}],
                tools=tools, timeout=180)
            out[plat] = _parse_web_answer(raw)
        except Exception as e:
            log.warning("web_search_verify %s failed: %s", plat, e)
            out[plat] = {"answer":"", "sources":[], "confidence":"外部未验证"}
    return out
