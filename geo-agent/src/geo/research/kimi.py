# src/geo/research/kimi.py
from __future__ import annotations
import json, logging
from geo.shared.config import settings
from geo.research.models import FeatureAggregates, PlaybookConclusion

log = logging.getLogger("research.kimi")
_SYS_SYNTH = (
    "你是 GEO 研究 agent。只能依据所给的 FeatureAggregates（JSON）与少量真实回答片段归纳结论。"
    "输出 JSON {conclusions:[{id,category(format|source|platform|problem_space),conclusion,"
    "sample_n,cited_n,platforms,confidence(high|mid|low),action,examples[]}]}。"
    "纪律：sample_n 必须等于所给数据，不得改写或杜撰；不得编造 URL；低样本标 low。"
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
                examples=c.get("examples",[])))
        except Exception as e:
            log.warning("skip malformed conclusion %r: %s", c, e)
    return out

def _agg_to_dict(a: FeatureAggregates) -> dict:
    return {"week":a.week,"coverage":a.coverage.__dict__,
            "formats":[b.__dict__ for b in a.formats],"sources":a.sources,
            "platforms":a.platforms,"problem_space":a.problem_space}
