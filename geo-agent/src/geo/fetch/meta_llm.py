from __future__ import annotations
import json
from openai import OpenAI
from geo.shared.config import MODELS, settings

_SYS = ("Extract semantic metadata from the page text as JSON ONLY. Keys: "
        "page_type (product|faq|blog|comparison|spec|forum|qa|news|other), "
        "has_definition_segment (bool), has_faq_block (bool), datapoint_count (int), "
        "has_author_byline (bool), has_publish_date (bool), cites_external_sources (bool).")

def extract_semantic(text: str) -> dict:
    if not text.strip(): return {}
    try:
        c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=120)
        r = c.chat.completions.create(
            model=MODELS["kimi"]["api_code"],
            messages=[{"role":"system","content":_SYS},
                      {"role":"user","content":text[:6000]}],
            response_format={"type":"json_object"}, temperature=1)  # kimi 仅允许 temperature=1（=0 报 400）
        return json.loads(r.choices[0].message.content or "{}")
    except Exception:
        return {}     # Kimi 失败不阻断：语义缺则后续确定性代理用 structural 兜底
