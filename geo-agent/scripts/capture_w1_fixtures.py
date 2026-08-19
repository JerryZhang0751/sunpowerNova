"""Capture real w1 aggregates/eval_report into tests/fixtures/rules/ (committed)."""
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "rules"
OUT.mkdir(parents=True, exist_ok=True)

# Copy real w1 data to committed fixtures
for src in ("data/analysis/w1/research_aggregates.json", "data/analysis/w1/eval_report.json"):
    src_path = REPO / src
    if src_path.exists():
        shutil.copy(src_path, OUT / Path(src).name)
        print(f"copied {src} -> {OUT / Path(src).name}")
    else:
        print(f"WARNING: {src} does not exist, skipped")

print(f"\ncaptured w1 fixtures to {OUT}")
