"""
Tests for geo.report.reporter module
Byte-level determinism tests (golden tests)
"""

import json
from pathlib import Path
from geo.report.reporter import render

REPORT = {
    "week": 1,
    "rule_version": "geo-seo-v1",
    "prompt_set_version": "abc",
    "metrics": {
        "qwen": {
            "mention_rate": 0.5,
            "citation_rate": 0.0,
            "avg_position": None,
            "sov": 0.1
        }
    },
    "self_geo": {
        "total": 62.5,
        "dims": [
            {
                "name": "schema",
                "score": 80,
                "weight": 10,
                "signals": {}
            }
        ]
    },
    "self_seo": {
        "total": 70.0,
        "dims": []
    },
    "gap": {
        "dim_diff": {
            "schema": 15.0
        }
    },
    "authority_gap_note": "权威分基于 P0 代理；外部权威未计入"
}

def test_byte_identical(tmp_path):
    """Test that rendering the same input twice produces byte-identical output"""
    a = render(REPORT, out=tmp_path/"a.html")
    b = render(REPORT, out=tmp_path/"b.html")
    assert a.read_bytes() == b.read_bytes()           # 字节级一致
    assert "ECharts" in a.read_text() or "echarts" in a.read_text()
    assert "权威分基于 P0 代理" in a.read_text(encoding="utf-8")   # 缺口标注强制

def test_7_sections_present(tmp_path):
    """Test that all 7 required sections are present in the report"""
    out = render(REPORT, out=tmp_path/"report.html")
    html = out.read_text(encoding="utf-8")

    # Check for the 7 report sections in the redesigned Chinese dashboard.
    required_sections = [
        "执行摘要",
        "GEO 六维表现",
        "SEO 五项表现",
        "模型横向对比",
        "竞品差距",
        "规则迭代摘要",
        "本周优化建议",
        "数据附录",
    ]

    for section in required_sections:
        assert section in html, f"Section '{section}' not found in report"

def test_rules_iteration_section_rendered(tmp_path):
    """Test rules iteration section with data renders correctly"""
    base = {"week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "x",
            "metrics": {}, "self_geo": {"total": 47.6, "dims": []},
            "self_seo": {"total": 49.8, "dims": []}, "gap": {}}
    rep = {**base, "rules_iteration": {
        "week": 1, "from_version": "geo-seo-v1", "to_version": "geo-seo-v2",
        "entries": [{"signal": "has_breadcrumblist", "type": "signal_add", "target": "schema",
                     "status": "active", "change": "promoted",
                     "evidence": {"share": 0.206, "with_n": 7, "unique_n": 34,
                                  "platforms": ["doubao", "qwen", "zhipu"], "weeks": [1]}}],
        "weights_before": {"citability": 25}, "weights_after": {"citability": 25},
        "observations": ["SEO 权重证据流暂缺(GSC 太薄)→ 本期休眠",
                         "GEO 权重证据已记录,待 2 周同向后调整(v1.1 持续性门)"]}}
    out1 = render(rep, tmp_path / "a.html")
    out2 = render(rep, tmp_path / "b.html")
    html = out1.read_text(encoding="utf-8")
    assert out1.read_bytes() == out2.read_bytes()               # 字节级确定性
    assert "geo-seo-v1" in html and "geo-seo-v2" in html
    assert "面包屑结构化数据" in html and "已生效" in html
    assert "本期权重未调整" in html          # v1.1:首周持续性门 → 权重不变
    assert "本期休眠" in html and "持续性" in html

def test_rules_iteration_section_absent_graceful(tmp_path):
    """Test rules iteration section without data shows graceful message"""
    base = {"week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "x",
            "metrics": {}, "self_geo": {"total": 47.6, "dims": []},
            "self_seo": {"total": 49.8, "dims": []}, "gap": {}}
    html = render(base, tmp_path / "c.html").read_text(encoding="utf-8")
    assert "本期无规则迭代记录" in html

# ---- Fix(2026-08-24 审查#5): 采集真实分母与质量门必须在报告中可见 ----
def test_collection_gate_visible(tmp_path):
    rep = json.loads(json.dumps(REPORT))
    rep["metrics"]["qwen"].update({"planned": 15, "valid": 10, "failed": 5, "success_rate": 0.667})
    rep["collection_gate"] = {"manifest": True, "threshold": 0.95,
                              "min_success_rate": 0.667, "ok": False}
    html = render(rep, tmp_path / "gate.html").read_text(encoding="utf-8")
    assert "质量门" in html
    assert "66.7%" in html                       # 最低成功率可见
    assert "未通过质量门" in html                 # 门未过要明说,不再虚假健康
    assert "计划 15 · 有效 10 · 失败 5" in html  # planned/valid/failed

def test_collection_gate_absent_graceful(tmp_path):
    """旧报告/最小 dict(无新键)渲染不崩。"""
    html = render(REPORT, tmp_path / "old.html").read_text(encoding="utf-8")
    assert "数据完整性未记录" not in html and "完整性待确认" in html


# ---- T11(2026-09-02): SEO 维度口径注记 + 成本 token 呈现 ----
def test_seo_aggregation_note_present(tmp_path):
    """SEO 区标题旁必须带口径注记(w4+ 全页平均 / w1–w3 代表页,跨周对比有断点)。"""
    html = render(REPORT, tmp_path / "note.html").read_text(encoding="utf-8")
    assert "w4+ 维度=全页平均" in html
    assert "w1–w3 为代表页口径" in html and "跨周维度对比有断点" in html


