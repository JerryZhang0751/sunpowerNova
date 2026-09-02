from __future__ import annotations
import json
import logging
import re
import yaml
from collections import Counter
from pathlib import Path
from geo.shared.config import MODELS, REPO, settings

REQUIRED_KEYS = ("entity", "products", "faqs", "glossary", "banned")

class BrandError(Exception):
    pass

def load_brand(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise BrandError(f"brand.yaml 不存在: {path}；先运行 --bootstrap-brand")
    brand = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(brand.get("version"), int) or brand["version"] < 1:
        raise BrandError(f"brand.yaml version 非法: {brand.get('version')!r}")
    missing = [k for k in REQUIRED_KEYS if k not in brand]
    if missing:
        raise BrandError(f"brand.yaml 缺少顶层键: {missing}")
    return brand

def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s or "untitled"

# --- 数字 claim 提取（brand 抽取校验与草稿核验共用脊柱）---
_UNITS = r"(kwh|kw|wh|watts|watt|w|years|year|percent|volts|volt|v|%|°c|°f)"
_UNIT_NORM = {"watts": "w", "watt": "w", "years": "year", "percent": "%", "volts": "v", "volt": "v"}
# 数字原子(2026-08-24 审查#4): 支持小数与千分位;千分位形必须在前,否则 \d+ 会
# 把 "1,500" 截成 "1"。(2026-08-25 二次审查#4)千分位形补小数尾巴("1,500.5"),
# 否则正则回退会截出子数 "500.5";另补欧式小数逗号形("5,5"),规范化时逗号→点,
# 不得截成 "5"。
_NUM_ATOM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+,\d+|\d+(?:\.\d+)?)"
# 符号位(2026-08-25 二次审查#4): "+10°C" 与 "-10°C" 是方向相反的两个事实;
# 原子/RANGE 端点各带 [+-]?,规范化保留负号、+ 归一(数值等同)。_norm 已把
# en/em dash 与 U+2212 归一为 "-",分隔符只写 "-"。
_NUM = rf"([+-]?{_NUM_ATOM}(?:\s*[-]\s*[+-]?{_NUM_ATOM})?)"
_RANGE_RE = re.compile(rf"([+-]?{_NUM_ATOM})\s*-\s*([+-]?{_NUM_ATOM})")
_NUM_TOKEN_RE = re.compile(rf"[+-]?{_NUM_ATOM}(?:\s*-\s*[+-]?{_NUM_ATOM})?")
# 文本体：数字在前，单位紧随（含 "10-year" 连字符形）
# 使用 (?![a-z0-9]) 替代 \b 以匹配 % 等非字母单位（% 后的字符都是非单词字符，\b 无法匹配）
_CLAIM_RE = re.compile(rf"{_NUM}\s*[-\s]*{_UNITS}(?![a-z0-9])", re.I)
# 键值体：键名含单位在前、值在后（"capacity kwh: 5–15"；下划线先归一为空格）
# 间隔用惰性量词并禁止吞掉贴着数字的符号位——否则 "temp °c: -10" 的 "-" 被
# 贪婪间隔吃掉,值变成无符号 10(2026-08-25 二次审查#4)。
_KEYVAL_RE = re.compile(rf"\b{_UNITS}(?![a-z0-9])[^0-9\n]{{0,25}}?{_NUM}", re.I)

def _norm(s: str) -> str:
    return re.sub(
        r"\s+", " ",
        s.replace("_", " ").replace("–", "-").replace("—", "-").replace("−", "-")
    ).strip().lower()

def _norm_unit(u: str) -> str:
    u = u.lower()
    return _UNIT_NORM.get(u, "%" if u == "percent" else u)

def _canon_num(tok: str) -> str:
    """数字 token 规范形式: 千分位去除/欧式小数逗号归一、保留负号、去尾零。

    "+10"→"10"(数值等同); "-10"→"-10"; "1,500"→"1500"; "1,500.5"→"1500.5";
    "5,5"→"5.5"(非合法千分位的逗号按小数逗号处理,不得截成 "5")。
    """
    t = tok.strip()
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
        t = t.replace(",", "")                     # 合法千分位
    else:
        t = t.replace(",", ".")                    # 欧式小数逗号("5,5"→"5.5")
    f = -float(t) if neg else float(t)
    return str(int(f)) if f.is_integer() else repr(f)

