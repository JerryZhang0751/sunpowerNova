# src/geo/research/render.py
from __future__ import annotations
import json
from geo.research.models import FeatureAggregates, PlaybookConclusion

_FMT_LABEL = {"comparison_table":"对比表","qa":"Q&A","list":"清单","definition":"定义段","spec_card":"规格卡"}

def _rule_version(feed: dict | None) -> str:
    rv = (feed or {}).get("rule_version")
    if rv:
        return rv
    from geo.shared.config import settings
    return settings.run.rule_version

def _feedback_section(feed: dict | None) -> list[str]:
    if not feed:
        return ["\n## 6. 上期动作→指标对照", "- 无对照(数据缺失)。"]
    L = ["\n## 6. 上期动作→指标对照"]
    pub = feed.get("published") or []
    if pub:
        L.append("- 上期发布: " + "; ".join(f"{p['slug']}({p['created']})" for p in pub))
    else:
        L.append("- 上期发布: 无")
    lat, prev = feed.get("latest"), feed.get("prev")
    def row(k, label):
        if lat is None:
            return f"- {label}: 无数据"
        v = lat[k]
        if prev:
            return f"- {label}: {v} → 前期 {prev[k]}(Δ{round(v - prev[k], 1):+})"
        return f"- {label}: {v}(首期基线,无环比)"
    L += [row("mention_rate", "mention_rate"), row("citation_rate", "citation_rate"),
          row("sov", "sov"), row("self_geo", "self_geo"), row("self_seo", "self_seo")]
    L.append(f"- 规则版本: {feed.get('rule_version', '—')}")
    L.append("- ⚠️ 收录有延迟、单周样本小;对照为观察性相关,非因果归因。")
    return L

def render_playbook(conclusions: list[PlaybookConclusion], aggregates: FeatureAggregates, week: int, feed: dict | None = None) -> str:
    c = aggregates.coverage
    L = [f"# SunHestia GEO Playbook · w{week}",
         f"> rule_version {_rule_version(feed)} | L1={c.total_l1} | 被引源分析 sample_n={c.l3_resolved}(缺失{c.l3_missing}/js_only{c.l3_js_only})",
         "> ⚠️ 观察性相关非因果，低置信项已标注。结论由确定性聚合 + Kimi 综合生成。\n",
         "## 1. 被引格式特征"]
    fmt_concl = [x for x in conclusions if x.category=="format"]
    for b in aggregates.formats:
        label = _FMT_LABEL.get(b.key, b.key)
        L.append(f"### {b.key}（{label}）")
        L.append(f"- cited_n={b.cited_n} sample_n={b.sample_n} confidence={'low' if b.low_confidence else 'ok'} platforms={b.platforms}")
        match = next((x for x in fmt_concl if x.bucket_key == b.key), None)
        if match: L.append(f"- 结论：{match.conclusion}｜行动：{match.action}")
    L += ["\n## 2. 被引来源特征",
          f"```json\n{json.dumps(aggregates.sources, ensure_ascii=False, indent=2)}\n```",
          "\n## 3. 分平台差异",
          f"```json\n{json.dumps(aggregates.platforms, ensure_ascii=False, indent=2)}\n```",
          "\n## 4. 问题空间与选题",
          f"意图簇：{aggregates.problem_space.get('intent_clusters')}  选题缺口候选：{aggregates.problem_space.get('topic_gaps')}",
          "\n## 5. 可复用内容模板",
          "- 据 §1 高被引格式，建议骨架：对比表 / 定义段 / 规格卡（由生成 agent P2 落地）。"]
    L += _feedback_section(feed)
    return "\n".join(L) + "\n"

def render_profiles(platforms_metrics: dict, verified_facts: dict, week: int) -> str:
    L = [f"# 平台引用画像 · w{week}", ""]
    names = {"qwen":"Qwen · qwen3.7-plus (阿里 DashScope)",
             "doubao":"Doubao · doubao-seed-2-1-pro (字节 Ark)",
             "zhipu":"Zhipu · glm-5.2 (BigModel)"}
    for m, met in platforms_metrics.items():
        L.append(f"## {names.get(m,m)}")
        L.append(f"- 引用偏好(数据,n={met.get('n')}): mention={met.get('mention_rate')} citation={met.get('citation_rate')}")
        vf = verified_facts.get(m.capitalize()) or verified_facts.get(m, {})
        if vf:
            L.append(f"- 爬虫名/收录(联网查证): {vf.get('answer','—')}")
            L.append(f"  来源：{', '.join(vf.get('sources',[])) or '—'} | 置信度：{vf.get('confidence','—')}")
        L.append("")
    L.append("## 附录：主流 AI 平台爬虫名对照表（Tier2 联网查证）")
    for plat, vf in verified_facts.items():
        if plat.lower() in ("chatgpt","gemini","perplexity","claude"):
            L.append(f"- {plat}: {vf.get('answer','—')} [{vf.get('confidence','—')}]")
    return "\n".join(L) + "\n"
