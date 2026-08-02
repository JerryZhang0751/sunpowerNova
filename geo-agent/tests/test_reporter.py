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