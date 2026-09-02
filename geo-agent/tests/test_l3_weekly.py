"""T9(2026-09-02 D1): L3 缓存周目录隔离。

每周独立快照自洽(data/sources/w{week}/{sha1[:12]}),历史 SEO 重算可复现:
- week<=3 查找回退链 [w{week}, w3](w1-w3 的历史评估消费的是迁移前共享缓存=迁移后 w3/ 终态,黄金锁通路);
- week>=4 只读本周,miss=诚实缺失(跨周真重抓)。
- 读命中=text.md 与 meta.json 齐备且非毒化;写序 meta→text(text=完整对标志)——
  崩溃残留只可能是孤儿 meta/孤儿 text,判 miss 重抓自愈,不再产生
  "research 读 meta 撞 FileNotFoundError 被吞成永久 failed"的路径。
"""
import ipaddress
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from geo.shared import storage
from geo.shared.storage import sha1_url, source_dir, legacy_source_dirs
from geo.fetch.fetcher import fetch_source
from geo.assess.analyst import _load_l3_source

TEST_WEEK = 901
_PUB = [ipaddress.ip_address("93.184.216.34")]
BODY = "<html><head><title>t</title></head><body><p>word " * 20 + "</p></body></html>"


@pytest.fixture(autouse=True)
def _iso_repo(tmp_path, monkeypatch):
    """storage 与 analyst 双 patch 到同一 tmp 根(fetcher 写路径 = analyst 读路径)。"""
    monkeypatch.setattr(storage, "REPO", tmp_path)
    import geo.assess.analyst as _analyst
    monkeypatch.setattr(_analyst, "REPO", tmp_path)
    return tmp_path


def _write_pair(week: int, url: str, text: str = "cached text") -> Path:
    """按 fetcher 的落盘形态预置一个完整对。"""
    sha = sha1_url(url)
    sd = source_dir(week, sha)
    meta = {"url": url, "sha1": sha, "http_status": 200, "text": text,
            "structural": {}, "semantic": {}, "js_only": False,
            "fetched_iso": "2026-08-01T00:00:00Z"}
    (sd / "text.md").write_text(text, encoding="utf-8")
    (sd / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return sd


def _net_mock(calls: list):
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text=BODY)
    return httpx.MockTransport(handler)


# ---- source_dir 周隔离 -------------------------------------------------------

def test_source_dir_is_week_scoped(tmp_path):
    d = storage.source_dir(4, "a" * 40)
    assert d == tmp_path / "data" / "sources" / "w4" / ("a" * 12) and d.exists()


def test_legacy_source_dirs_chain():
    """week<=3 回退链含 w3(黄金锁通路);w4+ 只含本周;week==3 不重复列 w3。"""
    r = Path("/r")
    assert legacy_source_dirs(1, r) == [r / "data" / "sources" / "w1",
                                        r / "data" / "sources" / "w3"]
    assert legacy_source_dirs(3, r) == [r / "data" / "sources" / "w3"]
    assert legacy_source_dirs(4, r) == [r / "data" / "sources" / "w4"]
    assert legacy_source_dirs(901, r) == [r / "data" / "sources" / "w901"]


# ---- fetch_source: 成对命中 / 孤儿自愈 / 写序 --------------------------------

def test_fetch_source_full_pair_is_hit_no_network():
    url = "https://weekly.example/pair"
    _write_pair(TEST_WEEK, url, text="weekly cached")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                           transport=_net_mock(calls))
    assert calls == [], "完整对必须判命中,不得发起网络"
    assert rec.text == "weekly cached"


