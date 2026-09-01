# src/geo/generate/kimi.py
from __future__ import annotations
import re
import json
import logging
import yaml
from geo.shared.config import settings

log = logging.getLogger("generate.kimi")

_WEEK_RE = re.compile(r"Playbook · w(\d+)")
_FMT_HDR_RE = re.compile(r"^### (\w+)（.+?）", re.M)
_FMT_LINE_RE = re.compile(r"- cited_n=(\d+) sample_n=(\d+) confidence=(\w+)")

PAGE_TYPES = ("faq", "spec", "comparison", "guide")
_SKELETONS = {
    "faq":        "## {topic}\n\n（FAQ 块：每小节一问一答）\n\n## Q1 …",
    "spec":       "## {topic}\n\n（规格卡：表格列产品事实，数据只取 BRAND FACTS）",
    "comparison": "## {topic}\n\n（对比表：列 = 维度，行 = 选项；数据只取 BRAND FACTS）",
    "guide":      "## {topic}\n\n（指南：定义段开头 + 步骤清单 + 数据点）",
}

class GenerateError(Exception):
    pass

def playbook_digest(playbook_text: str) -> dict:
    text = playbook_text or ""
    m = _WEEK_RE.search(text)
    formats: list[dict] = []
    lines = text.splitlines()
    current_key = None
    for line in lines:
        h = _FMT_HDR_RE.match(line)
        if h:
            current_key = h.group(1)
            continue
        if current_key:
            fm = _FMT_LINE_RE.search(line)
            if fm:
                formats.append({"key": current_key, "cited_n": int(fm.group(1)),
                                "sample_n": int(fm.group(2)), "confidence": fm.group(3)})
                current_key = None
    return {"week": int(m.group(1)) if m else None, "formats": formats,
            "templates_note": "高被引骨架：对比表 / 定义段 / 规格卡（见 playbook §5）"}

def _kimi_chat(messages: list[dict], tools=None, timeout: int = 300) -> str:
    # 300s:草稿生成为长补全,Kimi 实测响应 50–215s(见模型记录);180s 在 w3 实跑
    # (2026-09-01)连续两次掐死正常生成。研究层短调用不受影响(各自独立超时)。
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    r = c.chat.completions.create(model="kimi-k3", messages=messages, temperature=1,
                                  response_format={"type": "json_object"})
    return r.choices[0].message.content or ""

_SYS_GEN = (
    "你是 SunHestia 官网内容写手。只能使用 BRAND FACTS 中的数字与规格，不得编造任何数字、"
    "型号或承诺；写不出的事实就略过。输出 JSON："
    "{frontmatter:{topic,page_type,slug},title,body_md,json_ld:[schema.org 对象],"
    "fact_anchors:[{claim,path,value}]}。"
    "纪律：body_md 里每个数字都必须有一条 fact_anchors，path 语法只有三种："
    "products[<id>].specs.<键>、faqs[<id>].a、glossary[<id>].definition，"
    "<id> 必须原样使用 BRAND FACTS 里各条目的 id 字段值（不得自造下标或缩写）；"
    "json_ld 至少一个对象且与页面类型匹配"
    "（guide→Article、faq→FAQPage、spec→Product、comparison→Article）；body_md 用英文写、"
    "markdown 结构（H1/H2/表格/FAQ 块按 PLAYBOOK DIGEST 的高被引格式优先）。"
)

def generate_draft(topic: str, page_type: str, brand: dict, digest: dict, *, chat_fn=None) -> dict:
    chat = chat_fn or _kimi_chat
    facts = yaml.safe_dump({k: brand.get(k) for k in ("entity", "products", "faqs", "glossary")},
                           allow_unicode=True, sort_keys=False)
    user = (f"TOPIC: {topic}\nPAGE_TYPE: {page_type}\n\nBRAND FACTS:\n{facts}\n\n"
            f"PLAYBOOK DIGEST:\n{json.dumps(digest, ensure_ascii=False)}")
    last: Exception | None = None
    for attempt in (1, 2):
        try:
            data = json.loads(chat([{"role": "system", "content": _SYS_GEN},
                                    {"role": "user", "content": user}]))
            for k in ("frontmatter", "title", "body_md", "json_ld", "fact_anchors"):
                if k not in data:
                    raise ValueError(f"输出缺键 {k}")
            return data
        except Exception as e:
            last = e
            log.warning("generate_draft 第 %d 次失败: %s", attempt, e)
    raise GenerateError(f"Kimi 生成两次失败: {last}")

def skeleton_draft(topic: str, page_type: str, brand: dict) -> dict:
    body = _SKELETONS.get(page_type, _SKELETONS["guide"]).format(topic=topic)
    # Generate readable specs that claim extractor can parse (e.g., "5–15 kWh", "10-year warranty")
    specs_lines = []
    for p in brand.get("products", []):
        name = p.get("name", "")
        for k, v in p.get("specs", {}).items():
            # Convert underscore keys to readable format with units
            if "capacity" in k and "kwh" in k:
                specs_lines.append(f"{name} capacity is {v} kWh")
            elif "warranty" in k and "year" in k:
                specs_lines.append(f"{name} includes a {v}-year warranty")
            elif "power" in k and "w" in k:
                specs_lines.append(f"{name} power output is {v} W")
            else:
                specs_lines.append(f"{name} {k}: {v}")
    body_md = f"{body}\n\n" + "\n".join(specs_lines) if specs_lines else body
    return {"frontmatter": {"topic": topic, "page_type": page_type, "slug": ""},
            "title": topic, "body_md": body_md, "json_ld": [], "fact_anchors": []}
