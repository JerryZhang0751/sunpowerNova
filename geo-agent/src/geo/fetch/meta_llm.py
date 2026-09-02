from __future__ import annotations
import json
import logging
from geo.shared.config import MODELS
from geo.shared.kimi_client import make_kimi_client

log = logging.getLogger(__name__)

_SYS = ("Extract semantic metadata from the page text as JSON ONLY. Keys: "
        "page_type (product|faq|blog|comparison|spec|forum|qa|news|other), "
        "has_definition_segment (bool), has_faq_block (bool), datapoint_count (int), "
        "has_author_byline (bool), has_publish_date (bool), cites_external_sources (bool).")

def extract_semantic(text: str) -> tuple[dict, bool]:
    """返回 (semantic, degraded)。degraded=True = Kimi 失败/解析失败——
    semantic 为空但非静默:落 L3Source.semantic_degraded,评估与报告可见(§12)。
    空文本=无从提取,返回 ({}, False)(不算降级)。"""
    if not text.strip():
        return {}, False
    try:
        c = make_kimi_client(timeout=120)   # T4(2026-09-02): client 构造合一至 shared
        r = c.chat.completions.create(
            model=MODELS["kimi"]["api_code"],
            messages=[{"role":"system","content":_SYS},
                      {"role":"user","content":text[:6000]}],
            response_format={"type":"json_object"}, temperature=1)  # kimi 仅允许 temperature=1（=0 报 400）
        parsed = json.loads(r.choices[0].message.content or "{}")
        return (parsed if isinstance(parsed, dict) else {}), False
    except Exception as e:
        log.warning("meta_llm Kimi 失败,semantic 降级(structural 兜底): %s: %s",
                    type(e).__name__, e)
        return {}, True