def test_fetch_source_meta_only_orphan_is_miss():
    """孤儿 meta(新写序的崩溃残留)→ miss → 重抓 → 两文件齐备自愈。"""
    url = "https://orphan-meta.example/a"
    sha = sha1_url(url)
    sd = source_dir(TEST_WEEK, sha)
    (sd / "meta.json").write_text(json.dumps(
        {"url": url, "sha1": sha, "http_status": 200, "text": "stale",
         "structural": {}, "semantic": {}, "js_only": False,
         "fetched_iso": "2026-08-01T00:00:00Z"}), encoding="utf-8")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                           transport=_net_mock(calls))
    assert calls, "孤儿 meta 必须视为 miss 重抓"
    assert rec.text != "stale"
    assert (sd / "text.md").exists() and (sd / "meta.json").exists()


def test_fetch_source_text_only_orphan_is_miss():
    """孤儿 text.md(旧写序的崩溃残留,旧读路径在此 FileNotFoundError)→ miss 重抓。"""
    url = "https://orphan-text.example/a"
    sd = source_dir(TEST_WEEK, sha1_url(url))
    (sd / "text.md").write_text("stale", encoding="utf-8")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                           transport=_net_mock(calls))
    assert calls, "孤儿 text 必须视为 miss 重抓"
    assert (sd / "meta.json").exists(), "重抓后必须补齐 meta,自愈成完整对"


def test_fetch_source_corrupt_meta_is_miss():
    """坏 meta(残缺 JSON)→ miss 重抓覆写;解析错不上抛(与 analyst/corpus 读路径对称),
    否则被 fetch_node/fetch_topn 吞掉后坏 meta 永不覆写(URL 该周永久 failed)。"""
    url = "https://corrupt-meta.example/a"
    sd = source_dir(TEST_WEEK, sha1_url(url))
    (sd / "text.md").write_text("stale", encoding="utf-8")
    (sd / "meta.json").write_text("{not json", encoding="utf-8")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                           transport=_net_mock(calls))
    assert calls, "坏 meta 必须判 miss 重抓"
    assert rec.http_status == 200
    assert json.loads((sd / "meta.json").read_text(encoding="utf-8"))["url"] == url


def test_fetch_source_schema_drift_meta_is_miss():
    """schema 漂移(合法 JSON 但字段不符 → TypeError)同样判 miss 重抓。"""
    url = "https://drift-meta.example/a"
    sd = source_dir(TEST_WEEK, sha1_url(url))
    (sd / "text.md").write_text("stale", encoding="utf-8")
    (sd / "meta.json").write_text('{"unexpected_field": true}', encoding="utf-8")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                           transport=_net_mock(calls))
    assert calls, "schema 漂移 meta 必须判 miss 重抓"
    assert rec.http_status == 200


def test_fetch_source_writes_meta_before_text(monkeypatch):
    """写序反转 meta→text:text.md 存在即完整对标志。"""
    import geo.fetch.fetcher as F
    order: list = []
    real = F.atomic_write_text

    def spy(path, text):
        order.append(Path(path).name)
        return real(path, text)

    monkeypatch.setattr(F, "atomic_write_text", spy)
    url = "https://writeorder.example/a"
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        fetch_source(url, TEST_WEEK, fetcher_kimi=False,
                     transport=_net_mock([]))
    assert order == ["meta.json", "text.md"]


# ---- 跨周隔离: w4 不读 w3(D1 跨周真重抓) ------------------------------------

def test_fetch_source_w4_does_not_read_w3():
    url = "https://crossweek.example/a"
    _write_pair(3, url, text="w3 state")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, 4, fetcher_kimi=False, transport=_net_mock(calls))
    assert len(calls) == 1, "w4 必须无视 w3 缓存,发起真抓取"
    assert rec.http_status == 200
    w4 = storage.REPO / "data" / "sources" / "w4" / sha1_url(url)[:12]
    assert (w4 / "meta.json").exists() and (w4 / "text.md").exists(), "结果必须落本周目录"