def _norm_nums(raw: str) -> frozenset[str]:
    """range 两端拆开(各带符号);单值带符号整体化。"""
    t = raw.strip()
    m = _RANGE_RE.fullmatch(t)
    if m:
        return frozenset({_canon_num(m.group(1)), _canon_num(m.group(2))})
    return frozenset({_canon_num(t)})

def tokenize_nums(text: str) -> list[str]:
    """提取文本中全部数字 token(规范化;range 两端拆开、符号保留)。validate
    的 anchor 值核对与其用同一 tokenizer,否则小数/千分位/符号两边口径不一仍可绕过。"""
    out: list[str] = []
    for m in _NUM_TOKEN_RE.finditer(_norm(text)):
        out.extend(sorted(_norm_nums(m.group(0)), key=float))   # 数值序,非字典序
    return out

def parse_claims(text: str) -> list[tuple[frozenset[str], str]]:
    t = _norm(text)
    out = []
    for nums_raw, unit in _CLAIM_RE.findall(t):
        out.append((_norm_nums(nums_raw), _norm_unit(unit)))
    return out

def _iter_fact_leaves(brand: dict):
    def scalars(d: dict, prefix=""):
        for k, v in d.items():
            if isinstance(v, (str, int, float)):
                yield f"{k}: {v}"
            elif isinstance(v, dict):
                yield from scalars(v, f"{prefix}{k}.")
    yield from scalars(brand.get("entity", {}))
    for p in brand.get("products", []):
        yield from scalars(p)
    for f in brand.get("faqs", []):
        yield from scalars(f)
    for g in brand.get("glossary", []):
        yield from scalars(g)

def brand_claims(brand: dict) -> list[tuple[frozenset[str], str]]:
    out = []
    for leaf in _iter_fact_leaves(brand):
        t = _norm(leaf)
        # _KEYVAL_RE matches unit first, then number - need to swap the order
        for unit, nums_raw in _KEYVAL_RE.findall(t):
            out.append((_norm_nums(nums_raw), _norm_unit(unit)))
        # _CLAIM_RE：数字在前、单位紧随（FAQ/modularity 等自由文本，2026-08-18 live 校准：
        # 仅 keyval 体抽库存会把 "5–10 kWh" 类 FAQ 事实漏成"编造"假阳性）
        for nums_raw, unit in _CLAIM_RE.findall(t):
            out.append((_norm_nums(nums_raw), _norm_unit(unit)))
    return out

def claims_match(claim: tuple[frozenset[str], str],
                 inventory: list[tuple[frozenset[str], str]]) -> bool:
    nums, unit = claim
    return any(unit == u2 and nums <= n2 for n2, u2 in inventory)

def _leaf_keyval_claims(leaf: str) -> list[tuple[frozenset[str], str]]:
    # 键名含单位、值为裸数字的叶子（parse_claims 文本体正则吃不到，用键值正则）
    t = _norm(leaf)
    # _KEYVAL_RE matches unit first, then number - need to swap the order
    return [(_norm_nums(nums_raw), _norm_unit(unit)) for unit, nums_raw in _KEYVAL_RE.findall(t)]

def validate_brand(brand: dict, sources_text: str) -> list[str]:
    src_claims = parse_claims(sources_text)
    violations = []
    for leaf in _iter_fact_leaves(brand):
        for claim in parse_claims(leaf) + _leaf_keyval_claims(leaf):
            if not claims_match(claim, src_claims):
                nums, unit = claim
                violations.append(f"数字 claim {sorted(nums)} {unit} 未在源页出现（来自: {leaf[:60]}）")
    for p in brand.get("products", []):
        if p.get("name") and p["name"].lower() not in sources_text.lower():
            violations.append(f"产品名未在源页字面出现: {p['name']}")
    for g in brand.get("glossary", []):
        if g.get("term") and g["term"].lower() not in sources_text.lower():
            violations.append(f"术语未在源页字面出现: {g['term']}")
    return violations

# --- bootstrap（一次性引导，低频重跑保险）---
log = logging.getLogger("generate.brand")

_SYS_BOOT = (
    "你是品牌事实抽取器。只准从所给的站点页面文本抽取事实，禁止推断或编造。"
    "输出 JSON：{entity:{brand,domain,positioning,legal_name?,locations?},"
    "products:[{id,name,specs:{...}}],faqs:[{q,a}],glossary:[{term,definition}]}。"
    "specs 的键名带单位（如 capacity_kwh/warranty_years/power_w）；抽不到的键省略，不要编。"
)

