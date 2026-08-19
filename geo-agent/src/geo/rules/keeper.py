# src/geo/rules/keeper.py
"""RulesKeeper 单轮迭代:证据 → 门槛 → 权重 → 归档/升版/changelog/run.yaml。
纯确定性、零 LLM;升版自动(v1.1),人可在 changelog/files 事后回滚。"""
from __future__ import annotations
import json, shutil
from datetime import date
from pathlib import Path
import yaml
from geo.shared.config import REPO
from geo.assess.registry import GEO_SIGNALS, SEO_SIGNALS
from geo.rules.evidence import collect_evidence, dimension_strengths
from geo.rules.gate import evaluate
from geo.rules.weights import persisted_deltas, apply_deltas

# signal → 目标维度(候选必须已在注册表)
SIGNAL_TARGET = {"has_breadcrumblist": "schema", "faq_block_count": "citability"}


def _bump(v: str) -> str:
    return f"geo-seo-v{int(v.rsplit('v', 1)[1]) + 1}"


def _next_version(repo: Path, current: str) -> str:
    """Compute next version monotonic: max(current, all history dir versions)+1.
    Raises clear error if current < max known (inconsistent state)."""
    hist = repo / "rules" / "history"
    known = [current]
    if hist.exists():
        known += [d.name for d in hist.iterdir() if d.is_dir()]
    nums = [int(v.rsplit('v', 1)[1]) for v in known if v.startswith('geo-seo-v')]
    max_known = max(nums) if nums else 0
    current_num = int(current.rsplit('v', 1)[1])
    if current_num < max_known:
        raise ValueError(
            f"Version inconsistent: run.yaml rule_version={current} < max known in history={max_known}. "
            f"Restore state or manually fix run.yaml before iterating."
        )
    return f"geo-seo-v{max_known + 1}"


def _git_head(repo: Path) -> str:
    """归档绑定代码(v1.1):recalc 精确性 = 版本↔commit + 黄金锁。非 git 环境(测试 tmp)→ unknown。"""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _converge_membership(signals: dict, decisions) -> dict:
    """按条目终态收敛 membership(幂等):
    add+active → 在;add rejected/retired → 不在;remove+active → 不在;remove 其他 → 不动。"""
    sig = {k: list(v) for k, v in signals.items()}
    for d in decisions:
        t = d.target
        if t not in sig:
            continue
        if d.kind == "signal_add":
            if d.status == "active":
                if d.signal not in sig[t]:
                    sig[t].append(d.signal)
            else:                                   # draft/rejected/retired 一律不在成员里
                sig[t] = [s for s in sig[t] if s != d.signal]
        elif d.kind == "signal_remove" and d.status == "active":
            sig[t] = [s for s in sig[t] if s != d.signal]
    return sig


def _entries_yaml(decisions, week, new_version, prev_map: dict) -> list[dict]:
    out = []
    for d in decisions:
        prev = prev_map.get(d.signal) or {}
        # since_version:状态首次离开 draft 时记录;状态不变则沿用旧值
        if prev.get("status") == d.status and prev.get("since_version"):
            since = prev["since_version"]
        elif d.status == "draft":
            since = None
        else:
            since = new_version
        out.append({
            "id": f"{'add' if d.kind == 'signal_add' else 'remove'}-{d.signal}",
            "type": d.kind, "target": d.target, "signal": d.signal, "status": d.status,
            "statement": (f"{d.evidence.get('bucket', '')} 被检索源唯一页 share "
                          f"{d.evidence.get('share', 0.0):.1%} "
                          f"(unique_n={d.evidence.get('unique_n', 0)}, "
                          f"platforms={len(d.evidence.get('platforms', []))})"),
            "evidence": d.evidence,
            "since_version": since,
            "decided_at_week": week,
        })
    return out


def render_changelog(week: int, from_v: str, to_v: str | None, decisions,
                     w_before: dict, w_after: dict, observations: list[str]) -> str:
    L = [f"\n## {to_v or from_v} — {date.today().isoformat()} (week {week})"]
    if to_v is None:
        L.append("- 无变更(证据/权重均未达调整条件);version 不变。")
    else:
        L.append(f"- version: {from_v} → {to_v}(本周评分用 {from_v},变更自下周生效)")
        for d in decisions:
            if d.change in ("promoted", "rejected", "retired", "draft"):
                L.append(f"- entry {d.signal} [{d.kind}→{d.target}]: {d.change} "
                         f"(share={d.evidence.get('share', 0.0):.1%}, "
                         f"unique_n={d.evidence.get('unique_n', 0)}, "
                         f"platforms={len(d.evidence.get('platforms', []))})")
        if w_after != w_before:
            L.append("- weights: " + ", ".join(
                f"{k} {w_before[k]}→{w_after[k]}" for k in w_before if w_before[k] != w_after.get(k)))
        L.append(f"- rollback: python3.11 -m geo.rules.run rollback --to {from_v}")
    for o in observations:
        L.append(f"- 观察: {o}")
    return "\n".join(L) + "\n"


