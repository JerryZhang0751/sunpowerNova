# tests/test_rules_keeper.py
import json, yaml
from pathlib import Path
import geo.rules.keeper as K
from geo.rules.keeper import iterate, SIGNAL_TARGET

def _mk_repo(tmp_path):
    repo = tmp_path / "repo"; (repo / "rules").mkdir(parents=True)
    (repo / "data" / "analysis" / "w1").mkdir(parents=True)
    fix = Path(__file__).parent / "fixtures" / "rules"
    for f in ("research_aggregates.json", "eval_report.json"):
        (repo / "data" / "analysis" / "w1" / f).write_text((fix / f).read_text(encoding="utf-8"))
    (repo / "rules" / "geo-rules.yaml").write_text((fix / "geo_rules_v1.yaml").read_text())
    (repo / "rules" / "seo-rules.yaml").write_text((fix / "seo_rules_v1.yaml").read_text())
    (repo / "rules" / "changelog.md").write_text("# Rules changelog\n")
    (repo / "run.yaml").write_text(yaml.safe_dump(
        {"week": 1, "mode": "audit", "scope": "core", "runs": 1,
         "rule_version": "geo-seo-v1", "providers": ["qwen"]}, sort_keys=False))
    return repo

def test_iterate_w1_promotes_breadcrumblist_weights_hold(tmp_path):
    repo = _mk_repo(tmp_path)
    it = iterate(1, repo=repo)
    assert it["from_version"] == "geo-seo-v1" and it["to_version"] == "geo-seo-v2"
    st = {e["signal"]: e["status"] for e in it["entries"]}
    assert st["has_breadcrumblist"] == "active"            # 唯一口径 7/34=20.6%、3 家 → 转正
    assert st["faq_block_count"] == "draft"                # 0/34 首周 → 草稿(移除需 2 周)
    assert it["weights_after"] == it["weights_before"]     # v1.1:首周持续性门槛 → 权重不动
    assert it["dimension_strengths"]["schema"] == round(7 / 34, 4)   # strengths 已记录供次周
    # 归档(含 manifest)+ 新文件 + run.yaml + changelog + rules_iteration.json
    assert (repo / "rules" / "history" / "geo-seo-v1" / "geo-rules.yaml").exists()
    assert (repo / "rules" / "history" / "geo-seo-v1" / "manifest.json").exists()
    new_geo = yaml.safe_load((repo / "rules" / "geo-rules.yaml").read_text())
    assert new_geo["version"] == "geo-seo-v2"
    assert "has_breadcrumblist" in new_geo["signals"]["schema"]      # membership 生效
    assert sum(new_geo["weights"].values()) == 100
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v2"
    cl = (repo / "rules" / "changelog.md").read_text()
    assert "geo-seo-v2" in cl and "has_breadcrumblist" in cl
    ri = json.loads((repo / "data" / "analysis" / "w1" / "rules_iteration.json").read_text())
    assert ri["to_version"] == "geo-seo-v2"
    # seo 文件只升版本号,结构不变
    new_seo = yaml.safe_load((repo / "rules" / "seo-rules.yaml").read_text())
    assert new_seo["version"] == "geo-seo-v2" and "entries" in new_seo

def test_iterate_no_change_no_bump(tmp_path):
    repo = _mk_repo(tmp_path)
    ana = repo / "data" / "analysis" / "w1"
    agg = json.loads((ana / "research_aggregates.json").read_text())
    for b in agg["formats"]:
        b["unique_cited_n"] = 17; b["unique_n"] = 34; b["unique_platforms"] = ["qwen", "zhipu"]
    agg["sources"]["schema_unique"] = {"BreadcrumbList": 17}
    (ana / "research_aggregates.json").write_text(json.dumps(agg, ensure_ascii=False))
    ev = json.loads((ana / "eval_report.json").read_text())
    ev["gap"]["metrics"]["mention_rate"] = 0.5             # 三个证据流全部 = 0.5
    ev["gap"]["metrics"]["citation_rate"] = 0.5            # → raw deltas 全 0
    (ana / "eval_report.json").write_text(json.dumps(ev, ensure_ascii=False))
    it1 = iterate(1, repo=repo)                            # 首轮:breadcrumblist 转正 → v2(权重不动)
    assert it1["to_version"] == "geo-seo-v2"
    it2 = iterate(1, repo=repo)                            # 同周重跑 → 幂等,无变更不升版
    assert it2["to_version"] is None
    assert yaml.safe_load((repo / "run.yaml").read_text())["rule_version"] == "geo-seo-v2"

def test_iterate_isolated_delta_moves_weights(tmp_path):
    repo = _mk_repo(tmp_path)
    ana1 = repo / "data" / "analysis" / "w1"
    ana2 = repo / "data" / "analysis" / "w2"
    ana2.mkdir(parents=True)
    agg = json.loads((ana1 / "research_aggregates.json").read_text(encoding="utf-8"))
    for b in agg["formats"]:
        b["unique_cited_n"] = 36; b["unique_n"] = 40                 # citability 0.9
    agg["sources"]["unique_n"] = 40
    agg["sources"]["schema_unique"] = {"BreadcrumbList": 19}         # schema 0.475
    (ana2 / "research_aggregates.json").write_text(json.dumps(agg, ensure_ascii=False))
    ev = json.loads((ana1 / "eval_report.json").read_text(encoding="utf-8"))
    ev["gap"]["metrics"]["mention_rate"] = 0.5                        # brand (0.5+0.5)/2=0.5
    ev["gap"]["metrics"]["citation_rate"] = 0.5
    (ana2 / "eval_report.json").write_text(json.dumps(ev, ensure_ascii=False))
    (ana1 / "rules_iteration.json").write_text(json.dumps(           # 上期同向记录
        {"dimension_strengths": {"citability": 0.8, "schema": 0.5, "brand": 0.48}}))
    it = iterate(2, repo=repo)
    assert it["weights_before"] != it["weights_after"]
    # strengths {citability 0.9, schema 0.475, brand 0.5} → delta 仅 citability +1;
    # diff=-1 补偿只动零-delta 维 → 测量最弱者 schema 0.475 让权(10→9);
    # 若丢 strengths 传参,名字 ASCII 兜底会落 brand(用例即失效)。
    assert it["weights_after"] == {**it["weights_before"], "citability": 26, "schema": 9}
    assert it["to_version"] is not None                              # 权重动了 → 升版