def _kimi_chat(messages: list[dict], tools=None, timeout: int = 120) -> str:
    from openai import OpenAI
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=timeout)
    r = c.chat.completions.create(model=MODELS["kimi"]["api_code"], messages=messages, temperature=1,
                                  response_format={"type": "json_object"})
    return r.choices[0].message.content or ""

def read_site_pages(site_root: Path) -> dict[str, str]:
    site_root = Path(site_root)
    return {str(p.relative_to(site_root)): p.read_text(encoding="utf-8")
            for p in sorted(site_root.rglob("*.astro"))}

def bootstrap_draft(pages: dict[str, str], *, chat_fn=None) -> dict:
    chat = chat_fn or _kimi_chat
    user = "\n\n".join(f"=== 页面 {name} ===\n{text}" for name, text in pages.items())
    try:
        data = json.loads(chat([{"role": "system", "content": _SYS_BOOT},
                                {"role": "user", "content": user}]))
    except Exception as e:
        raise BrandError(f"Kimi 抽取失败（非法 JSON）: {e}") from e
    for k in ("entity", "products", "faqs", "glossary"):
        if k not in data:
            raise BrandError(f"Kimi 抽取结果缺键: {k}")
    return data

def competitors_from_raw(raw_root: Path) -> list[str]:
    raw_root = Path(raw_root)
    counter: Counter[str] = Counter()
    for f in raw_root.rglob("r*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            counter.update((rec.get("l2") or {}).get("competitors_mentioned", []))
        except Exception as e:
            log.warning("skip unreadable raw %s: %s", f, e)
    return [name for name, _ in counter.most_common()]

DEFAULT_BANNED = ["no_pricing", "no_savings_percentages"]

def assemble_brand(draft: dict, competitors: list[str], *, updated: str = "1970-01-01") -> dict:
    return {"version": 1, "updated": updated,
            "entity": draft.get("entity", {}), "products": draft.get("products", []),
            "faqs": draft.get("faqs", []), "glossary": draft.get("glossary", []),
            "banned": list(DEFAULT_BANNED), "competitors": competitors, "i18n": {}}

def run_bootstrap(*, repo: Path = REPO, chat_fn=None, updated: str = None) -> dict:
    from datetime import date
    repo = Path(repo)
    site_root = repo / "site" / "src" / "pages"          # mini-repo 约定：repo 下有 site/
    if not site_root.exists():                            # 真仓库：site/ 是 geo-agent 的兄弟
        site_root = repo.parent / "site" / "src" / "pages"
    pages = read_site_pages(site_root)
    draft = bootstrap_draft(pages, chat_fn=chat_fn)
    competitors = competitors_from_raw(repo / "data" / "raw")
    brand = assemble_brand(draft, competitors, updated=updated or date.today().isoformat())
    sources_text = "\n\n".join(pages.values())
    violations = validate_brand(brand, sources_text)
    (repo / "knowledge").mkdir(parents=True, exist_ok=True)

    brand_yaml = repo / "knowledge" / "brand.yaml"
    brand_draft = repo / "knowledge" / "brand.yaml.draft"

    if violations:
        out = brand_draft
        out.write_text(yaml.safe_dump(brand, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log.warning("brand 校验 %d 项违规，写入 %s（人修/删后重跑）", len(violations), out)
        return {"wrote": str(out), "violations": violations,
                "hint": "人审定稿后 git commit knowledge/brand.yaml"}
    else:
        # 无违规，但若 brand.yaml 已存在（人审定稿），则写入 .draft 避免覆盖
        if brand_yaml.exists():
            out = brand_draft
            out.write_text(yaml.safe_dump(brand, allow_unicode=True, sort_keys=False), encoding="utf-8")
            log.info("knowledge/brand.yaml 已存在（人审定稿），新抽取结果写入 %s（人对比后决定是否替换）", out)
            return {"wrote": str(out), "violations": violations,
                    "hint": "brand.yaml 已存在（人审定稿）；新结果在 .draft 中，需人工 diff 后决定是否替换"}
        else:
            out = brand_yaml
            out.write_text(yaml.safe_dump(brand, allow_unicode=True, sort_keys=False), encoding="utf-8")
            log.info("brand.yaml 写入 %s（待人审定稿）", out)
            return {"wrote": str(out), "violations": violations,
                    "hint": "人审定稿后 git commit knowledge/brand.yaml"}
