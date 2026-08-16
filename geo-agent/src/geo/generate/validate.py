# src/geo/generate/validate.py
from __future__ import annotations
import re
from dataclasses import dataclass, field
from geo.generate.brand import parse_claims, brand_claims, claims_match

_MISSING = object()
JSONLD_REQUIRED = {"FAQPage": ["mainEntity"], "Article": ["headline"],
                   "HowTo": ["name", "step"], "Product": ["name", "brand"]}
FRONTMATTER_REQUIRED = ("topic", "page_type", "slug", "created", "brand_version")
PAGE_TYPES = ("faq", "spec", "comparison", "guide")
BANNED_PATTERNS = {
    "no_pricing": re.compile(r"[$€£¥]\s*\d|\b\d+\s*(yuan|eur|usd|dollars?|euros?)\b|price[:\s$€£¥]*\d", re.I),
    "no_savings_percentages": re.compile(
        r"(save|saving|savings|off|cheaper|节省)[^.\n]{0,25}\d+\s*%|\d+\s*%\s*(off|savings?|cheaper|节省)", re.I),
}

@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    appendix_md: str = ""

def resolve_path(brand: dict, path: str):
    cur = brand
    for seg in path.split("."):
        m = re.match(r"^(\w+)\[(.+)\]$", seg)
        if m:
            key, ident = m.group(1), m.group(2)
            cur = cur.get(key) if isinstance(cur, dict) else None
            if not isinstance(cur, list):
                return _MISSING
            cur = next((it for it in cur if isinstance(it, dict) and it.get("id") == ident), None)
            if cur is None:
                return _MISSING
        elif isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return _MISSING
    return cur

def validate_draft(draft: dict, brand: dict) -> ValidationResult:
    issues: list[str] = []
    rows: list[tuple[str, str, bool]] = []      # (claim 文本, anchor 展示, ok)
    fm = draft.get("frontmatter", {})
    missing_fm = [k for k in FRONTMATTER_REQUIRED if not fm.get(k)]
    if missing_fm:
        issues.append(f"frontmatter 缺字段: {missing_fm}")
    if fm.get("page_type") not in PAGE_TYPES:
        issues.append(f"frontmatter.page_type 非法: {fm.get('page_type')!r}")

    inventory = brand_claims(brand)
    body = draft.get("body_md", "")
    body_claims = parse_claims(body)
    anchors = draft.get("fact_anchors", []) or []

    # Map number sets to original unit text from body for display
    original_units = {}
    for m in re.finditer(r"(\d+(?:[-–—]+\d+)?)\s*([a-zA-Z%]+)", body):
        nums_in_match = frozenset(re.findall(r"\d+", m.group(1)))
        original_units[nums_in_match] = m.group(2)

    for claim in body_claims:
        nums, unit = claim
        # CRITICAL: Sort by float value to avoid lexical sort bug (e.g., "15" < "5" lexicographically)
        nums_sorted = sorted(nums, key=float)
        # Use original unit from body text if available, otherwise normalized unit
        display_unit = original_units.get(nums, unit)
        claim_txt = f"{'–'.join(nums_sorted)} {display_unit}"

        # Check attribution FIRST - a claim must be in brand inventory before checking anchors
        if not claims_match(claim, inventory):
            issues.append(f"数字 claim 未归属 brand.yaml: {claim_txt}")
            rows.append((claim_txt, "—(编造)", False))
            continue

        # Find exact-match anchor: both claim AND value must exactly match nums (not subset)
        anchor = next((a for a in anchors
                       if set(parse_nums_from(a.get("claim", ""))) == nums or
                          set(parse_nums_from(str(a.get("value", "")))) == nums), None)

        if anchor is None:
            issues.append(f"数字 claim 缺 anchor: {claim_txt}")
            rows.append((claim_txt, "—(缺)", False))
            continue

        # Anchor exists - now verify path resolves and value matches
        resolved = resolve_path(brand, anchor.get("path", ""))
        if resolved is _MISSING:
            issues.append(f"anchor 路径不可解析: {anchor.get('path')!r}（claim {claim_txt}）")
            rows.append((claim_txt, anchor.get("path", ""), False))
            continue

        # Verify resolved value covers the claim numbers
        resolved_nums = set(parse_nums_from(str(resolved)))
        if resolved_nums >= nums:
            rows.append((claim_txt, anchor.get("path", ""), True))
        else:
            issues.append(f"anchor 值不吻合: claim {claim_txt} vs brand 值 {resolved!r}（path {anchor.get('path')}）")
            rows.append((claim_txt, anchor.get("path", ""), False))

    for i, obj in enumerate(draft.get("json_ld", []) or []):
        t = obj.get("@type", "") if isinstance(obj, dict) else ""
        if t not in JSONLD_REQUIRED:
            issues.append(f"json_ld[{i}] @type 非法: {t!r}")
            continue
        for k in JSONLD_REQUIRED[t]:
            if not obj.get(k):
                issues.append(f"json_ld[{i}] {t} 缺必填键: {k}")

    body = draft.get("body_md", "")
    for name, pat in BANNED_PATTERNS.items():
        if name in (brand.get("banned") or []) and pat.search(body):
            issues.append(f"口径禁项命中: {name}")

    lines = ["| claim | anchor | 校验 |", "|---|---|---|"]
    for claim_txt, path, ok in rows:
        lines.append(f"| {claim_txt} | {path} | {'✅' if ok else '❌'} |")
    return ValidationResult(ok=not issues, issues=issues, appendix_md="\n".join(lines))

def parse_nums_from(s: str) -> list[str]:
    return re.findall(r"\d+", str(s))
