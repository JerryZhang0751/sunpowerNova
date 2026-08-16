from __future__ import annotations
import re
import yaml
from pathlib import Path

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
_NUM = r"(\d+(?:\s*[-–—]\s*\d+)?)"
# 文本体：数字在前，单位紧随（含 "10-year" 连字符形）
_CLAIM_RE = re.compile(rf"{_NUM}\s*[-\s]*{_UNITS}\b", re.I)
# 键值体：键名含单位在前、值在后（"capacity kwh: 5–15"；下划线先归一为空格）
_KEYVAL_RE = re.compile(rf"\b{_UNITS}\b[^0-9\n]{{0,25}}{_NUM}", re.I)

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("_", " ").replace("–", "-").replace("—", "-")).strip().lower()

def _norm_unit(u: str) -> str:
    u = u.lower()
    return _UNIT_NORM.get(u, "%" if u == "percent" else u)

def _norm_nums(raw: str) -> frozenset[str]:
    return frozenset(p.strip() for p in re.split(r"[-]+", raw) if p.strip())

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
