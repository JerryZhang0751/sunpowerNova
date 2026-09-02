# tests/test_analyst_competitors.py
def test_competitors_get_empty_static_not_site_signals(monkeypatch):
    import geo.assess.analyst as A
    from geo.shared.models import L3Source
    calls = []
    monkeypatch.setattr(A, "competitor_domains_by_count", lambda w, n: ["example.com"])
    monkeypatch.setattr(A, "_load_l3_source",
                        lambda week, url: L3Source(url=url, sha1="s", text="t"))
    monkeypatch.setattr(A, "score_geo",
                        lambda src, brand, static, **kw: calls.append(static))
    A._score_competitors(1, {"robots_ai": {"GPTBot": True}, "https": True, "pages": [{"path": "/about"}]},
                         {})   # T13: 第三参=degraded_events 计数字典
    assert calls == [{}]        # 竞品不再借 SunHestia 静态信号(下界 proxy;v1.1 修正)
