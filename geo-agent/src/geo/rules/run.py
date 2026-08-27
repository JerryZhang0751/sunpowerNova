# src/geo/rules/run.py
"""RulesKeeper CLI:iterate / recalc / rollback / show。零 LLM。"""
from __future__ import annotations
import json, shutil
from pathlib import Path
import yaml
from geo.shared.config import REPO, settings
from geo.shared.weeks import validate_production_week
from geo.rules.keeper import iterate
from geo.assess.analyst import assemble


def do_recalc(repo: Path, week: int, rule_version: str, render: bool = False) -> dict:
    from geo.rules.loader import load_rules
    # Load rules via public loader (repo param only for render output path)
    rg = load_rules("geo", version=rule_version)
    rs = load_rules("seo", version=rule_version)
    rep = assemble(week, rules_geo=rg, rules_seo=rs,
                   out_name=f"eval_report.recalc-{rule_version}.json",
                   rule_version=rule_version)
    if render:
        from geo.report.reporter import render as _render
        out = repo / "reports" / f"w{week}" / f"report.recalc-{rule_version}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        _render(rep, out)
        print(out)
    return rep


def _known_versions(repo: Path) -> list[str]:
    vers = [yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))["version"]]
    hist = repo / "rules" / "history"
    if hist.exists():
        vers += [d.name for d in hist.iterdir() if d.is_dir()]
    return vers


def _next_version(repo: Path) -> str:
    ns = [int(v.rsplit("v", 1)[1]) for v in _known_versions(repo) if v.startswith("geo-seo-v")]
    return f"geo-seo-v{max(ns) + 1}"


def do_rollback(repo: Path, to_version: str) -> None:
    """v1.1:回滚 = 创建新单调版本(内容 = to_version 快照,restores 元数据),不倒退版本号。
    直接改回旧号会在下次迭代产出与 history/ 不可变归档同名不同容的版本 → recalc 语义歧义。"""
    src = repo / "rules" / "history" / to_version
    if not src.exists():
        raise SystemExit(f"历史版本不存在: {src}")
    cur_v = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))["version"]
    if cur_v == to_version:
        raise SystemExit(f"当前已是 {to_version},无需回滚")
    new_v = _next_version(repo)
    hist_cur = repo / "rules" / "history" / cur_v          # 现行版本先归档(若未归档)
    hist_cur.mkdir(parents=True, exist_ok=True)
    for f in ("geo-rules.yaml", "seo-rules.yaml"):
        shutil.copy2(repo / "rules" / f, hist_cur / f)
    for name in ("geo", "seo"):
        d = yaml.safe_load((src / f"{name}-rules.yaml").read_text(encoding="utf-8"))
        d["version"] = new_v
        d["restores"] = to_version
        (repo / "rules" / f"{name}-rules.yaml").write_text(
            yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
    run_raw["rule_version"] = new_v
    (repo / "run.yaml").write_text(
        yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with (repo / "rules" / "changelog.md").open("a", encoding="utf-8") as fh:
        fh.write(f"\n## rollback — {new_v} restores {to_version}(现行 {cur_v} 已归档;不倒退版本号)\n")
    print(f"rolled back: {new_v} restores {to_version}")


def do_show(repo: Path) -> None:
    for name in ("geo", "seo"):
        d = yaml.safe_load((repo / "rules" / f"{name}-rules.yaml").read_text(encoding="utf-8"))
        print(f"[{name}] version={d['version']} weights={d['weights']} entries={len(d.get('entries', []))}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="geo.rules.run", description="P3 RulesKeeper CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("iterate"); p1.add_argument("--week", type=int, required=True)
    p2 = sub.add_parser("recalc"); p2.add_argument("--week", type=int, required=True)
    p2.add_argument("--rule-version", required=True); p2.add_argument("--render", action="store_true")
    p3 = sub.add_parser("rollback"); p3.add_argument("--to", required=True)
    sub.add_parser("show")
    a = ap.parse_args()
    if a.cmd in ("iterate", "recalc"):
        validate_production_week(a.week)
    if a.cmd == "iterate":
        print(json.dumps(iterate(a.week), ensure_ascii=False, indent=2))
    elif a.cmd == "recalc":
        do_recalc(REPO, a.week, a.rule_version, a.render)
    elif a.cmd == "rollback":
        do_rollback(REPO, a.to)
    else:
        do_show(REPO)


if __name__ == "__main__":
    main()
