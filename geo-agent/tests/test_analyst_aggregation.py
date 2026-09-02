"""T11(2026-09-02 D4): SEO dims 全页平均 + gap avg_position 真值 + 成本 token 呈现。

- mean 口径(新默认)= 维度跨全页均值,与 total 同源;first_page = w1-w3 旧口径
  (黄金锁通路,tests/test_v1_semantics.py 注入)。
- gap.metrics.avg_position 接入 per-model 已算值(旧恒 None 占位消灭)。
- cost 节 = L1 usage 按模型汇总,记录呈现、不折价不考核(spec v1.1)。
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from geo.assess.analyst import assemble
from geo.shared.models import L1Record, L2Record, CitedSource, L3Source


def mk_l2(mentioned=False, cited=False, position=None, competitors=None):
    return L2Record(
        cited_sources=[CitedSource(url="https://example.com", position=position,
                                   title="", snippet="")] if cited else [],
        mentioned=mentioned, cited_with_link=cited, citation_position=position,
        sentiment="neu", competitors_mentioned=competitors or [], low_confidence=False)


def mk_l1(model="qwen", prompt_id="B02", run=1, l2=None, usage=None):
    return L1Record(week=901, model=model, prompt_id=prompt_id, run=run,
                    answer="ans", l2=l2 or mk_l2(), usage=usage or {},
                    elapsed_s=1.0, search_triggered=False,
                    ts_iso="2026-09-02T12:00:00Z", prompt_set_version="psv-t11")


# 两页 fixture:dim(on_page←https)页1=100 页2=0 → mean=50;total=两页 total 均值=50
PAGES = [
    {"url": "https://sunhestia.com/", "https": True, "http_status": 200},
    {"url": "https://sunhestia.com/about", "https": False, "http_status": 200},
]
SEO_RULES_1DIM = SimpleNamespace(version="t11", signals={"on_page": ["https"]},
                                 weights={"on_page": 100.0})
GEO_RULES_1DIM = SimpleNamespace(version="t11", signals={"brand": ["entity_known"]},
                                 weights={"brand": 100.0})


def _assemble(records=None, pages=PAGES, l3=None, **kw):
    records = records if records is not None else [mk_l1()]
    with patch('geo.assess.analyst.iter_l1', side_effect=lambda *a, **k: iter(records)), \
         patch('geo.assess.analyst._load_l3_source', return_value=l3), \
         patch('geo.assess.analyst._load_static_signals',
               return_value={"site": "https://sunhestia.com", "pages": pages}), \
         patch('geo.assess.analyst._load_gsc_snapshot',
               return_value={"impressions": 100, "clicks": 5, "ctr": 0.05}):
        kw.setdefault("rules_seo", SEO_RULES_1DIM)
        return assemble(901, write=False, **kw)


# ---- SEO dims 聚合口径 ----

def test_seo_dims_mean_across_two_pages():
    rep = _assemble(seo_dims_aggregation="mean")
    dim = next(d for d in rep["self_seo"]["dims"] if d["name"] == "on_page")
    assert dim["score"] == 50.0                       # 页1 100 + 页2 0 → 均值 50
    assert dim["signals"] == {"aggregation": "mean_across_pages", "n_pages": 2}
    assert rep["self_seo"]["total"] == 50.0           # total 本就是页均值,与维度同源


def test_seo_dims_first_page_legacy():
    rep = _assemble(seo_dims_aggregation="first_page")
    dim = next(d for d in rep["self_seo"]["dims"] if d["name"] == "on_page")
    assert dim["score"] == 100.0                      # 旧口径=第 1 页(https=True)
    assert rep["self_seo"]["total"] == 50.0           # total 口径不受维度聚合影响


def test_mean_is_default_aggregation():
    """默认值必须是 mean(T11 起真实切默认;w1-w3 重算走 first_page 注入)。"""
    rep_default = _assemble()
    rep_mean = _assemble(seo_dims_aggregation="mean")
    assert rep_default["self_seo"]["dims"] == rep_mean["self_seo"]["dims"]


def test_seo_dims_aggregation_invalid_value_rejected():
    with pytest.raises(ValueError):
        _assemble(seo_dims_aggregation="median")


# ---- gap.metrics.avg_position 真值 ----

MIN_L3 = L3Source(url="https://example.com", sha1="s", text="t")


def test_gap_avg_position_real_value():
    # qwen 两次引用 position 4/7 → 模型 avg=5.5;doubao 无引用 → None(均值跳过)
    records = [
        mk_l1(model="qwen", run=1, l2=mk_l2(mentioned=True, cited=True, position=4)),
        mk_l1(model="qwen", run=2, l2=mk_l2(mentioned=True, cited=True, position=7)),
        mk_l1(model="doubao", run=1, l2=mk_l2(mentioned=True, cited=False)),
    ]
    rep = _assemble(records=records, l3=MIN_L3, rules_geo=GEO_RULES_1DIM)
    assert rep["metrics"]["qwen"]["avg_position"] == 5.5
    assert rep["metrics"]["doubao"]["avg_position"] is None
    assert rep["gap"] is not None, "品牌+竞品 L3 均在场 → gap 必须可算"
    assert rep["gap"]["metrics"]["avg_position"] == 5.5   # 不再恒 None


def test_gap_avg_position_none_when_no_positions():
    # 有引用但无 position → per-model 全 None → gap avg_position=None(不虚报)
    records = [mk_l1(model="qwen", run=1,
                     l2=mk_l2(mentioned=True, cited=True, position=None))]
    rep = _assemble(records=records, l3=MIN_L3, rules_geo=GEO_RULES_1DIM)
    assert rep["gap"] is not None
    assert rep["gap"]["metrics"]["avg_position"] is None


# ---- cost 节(L1 usage 汇总) ----

def test_cost_section_from_l1_usage():
    records = [
        mk_l1(model="qwen", run=1,
              usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}),
        mk_l1(model="qwen", run=2,
              usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}),
        # 豆包系字段名(prompt/completion)且无 total_tokens → it+ot 兜底
        mk_l1(model="doubao", run=1, usage={"prompt_tokens": 200, "completion_tokens": 80}),
        # 空 usage → 不计入
        mk_l1(model="doubao", run=2, usage={}),
    ]
    rep = _assemble(records=records)
    cost = rep["cost"]
    assert cost["by_model"]["qwen"] == {"records_with_usage": 2, "input_tokens": 200,
                                        "output_tokens": 100, "total_tokens": 300}
    assert cost["by_model"]["doubao"] == {"records_with_usage": 1, "input_tokens": 200,
                                          "output_tokens": 80, "total_tokens": 280}
    assert "不折价" in cost["note"]                   # 记录呈现、不折价不考核(spec v1.1)


def test_cost_section_empty_when_no_usage():
    rep = _assemble(records=[mk_l1(usage={})])
    assert rep["cost"]["by_model"] == {}
