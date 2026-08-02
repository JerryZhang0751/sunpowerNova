#!/usr/bin/env python3
"""
Extract measurement fields from saved answer files and emit fill_row.py commands.

Deterministic extraction:
- mentioned: literal 'sunhestia' (any case) present -> Y else N
- cited: a sunhestia(.com|.pages.dev) URL present -> Y else N
- competitors: case-sensitive match against a curated solar+storage brand
  dictionary (best-effort — brands absent from the dictionary are missed)

Brand prompts (B*) are SKIPPED with a warning: they echo the brand name from the
question, so mention/citation need manual judgment (real info / unknown /
hallucinated). Any non-brand file that unexpectedly mentions SunHestia is also
flagged for manual review.

Usage:
  python3 parse_to_commands.py 1 ChatGPT          # print commands for review
  python3 parse_to_commands.py 1 ChatGPT | sh     # execute after review
"""
import glob
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANSWERS = ROOT / "answers"
DATE = "2026-07-19"

# Curated residential solar + storage brand dictionary (canonical spelling).
# Matched case-SENSITIVELY on word boundaries (brands are proper nouns) to avoid
# hitting common words; longest-first so "LG Energy Solution" beats "LG".
BRANDS = [
    # multi-word
    "Canadian Solar", "MidNite Solar", "LG Energy Solution", "LG Chem",
    "Jinko Solar", "Trina Solar", "JA Solar", "First Solar",
    "Meyer Burger", "Yangtze Solar", "Shine Solar", "SankoPower", "SolarWatt",
    # storage / battery
    "FranklinWH", "Sigenergy", "Pylontech", "Sonnen",
    "GivEnergy", "FoxESS", "Dyness", "Sunsynk", "Deye",
    "BYD", "Samsung SDI", "Generac", "SimpliPhi", "Fortress", "Electriq",
    "EcoFlow", "Bluetti", "Jackery", "Anker", "Varta", "Saft", "CATL", "CALB",
    "NorthStar", "Huawei",
    # inverters
    "SolarEdge", "Enphase", "Sungrow", "GoodWe", "Growatt", "Solis", "SolaX",
    "Fronius", "SMA", "Victron", "Schneider", "Sol-Ark", "Tesvolt",
    # panels / manufacturers
    "Tesla", "CertainTeed", "ReneSola", "Sirius PV", "CW Energy", "Aiko",
    "Astronergy", "LONGi", "Risen", "Phono", "Sunket", "REC", "Maxeon",
    "SunPower", "Silfab", "Q Cells", "Qcells", "Panasonic", "LG", "Hanwha", "Trina",
    "Jinko", "Anern", "WHC", "Tanfon",
]
_seen = {}
for b in BRANDS:
    if b.lower() not in _seen:
        _seen[b.lower()] = b
BRANDS_CANON = sorted(_seen.values(), key=len, reverse=True)
BRAND_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BRANDS_CANON) + r")\b")

SUN_RE = re.compile(r"sunhestia", re.IGNORECASE)
CITE_RE = re.compile(r"sunhestia\.(com|pages\.dev)", re.IGNORECASE)
SRC_RE = re.compile(r"\[\d+\]|Sources|来源|https?://", re.IGNORECASE)


def extract(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    mentioned = "Y" if SUN_RE.search(text) else "N"
    cited = "Y" if CITE_RE.search(text) else "N"
    found = []
    for m in BRAND_RE.finditer(text):
        canon = _seen[m.group(0).lower()]
        if canon not in found:
            found.append(canon)
    # drop a short form when a longer brand starts with it + space
    # (e.g. "Jinko" when "Jinko Solar" present; "LG" when "LG Chem" present)
    found = [b for b in found
             if not any(o != b and o.lower().startswith(b.lower() + " ") for o in found)]
    return mentioned, cited, found, bool(SRC_RE.search(text))


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: parse_to_commands.py <week> <model>", file=sys.stderr)
        return 2
    week, model = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(str(ANSWERS / f"w{int(week)}-{model}-*.md")))
    if not files:
        print(f"# no files for w{week}-{model}", file=sys.stderr)
        return 1
    for f in files:
        pid = os.path.basename(f)[:-3].split("-")[-1]
        mentioned, cited, comps, has_src = extract(f)
        link = f"answers/{os.path.basename(f)}"
        if pid.startswith("B"):
            print(f"# MANUAL (brand prompt): {pid}/{model} mentions={mentioned} "
                  f"cite={cited} -> read & judge; comps={comps}")
            continue
        if mentioned == "Y":
            print(f"# REVIEW (unexpected mention): {pid}/{model} -> manual")
            continue
        src_note = "联网(有来源)" if has_src else "联网已开、模型未引来源"
        notes = f"{src_note}；SunHestia 未出现"
        print(f'python3 fill_row.py {week} {pid} {model} '
              f'--mentioned N --cited N '
              f'--competitors "{";".join(comps)}" '
              f'--link {link} '
              f'--notes "{notes}" --date {DATE}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
