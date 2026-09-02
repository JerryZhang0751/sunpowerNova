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

def test_render_profiles_budget_exhausted_suffix():
    """§11(2026-09-02): 结论 dict 带 budget_exhausted（global/platform，D5）时,
    「外部未验证」呈现追加「（预算耗尽:原因）」后缀,与真查无从原因上区分;
    附录 Tier2 行同样带原因。"""
    vf = {"Qwen": {"answer": "", "sources": [], "confidence": "外部未验证",
                   "budget_exhausted": "global"},
          "Doubao": {"answer": "", "sources": [], "confidence": "外部未验证",
                     "budget_exhausted": "platform"},
          "ChatGPT": {"answer": "", "sources": [], "confidence": "外部未验证",
                      "budget_exhausted": "global"}}
    mets = {"qwen": {"n": 1, "mention_rate": 0.0, "citation_rate": 0.0},
            "doubao": {"n": 1, "mention_rate": 0.0, "citation_rate": 0.0}}
    md = render_profiles(mets, vf, week=1)
    assert "置信度：外部未验证（预算耗尽:global）" in md      # Qwen 全局预算耗尽
    assert "置信度：外部未验证（预算耗尽:platform）" in md    # Doubao 平台预算耗尽
    # 附录 Tier2 同带原因（answer="" 渲染为空是既有行为,本任务只加置信度后缀）
    assert "- ChatGPT:  [外部未验证（预算耗尽:global）]" in md


def test_render_profiles_no_budget_key_bytes_unchanged():
    """无 budget_exhausted 键（真查无/正常查证）渲染逐字节不变。"""
    vf = {"Qwen": {"answer": "阿里云搜索", "sources": ["https://help.aliyun.com/x"],
                   "confidence": "mid"}}
    md = render_profiles({"qwen": {"n": 1, "mention_rate": 0.0, "citation_rate": 0.0}}, vf, week=1)
    assert "预算耗尽" not in md
    assert "- 爬虫名/收录(联网查证): 阿里云搜索\n  来源：https://help.aliyun.com/x | 置信度：mid\n" in md


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

def test_render_playbook_feedback_section_tolerates_null_metrics():
    """w3 实跑回归(2026-09-01): w2 eval_report 的 gap=None(竞品 L3 缺失致 gap 跳过)
    → latest(=w2) 三指标为 null;prev(=w1) 有值 → Δ 减法 NoneType-float TypeError。
    w3 是首个 latest/prev 同时存在的周,首次踩中。反馈节必须容忍任一侧缺失。"""
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 45, "total_cited_sources": 1469, "l3_resolved": 134,
                                "l3_missing": 1315, "l3_js_only": 20})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [],
            "latest": {"week": 2, "mention_rate": None, "citation_rate": None,
                       "sov": None, "self_geo": 41.2, "self_seo": 49.9},
            "prev": {"week": 1, "mention_rate": 0.133, "citation_rate": 0.089,
                     "sov": 3.78, "self_geo": 43.4, "self_seo": 49.8},
            "rule_version": "geo-seo-v3"}
    md = render_playbook([], agg, 3, feed=feed)  # 不得 raise
    assert "## 6. 上期动作→指标对照" in md
    assert "41.2" in md and "43.4" in md          # 仍有值的行照常展示
    assert "数据缺失" in md                        # null 行明确标注,不静默不崩


def test_render_feedback_rejects_non_numeric_metrics():
    """codex w3 修改三(2026-09-02): 指标差值只对有效数值(int|float、非 bool、
    有限值)计算——字符串/NaN/inf/缺键一律"数据缺失/Δ不可算",禁止隐式 float()
    转换(字符串可能掩盖上游 schema 漂移)。合法数字输出保持不变。"""
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 45, "total_cited_sources": 1469, "l3_resolved": 134,
                                "l3_missing": 1315, "l3_js_only": 20})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [],
            "latest": {"week": 2, "mention_rate": "0.133",        # 字符串
                       "citation_rate": float("nan"),               # NaN
                       "sov": float("inf"),                         # 无穷
                       "self_geo": 41.2, "self_seo": True},         # bool 非数值
            "prev": {"week": 1, "mention_rate": 0.133, "citation_rate": 0.089,
                     "sov": 3.78, "self_geo": 43.4, "self_seo": 49.8},
            "rule_version": "geo-seo-v4"}
    md = render_playbook([], agg, 3, feed=feed)                    # 不得 raise
    lines = [l for l in md.splitlines() if l.startswith("- ")]
    mention = next(l for l in lines if l.startswith("- mention_rate"))
    assert "数据缺失" in mention and "Δ不可算" in mention
    sov = next(l for l in lines if l.startswith("- sov"))
    assert "数据缺失" in sov and "Δ不可算" in sov
    geo = next(l for l in lines if l.startswith("- self_geo"))
    assert "41.2" in geo and "43.4" in geo and "Δ-2.2" in geo      # 合法数字照常算差值


def test_render_feedback_tolerates_missing_keys_both_sides():
    """codex w3 修改三: 任一侧缺键(.get→None)同样走数据缺失;prev 缺键不炸。"""
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 0, "total_cited_sources": 0, "l3_resolved": 0,
                                "l3_missing": 0, "l3_js_only": 0})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [],
            "latest": {"week": 2, "self_geo": 41.2},               # 其余键整体缺失
            "prev": {"week": 1, "self_geo": 43.4},                 # prev 同样缺其余键
            "rule_version": "geo-seo-v4"}
    md = render_playbook([], agg, 3, feed=feed)                    # 不得 raise
    mention = next(l for l in md.splitlines() if l.startswith("- mention_rate"))
    assert "数据缺失" in mention and "Δ不可算" in mention


def test_render_feedback_first_period_invalid_value_marked():
    """codex w3 修改三: 无 prev(首期)时无效值显示"数据缺失(首期基线,无环比)",
    有效值仍显示首期基线。"""
    agg = FeatureAggregates(week=1,
        coverage=type("C", (), {"total_l1": 0, "total_cited_sources": 0, "l3_resolved": 0,
                                "l3_missing": 0, "l3_js_only": 0})(),
        formats=[], sources={}, platforms={}, problem_space={})
    feed = {"published": [],
            "latest": {"week": 1, "mention_rate": "n/a", "self_geo": 47.6},
            "prev": None, "rule_version": "geo-seo-v1"}
    md = render_playbook([], agg, 2, feed=feed)
    mention = next(l for l in md.splitlines() if l.startswith("- mention_rate"))
    assert "数据缺失(首期基线" in mention
    geo = next(l for l in md.splitlines() if l.startswith("- self_geo"))
    assert "47.6" in geo and "首期基线" in geo


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
