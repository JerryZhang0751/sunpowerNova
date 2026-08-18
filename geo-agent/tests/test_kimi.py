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

def test_web_search_confidence_tolerates_markdown_bold():
    # Perplexity 实测格式：**置信度**：high（加粗星号插在冒号前，旧正则漏匹配→误标未验证）
    raw = "PerplexityBot 是索引爬虫。\n来源：https://docs.perplexity.ai/guides/bots\n**置信度**：high"
    fake = lambda messages, tools=None, timeout=120: raw
    out = web_search_verify([{"platform":"Perplexity","fact":"crawler"}], chat_fn=fake)
    assert out["Perplexity"]["confidence"] == "high"

from types import SimpleNamespace as NS
from geo.research.kimi import _drive_web_search, _WEB_TOOLS

def test_web_search_tool_schema_is_official_builtin_function():
    # 回归：builtin_tools 曾被 Moonshot 400 拒；官方协议 = builtin_function/$web_search
    assert _WEB_TOOLS == [{"type": "builtin_function", "function": {"name": "$web_search"}}]

def test_web_search_verify_passes_official_tools_to_chat_fn():
    seen = {}
    def fake(messages, tools=None, timeout=120):
        seen["tools"] = tools
        return "无法确认。"
    web_search_verify([{"platform":"X","fact":"crawler"}], chat_fn=fake)
    assert seen["tools"] == _WEB_TOOLS

def _tool_call(id="call_1", name="$web_search", args='{"query":"qwen crawler"}'):
    return NS(id=id, function=NS(name=name, arguments=args))

def test_drive_web_search_roundtrips_verbatim_arguments():
    # 官方协议：finish_reason=tool_calls → role=tool 消息必须把 arguments 原封不动回传，
    # 服务端据此执行搜索并给终答（platform.kimi.com/docs/guide/use-web-search）
    calls = []
    def create(**kw):
        calls.append(kw)
        if len(calls) == 1:
            msg = NS(content="", tool_calls=[_tool_call()])
            return NS(choices=[NS(finish_reason="tool_calls", message=msg)])
        msg = NS(content="Qwen 爬虫是 QwenBot。来源：https://help.aliyun.com/x 置信度：mid", tool_calls=None)
        return NS(choices=[NS(finish_reason="stop", message=msg)])
    out = _drive_web_search(create, [{"role":"user","content":"q"}])
    assert "QwenBot" in out
    assert len(calls) == 2
    assert all(c["tools"] == _WEB_TOOLS for c in calls)      # 每轮都带完整 tools 声明
    tool_msgs = [m for m in calls[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["content"] == '{"query":"qwen crawler"}'  # 原样回传
    assert tool_msgs[0]["tool_call_id"] == "call_1" and tool_msgs[0]["name"] == "$web_search"

def test_drive_web_search_caps_rounds_and_returns_empty():
    def create(**kw):
        msg = NS(content="", tool_calls=[_tool_call()])
        return NS(choices=[NS(finish_reason="tool_calls", message=msg)])
    assert _drive_web_search(create, [{"role":"user","content":"q"}], max_rounds=3) == ""

def test_drive_web_search_nudges_on_empty_stop():
    # 偶发缺陷：模型想续搜时 API 返 stop+空 content → 注入催答（保留 tools）直至实质终答
    calls = []
    def create(**kw):
        calls.append(kw)
        n = len(calls)
        if n == 1:   # 发起搜索
            return NS(choices=[NS(finish_reason="tool_calls", message=NS(content="", tool_calls=[_tool_call()]))])
        if n == 2:   # 空 stop（缺陷态）
            return NS(choices=[NS(finish_reason="stop", message=NS(content="", tool_calls=None))])
        return NS(choices=[NS(finish_reason="stop",
                              message=NS(content="结论：X。来源：https://a.com/x 置信度：mid", tool_calls=None))])
    out = _drive_web_search(create, [{"role":"user","content":"q"}])
    assert out.startswith("结论：X")
    nudges = [m for m in calls[2]["messages"] if m.get("role") == "user" and "请继续完成查证" in m["content"]]
    assert nudges, "催答消息必须已注入且 tools 仍保留"
    assert calls[2]["tools"] == _WEB_TOOLS
