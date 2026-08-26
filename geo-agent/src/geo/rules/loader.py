from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import yaml
from geo.shared.config import REPO

RULES_DIR = REPO / "rules"


def _load(p: Path):
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    return SimpleNamespace(
        version=d["version"],
        composite=d["composite"],
        weights=d["weights"],
        signals=d.get("signals", {}),
        severity_bands=d.get("severity_bands", {}),
        p2plus_missing=d.get("p2plus_missing", []),
        entries=d.get("entries", [])
    )


def load_rules(name: str, version: str | None = None):
    """Load rules by name (geo or seo); version=None reads current, else reads
    rules/history/{version}/。

    请求恰好等于现行文件 version 的版本 → 解析到现行文件(用现行版本做 recalc
    不得依赖下一次升版后才存在的归档;2026-08-25 二次审查#6);其余历史版本
    读归档,缺归档抛 FileNotFoundError。
    """
    p_cur = RULES_DIR / f"{name}-rules.yaml"
    if version:
        p_hist = RULES_DIR / "history" / version / f"{name}-rules.yaml"
        if p_hist.exists():
            p = p_hist
        elif p_cur.exists() and _load(p_cur).version == version:
            p = p_cur
        else:
            raise FileNotFoundError(f"rules not found: {p_hist}")
    else:
        p = p_cur
    return _load(p)


def assert_normalized(rules) -> None:
    """Validate that pillar weights sum to 100%."""
    s = sum(rules.weights.values())
    if abs(s - 100) > 0.001:
        raise ValueError(f"{rules.composite} weights sum={s} != 100 (拒绝本次迭代)")
