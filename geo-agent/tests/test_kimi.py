# tests/test_kimi.py
import json
from geo.research.kimi import synthesize
from geo.research.models import FeatureAggregates, Coverage, FeatureBucket

def _agg():
    return FeatureAggregates(week=1, coverage=Coverage(1,1,1,0,0),
        formats=[FeatureBucket("comparison_table",1,1,["qwen"],True)],
        sources={"domain_type":{"manufacturer":1},"page_type":{"review":1},"schema":{"Article":1},
                 "has_publish_date":1,"ugc":0,"resolved":1},
        platforms={"qwen":{"n":1,"mention_rate":0.0,"citation_rate":0.0}},
        problem_space={"intent_clusters":[{"intent":"comparison","n":1}],"topic_gaps":[]})

def test_synthesize_parses_good_json():
    good = json.dumps({"conclusions":[
        {"id":"F01","category":"format","conclusion":"对比表常见","sample_n":1,"cited_n":1,
         "platforms":["qwen"],"confidence":"low","action":"多用对比表","examples":["https://a.com"],"bucket_key":"comparison_table"}]})
    fake = lambda messages, tools=None, timeout=120: good
    out = synthesize(_agg(), examples=[], chat_fn=fake)
    assert len(out)==1 and out[0].id=="F01" and out[0].confidence=="low" and out[0].bucket_key=="comparison_table"

def test_synthesize_bad_json_returns_empty():
    fake = lambda messages, tools=None, timeout=120: "not json{"
    assert synthesize(_agg(), examples=[], chat_fn=fake) == []

def test_synthesize_preserves_sample_n_no_invent():
    # conclusion sample_n must come from aggregates (1), not invented
    good = json.dumps({"conclusions":[{"id":"F01","category":"format","conclusion":"x",
        "sample_n":999,"cited_n":1,"platforms":[],"confidence":"low","action":"y","examples":[]}]})
    fake = lambda messages, tools=None, timeout=120: good
    out = synthesize(_agg(), examples=[], chat_fn=fake)
    # synthesize MUST clamp sample_n to the aggregate's resolved sample_n, refusing invented 999
    assert out[0].sample_n == 1

from geo.research.kimi import web_search_verify

def test_web_search_verify_parses_answer_block():
    raw = ("根据联网搜索，Qwen 的网页检索后端为阿里云搜索，公开爬虫名文档较少。\n"
           "来源：https://help.aliyun.com/x\n置信度：mid")
    fake = lambda messages, tools=None, timeout=120: raw
    out = web_search_verify([{"platform":"Qwen","fact":"crawler_and_inclusion"}], chat_fn=fake)
    assert "Qwen" in out
    assert out["Qwen"]["confidence"] == "mid"
    assert any("aliyun" in s for s in out["Qwen"]["sources"])

def test_web_search_verify_no_sources_marks_unverified():
    fake = lambda messages, tools=None, timeout=120: "无法确认。"
    out = web_search_verify([{"platform":"X","fact":"crawler"}], chat_fn=fake)
    assert out["X"]["confidence"] == "外部未验证"