def test_fetch_source_w3_reads_own_week_dir():
    """week=3 命中自身目录(回退链首位即 w3,黄金锁/重跑不重抓)。"""
    url = "https://sameweek.example/a"
    _write_pair(3, url, text="w3 own")
    calls: list = []
    with patch("geo.fetch.url_guard._resolve_ips", return_value=_PUB):
        rec = fetch_source(url, 3, fetcher_kimi=False, transport=_net_mock(calls))
    assert calls == []
    assert rec.text == "w3 own"


# ---- analyst._load_l3_source: 回退链 + 成对才算 -------------------------------

def test_load_l3_source_legacy_fallback_w3():
    """w1 重算回退链: w1/ 缺 → w3/ 命中(黄金锁 43.4 的数据通路)。"""
    url = "https://legacy.example/page"
    _write_pair(3, url, text="legacy text")
    got = _load_l3_source(1, url)
    assert got is not None and got.text == "legacy text"
    assert _load_l3_source(3, url) is not None
    # w4 无回退: data/sources/w4/ 缺 → None(诚实缺失)
    assert _load_l3_source(4, url) is None


def test_load_l3_source_requires_both_files():
    """meta 在 text 缺(或反之)→ None,不成对不算。"""
    url = "https://halfpair.example/page"
    sha = sha1_url(url)
    sd = source_dir(1, sha)
    (sd / "meta.json").write_text(json.dumps(
        {"url": url, "sha1": sha, "http_status": 200, "text": "x",
         "structural": {}, "semantic": {}, "js_only": False,
         "fetched_iso": "2026-08-01T00:00:00Z"}), encoding="utf-8")
    assert _load_l3_source(1, url) is None


def test_load_l3_source_own_week_wins_over_w3():
    """本周目录优先于 w3 回退(重跑后本周新态覆盖历史态)。"""
    url = "https://prefer-own.example/page"
    _write_pair(3, url, text="w3 state")
    _write_pair(2, url, text="w2 state")
    got = _load_l3_source(2, url)
    assert got.text == "w2 state"


# ---- research 侧: sample 无回退 / corpus 走同一条链 ---------------------------

def test_sample_already_fetched_checks_own_week_only(tmp_path):
    from geo.research.sample import _already_fetched
    url = "https://sample-week.example/a"
    _write_pair(3, url)
    assert not _already_fetched(4, url, tmp_path), "w4 不吃 w3 的账(top-N 每周重抓)"
    assert _already_fetched(3, url, tmp_path)


def test_sample_already_fetched_uses_text_completeness_marker(tmp_path):
    """完成标志=text.md(评审修复): 新写序 meta 先落、text 后落,崩溃残留是孤儿 meta——
    只查 meta 会把孤儿误计为已抓、select_topn 将其排除,fetcher 永远没机会补齐成对。"""
    from geo.research.sample import _already_fetched
    url = "https://orphan-meta-sample.example/a"
    sha = sha1_url(url)
    sd = source_dir(TEST_WEEK, sha)   # mkdir 副作用;只写孤儿 meta,无 text.md
    (sd / "meta.json").write_text(json.dumps(
        {"url": url, "sha1": sha, "http_status": 200, "text": "partial",
         "structural": {}, "semantic": {}, "js_only": False,
         "fetched_iso": "2026-08-01T00:00:00Z"}), encoding="utf-8")
    assert not _already_fetched(TEST_WEEK, url, tmp_path), \
        "孤儿 meta 不得计为已抓——须留在 top-N 里让 fetcher 重抓补齐"
    (sd / "text.md").write_text("full", encoding="utf-8")
    assert _already_fetched(TEST_WEEK, url, tmp_path)


def test_corpus_l3_uses_week_chain():
    from geo.research.corpus import _load_l3
    url = "https://corpus-week.example/page"
    _write_pair(3, url, text="corpus via w3")
    assert (_load_l3(url, storage.REPO, 1) or _load_l3(url, storage.REPO, 3)) is not None
    assert _load_l3(url, storage.REPO, 1).text == "corpus via w3"
    assert _load_l3(url, storage.REPO, 4) is None, "w4 无回退,诚实缺失"