def iterate(week: int, *, repo: Path = REPO) -> dict:
    repo = Path(repo)
    ana = repo / "data" / "analysis" / f"w{week}"
    agg = json.loads((ana / "research_aggregates.json").read_text(encoding="utf-8"))
    evalrep = json.loads((ana / "eval_report.json").read_text(encoding="utf-8"))

    geo_raw = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text(encoding="utf-8"))
    seo_raw = yaml.safe_load((repo / "rules" / "seo-rules.yaml").read_text(encoding="utf-8"))
    for e in (*SIGNAL_TARGET,):
        assert e in GEO_SIGNALS or e in SEO_SIGNALS, f"候选 {e} 不在注册表"

    candidates = collect_evidence(agg)
    decisions = evaluate(candidates, geo_raw.get("entries", []), week, SIGNAL_TARGET)

    strengths = dimension_strengths(agg, evalrep)
    prev_ri = repo / "data" / "analysis" / f"w{week - 1}" / "rules_iteration.json"
    prev_strengths = (json.loads(prev_ri.read_text(encoding="utf-8")).get("dimension_strengths")
                      if prev_ri.exists() else None)
    deltas = persisted_deltas(strengths, prev_strengths, geo_raw["weights"])   # v1.1:2 周同向
    w_before = dict(geo_raw["weights"])
    w_after = apply_deltas(w_before, deltas) if deltas else w_before

    changed = any(d.change in ("promoted", "rejected", "retired", "draft") for d in decisions) \
        or bool(deltas)
    from_v = geo_raw["version"]
    to_v = _next_version(repo, from_v) if changed else None

    observations = ["SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠",
                    "证据口径 = 被检索源唯一 URL(页-周);观察性相关、无未检索对照组",
                    "权重调整施加 2 周同向持续性门(v1.1)"]
    if not deltas and any(v is not None for v in strengths.values()):
        observations.append("GEO 权重证据已记录(dimension_strengths),待与上期同向后调整(首周或方向反转)")

    if changed:
        hist_dir = repo / "rules" / "history" / from_v
        hist_dir.mkdir(parents=True, exist_ok=True)
        for f in ("geo-rules.yaml", "seo-rules.yaml"):
            shutil.copy2(repo / "rules" / f, hist_dir / f)
        manifest = {"code_commit": _git_head(repo), "week": week,
                    "archived_at": date.today().isoformat()}          # v1.1:版本↔代码绑定
        (hist_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    new_signals = _converge_membership(geo_raw.get("signals", {}), decisions)
    if to_v:
        geo_raw.update({"version": to_v, "weights": w_after, "signals": new_signals,
                        "entries": _entries_yaml(decisions, week, to_v,
                                                  {e["signal"]: e for e in geo_raw.get("entries", [])})})
        seo_raw.update({"version": to_v})
        (repo / "rules" / "geo-rules.yaml").write_text(
            yaml.safe_dump(geo_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        (repo / "rules" / "seo-rules.yaml").write_text(
            yaml.safe_dump(seo_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        run_raw = yaml.safe_load((repo / "run.yaml").read_text(encoding="utf-8"))
        run_raw["rule_version"] = to_v
        (repo / "run.yaml").write_text(
            yaml.safe_dump(run_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with (repo / "rules" / "changelog.md").open("a", encoding="utf-8") as f:
        f.write(render_changelog(week, from_v, to_v, decisions, w_before, w_after, observations))

    iteration = {
        "week": week, "from_version": from_v, "to_version": to_v,
        "entries": [{"signal": d.signal, "type": d.kind, "target": d.target,
                     "status": d.status, "change": d.change,
                     "evidence": {"bucket": d.evidence.get("bucket"),
                                  "share": d.evidence.get("share"),
                                  "with_n": d.evidence.get("with_n"),
                                  "unique_n": d.evidence.get("unique_n"),
                                  "platforms": d.evidence.get("platforms"),
                                  "weeks": d.evidence.get("weeks", [])}}
                    for d in decisions],
        "weights_before": w_before, "weights_after": w_after if changed else w_before,
        "dimension_strengths": {k: (round(v, 4) if v is not None else None)
                                for k, v in strengths.items()},          # v1.1:供次周持续性对照
        "observations": observations,
    }
    ana.mkdir(parents=True, exist_ok=True)
    (ana / "rules_iteration.json").write_text(
        json.dumps(iteration, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return iteration
