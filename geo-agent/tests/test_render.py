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
        cited_n=1,platforms=["qwen"],confidence="low",action="多用对比表",examples=["https://a.com"])]

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
