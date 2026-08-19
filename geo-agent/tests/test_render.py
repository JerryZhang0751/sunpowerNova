# tests/test_render.py
from geo.research.render import render_playbook, render_profiles
from geo.research.models import FeatureAggregates, Coverage, FeatureBucket, PlaybookConclusion

def _agg():
    return FeatureAggregates(week=1, coverage=Coverage(1,1,1,0,0),
        formats=[FeatureBucket("comparison_table",1,1,["qwen"],True)],
        sources={"domain_type":{"manufacturer":1},"page_type":{"review":1},"schema":{"Article":1},
                 "has_publish_date":1,"ugc":0,"resolved":1},
        platforms={"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}},
        problem_space={"intent_clusters":[{"intent":"comparison","n":1}],"topic_gaps":["hestia solar"]})

def _concl():
    return [PlaybookConclusion(id="F01",category="format",conclusion="对比表常见",sample_n=1,
        cited_n=1,platforms=["qwen"],confidence="low",action="多用对比表",examples=["https://a.com"],bucket_key="comparison_table")]

def test_render_playbook_has_sections_and_warning():
    md = render_playbook(_concl(), _agg(), week=1)
    assert "# SunHestia GEO Playbook · w1" in md
    assert "## 1. 被引格式特征" in md
    assert "## 5. 可复用内容模板" in md
    assert "观察性相关" in md                     # honesty warning
    assert "comparison_table" in md or "对比表" in md
    assert "sample_n=1" in md or "sample_n= 1" in md

def test_render_profiles_data_and_web_sections():
    vf = {"Qwen":{"answer":"阿里云搜索","sources":["https://help.aliyun.com/x"],"confidence":"mid"}}
    md = render_profiles({"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}}, vf, week=1)
    assert "# 平台引用画像 · w1" in md
    assert "Qwen" in md and "阿里云搜索" in md
    assert "置信度" in md and "mid" in md

def test_render_playbook_per_bucket_matching():
    """Test that format conclusions match to buckets by bucket_key, not id prefix."""
    # Two buckets, two conclusions with different bucket_keys
    agg = FeatureAggregates(week=1, coverage=Coverage(1,1,1,0,0),
        formats=[FeatureBucket("comparison_table",1,1,["qwen"],True),
                 FeatureBucket("qa",2,1,["doubao"],False)],
        sources={"domain_type":{"manufacturer":1},"page_type":{"review":1},"schema":{"Article":1},
                 "has_publish_date":1,"ugc":0,"resolved":1},
        platforms={"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}},
        problem_space={"intent_clusters":[{"intent":"comparison","n":1}],"topic_gaps":[]})
    conclusions = [
        PlaybookConclusion(id="F01",category="format",conclusion="对比表常见",sample_n=1,
            cited_n=1,platforms=["qwen"],confidence="low",action="多用对比表",examples=[],bucket_key="comparison_table"),
        PlaybookConclusion(id="F02",category="format",conclusion="Q&A很重要",sample_n=1,
            cited_n=2,platforms=["doubao"],confidence="mid",action="增加FAQ",examples=[],bucket_key="qa")
    ]
    md = render_playbook(conclusions, agg, week=1)
    # Each conclusion should land on its matching bucket
    assert "comparison_table" in md and "对比表常见" in md
    assert "qa" in md and "Q&A很重要" in md
    # Verify wrong conclusions don't appear (the bug would place both conclusions on both buckets)
    lines = md.split("\n")
    comparison_table_section = [l for i,l in enumerate(lines) if "comparison_table" in l][0]
    qa_section_index = next(i for i,l in enumerate(lines) if "qa" in l)
    # Check that comparison_table conclusion appears near comparison_table bucket
    assert any("对比表常见" in l for l in lines[qa_section_index-5:qa_section_index+5])
    # Check that qa conclusion appears near qa bucket
    assert any("Q&A很重要" in l for l in lines[qa_section_index:qa_section_index+5])

def test_render_playbook_feedback_section():
    from geo.research.render import render_playbook
    from geo.research.models import FeatureAggregates
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 45, "total_cited_sources": 1469, "l3_resolved": 134,
                                "l3_missing": 1315, "l3_js_only": 20})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [{"slug": "self-consumption", "created": "2026-08-18"}],
            "latest": {"week": 1, "mention_rate": 0.133, "citation_rate": 0.089,
                       "sov": 3.78, "self_geo": 47.6, "self_seo": 49.8},
            "prev": None, "rule_version": "geo-seo-v1"}
    md = render_playbook([], agg, 2, feed=feed)
    assert "## 6. 上期动作→指标对照" in md
    assert "self-consumption" in md and "47.6" in md and "首期" in md   # prev=None → 首期基线注
    md2 = render_playbook([], agg, 2, feed=None)
    assert "无对照" in md2

def test_render_playbook_rule_version_live():
    from geo.research.render import render_playbook
    from geo.research.models import FeatureAggregates
    from geo.shared.config import settings
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 0, "total_cited_sources": 0, "l3_resolved": 0,
                                "l3_missing": 0, "l3_js_only": 0})(),
        formats=[], sources={}, platforms={}, problem_space={})
    md = render_playbook([], agg, 3, feed=None)
    header = md.split("\n")[1]
    assert f"rule_version {settings.run.rule_version}" in header   # 动态读,不再硬编码
