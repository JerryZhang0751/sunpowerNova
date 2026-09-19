"""
HTML Reporter for GEO/SEO evaluation reports
Generates byte-level deterministic HTML reports from eval_report.json
"""

from __future__ import annotations
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Import REPO from shared config
try:
    from geo.shared.config import REPO
except ImportError:
    # Fallback for testing
    REPO = Path(__file__).resolve().parents[3]

TMPL = REPO/"src"/"geo"/"report"/"templates"
VENDOR = REPO/"src"/"geo"/"report"/"vendor"/"echarts.min.js"

def render(report: dict, out: Path) -> Path:
    """
    Render an HTML report from eval_report data.

    Args:
        report: Dictionary containing evaluation report data
        out: Path where the HTML file should be written

    Returns:
        Path to the rendered HTML file

    Note:
        This function is byte-level deterministic: the same input + rule_version
        will produce byte-identical HTML output (validated by golden tests).
    """
    env = Environment(
        loader=FileSystemLoader(str(TMPL)),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Configure JSON serialization for determinism
    env.policies["json.dumps_kwargs"] = {
        "ensure_ascii": False,
        "sort_keys": True
    }

    # Render a score signal readably inside the data-appendix table.
    def _fmt_signal(v):
        if v is None: return "—"
        if isinstance(v, bool): return "✓" if v else "✗"          # bool 必须先于 int 判断
        if isinstance(v, (int, float, str)): return str(v)
        return json.dumps(v, ensure_ascii=False, sort_keys=True)  # list/dict → 紧凑 JSON
    env.filters["fmt_signal"] = _fmt_signal

    # Load template and render with vendored echarts
    template = env.get_template("report.html.j2")
    echarts_js = VENDOR.read_text(encoding="utf-8")

    html = template.render(
        report=report,
        echarts_js=echarts_js
    )

    out.write_text(html, encoding="utf-8")
    return out

def main(argv: list[str] | None = None) -> None:
    """报告重渲染入口: 必须显式 --week(重渲染不属于流水线完成语义)。"""
    import argparse
    import json
    from geo.shared.config import settings
    from geo.shared.weeks import validate_production_week

    ap = argparse.ArgumentParser(prog="geo.report.reporter")
    ap.add_argument("--week", type=int, required=True,
                    help="生产周次(重渲染须显式指定)")
    a = ap.parse_args(argv)
    week = validate_production_week(a.week)

    rep = json.loads(
        (REPO / "data" / "analysis" / f"w{week}" / "eval_report.json").read_text(encoding="utf-8")
    )
    ri_path = REPO / "data" / "analysis" / f"w{week}" / "rules_iteration.json"
    if ri_path.exists():
        rep["rules_iteration"] = json.loads(ri_path.read_text(encoding="utf-8"))

    out = REPO / "reports" / f"w{week}" / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render(rep, out)
    print(out)


if __name__ == "__main__":
    main()