def test_cost_row_renders_when_usage_present(tmp_path):
    rep = json.loads(json.dumps(REPORT))
    rep["cost"] = {
        "note": "token 用量(L1 usage 汇总;记录呈现、不折价不考核——spec v1.1)",
        "by_model": {
            "qwen": {"records_with_usage": 6, "input_tokens": 1000,
                     "output_tokens": 500, "total_tokens": 1500},
            "doubao": {"records_with_usage": 6, "input_tokens": 800,
                       "output_tokens": 400, "total_tokens": 1200},
        },
    }
    html = render(rep, tmp_path / "cost.html").read_text(encoding="utf-8")
    assert "成本(token,不折价)" in html
    assert "qwen 1500" in html and "doubao 1200" in html   # 按模型 total_tokens


def test_cost_absent_or_empty_graceful(tmp_path):
    """旧报告(无 cost 键)与空 by_model 均不渲染成本行,不崩。"""
    html_old = render(REPORT, tmp_path / "old.html").read_text(encoding="utf-8")
    assert "成本(token,不折价)" not in html_old
    rep = json.loads(json.dumps(REPORT))
    rep["cost"] = {"note": "n", "by_model": {}}
    html_empty = render(rep, tmp_path / "empty.html").read_text(encoding="utf-8")
    assert "成本(token,不折价)" not in html_empty


def test_dashboard_structure_and_interactions(tmp_path):
    """The approved layout and core interactions remain present in future reports."""
    html = render(REPORT, tmp_path / "dashboard.html").read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert 'class="sidebar"' in html
    assert 'id="week-select"' in html
    assert ".select-wrap::after" in html and "appearance: none" in html
    assert 'class="data-status"' not in html and 'class="pulse-dot"' not in html
    assert 'id="print-report"' not in html and "导出报告" not in html
    assert 'class="info-dot"' not in html
    assert '<a href="#geo-seo-analysis">GEO / SEO 分析</a>' in html
    assert '<a href="#diagnostics">竞品差距 / 规则迭代</a>' in html
    assert not any(index in html for index in "①②③④⑤⑥⑦")
    assert 'data-chart-mode' not in html and 'class="segmented"' not in html
    assert "metricText" in html and " 分 / " in html
    assert html.count('<span class="card-subtitle">得分 / 权重</span>') == 2
    assert '<details class="card appendix section"' in html
    assert "品牌提及率" in html and "声量占比" in html


# ---- T13(2026-09-02): 数据降级事件可见(有则黄色提示行;旧报告/全零不渲染) ----
DEGRADED_KEYS = ("self_geo_score_skipped", "page_seo_skipped", "gap_skipped",
                 "competitor_skipped", "l3_semantic_degraded")

def test_degraded_events_hint_renders_when_nonzero(tmp_path):
    """degraded_events 有非零项 → 黄色提示行列出各类计数(降级可见,不虚报健康)。"""
    rep = json.loads(json.dumps(REPORT))
    rep["degraded_events"] = {k: 0 for k in DEGRADED_KEYS}
    rep["degraded_events"]["page_seo_skipped"] = 1
    rep["degraded_events"]["l3_semantic_degraded"] = 2
    html = render(rep, tmp_path / "deg.html").read_text(encoding="utf-8")
    assert "数据降级事件" in html
    assert "page_seo_skipped 1" in html and "l3_semantic_degraded 2" in html


def test_degraded_events_zero_or_absent_graceful(tmp_path):
    """旧报告(无键)与全零 dict 均不渲染提示行(不虚报降级,T11 同款守卫模式)。"""
    html_old = render(REPORT, tmp_path / "old.html").read_text(encoding="utf-8")
    assert "数据降级事件" not in html_old
    rep = json.loads(json.dumps(REPORT))
    rep["degraded_events"] = {k: 0 for k in DEGRADED_KEYS}
    html_zero = render(rep, tmp_path / "zero.html").read_text(encoding="utf-8")
    assert "数据降级事件" not in html_zero


# ---- §9(2026-09-02): static robots 未知(degraded)呈现——flag 置位才改写 0.0 分格 ----
def _rep_with_robots_dim():
    """带 technical_geo 维度(含 robots 两信号)的最小报告;其余字段同 REPORT。"""
    rep = json.loads(json.dumps(REPORT))
    rep["self_geo"] = {"total": 40.0, "dims": [{
        "name": "technical_geo", "score": 40.0, "weight": 15,
        "signals": {"canonical_present": 100.0, "https": 100.0,
                    "robots_claudebot": 0.0, "robots_gptbot": 0.0}}]}
    return rep


def test_robots_unknown_label_when_flag_set(tmp_path):
    """static_robots_unknown 置位 → robots 信号显示「未知(degraded)」而非 0.0 分格。"""
    rep = _rep_with_robots_dim()
    rep["static_robots_unknown"] = True
    html = render(rep, tmp_path / "unknown.html").read_text(encoding="utf-8")
    assert "允许 GPTBot <strong>未知(degraded)</strong>" in html
    assert "允许 ClaudeBot <strong>未知(degraded)</strong>" in html
    assert "允许 GPTBot <strong>0.0</strong>" not in html
    assert "允许 ClaudeBot <strong>0.0</strong>" not in html
    assert "HTTPS 可用 <strong>100.0</strong>" in html   # 非 robots 信号呈现不受影响


def test_robots_render_unchanged_without_flag(tmp_path):
    """无 flag(旧报告/正常快照)→ 渲染不变:仍是 0.0 分格,无「未知(degraded)」字样。"""
    html = render(_rep_with_robots_dim(), tmp_path / "normal.html").read_text(encoding="utf-8")
    assert "未知(degraded)" not in html
    assert "允许 GPTBot <strong>0.0</strong>" in html
    assert "允许 ClaudeBot <strong>0.0</strong>" in html
