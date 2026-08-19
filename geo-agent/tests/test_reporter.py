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

    # Check for the 7 sections mentioned in the brief
    required_sections = [
        "执行摘要",  # ①执行摘要
        "GEO",       # ②自审 GEO6维雷达
        "SEO",       # ②自审 SEO5支柱
        "3 模型横向对比",  # ③3模型横向对比
        "竞品",      # ④竞品差值热图
        "规则",      # ⑤规则迭代摘要
        "优化",      # ⑥优化建议
        "附录"       # ⑦数据附录
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
    assert "geo-seo-v1</code> → <code>geo-seo-v2" in html
    assert "has_breadcrumblist" in html and "promoted" in html
    assert "25→26" not in html and "(无)" in html          # v1.1:首周持续性门 → 权重不变
    assert "本期休眠" in html and "持续性" in html

def test_rules_iteration_section_absent_graceful(tmp_path):
    """Test rules iteration section without data shows graceful message"""
    base = {"week": 1, "rule_version": "geo-seo-v1", "prompt_set_version": "x",
            "metrics": {}, "self_geo": {"total": 47.6, "dims": []},
            "self_seo": {"total": 49.8, "dims": []}, "gap": {}}
    html = render(base, tmp_path / "c.html").read_text(encoding="utf-8")
    assert "本期无规则迭代记录" in html