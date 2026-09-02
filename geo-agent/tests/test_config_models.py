"""T2 (2026-09-02 backlog §3): MODELS 模型名单一事实源 + settings.run/targets mtime 缓存。"""
import os
from types import SimpleNamespace


def test_models_registry_values():
    from geo.shared.config import MODELS
    assert MODELS["qwen"]["api_code"] == "qwen3.7-plus"
    assert MODELS["doubao"]["api_code"] == "doubao-seed-2-1-pro-260628"
    assert MODELS["zhipu"]["api_code"] == "glm-5.2"
    assert MODELS["kimi"]["api_code"] == "kimi-k3"
    for v in MODELS.values():
        assert v["display"]


def test_settings_run_cached_until_mtime_changes(tmp_path):
    from geo.shared.config import Settings
    s = Settings(run_path=tmp_path / "run.yaml", targets_path=tmp_path / "t.yaml")
    (tmp_path / "run.yaml").write_text("week: 3\n", encoding="utf-8")
    (tmp_path / "t.yaml").write_text("site: {url: 'https://x.com'}\n", encoding="utf-8")
    a = s.run
    assert s.run is a                       # mtime 未变 → 同一对象(缓存)
    (tmp_path / "run.yaml").write_text("week: 4\n", encoding="utf-8")
    # mtime 粒度: 同秒内两次 write_text mtime 可能不变 → 显式拨后,保证失效路径被测到
    st = (tmp_path / "run.yaml").stat()
    os.utime(tmp_path / "run.yaml", (st.st_atime + 5, st.st_mtime + 5))
    assert s.run.week == 4                  # mtime 变 → 重新读盘


def test_settings_targets_cached_until_mtime_changes(tmp_path):
    from geo.shared.config import Settings
    s = Settings(run_path=tmp_path / "run.yaml", targets_path=tmp_path / "t.yaml")
    (tmp_path / "run.yaml").write_text("week: 3\n", encoding="utf-8")
    (tmp_path / "t.yaml").write_text("site: {url: 'https://a.com'}\n", encoding="utf-8")
    a = s.targets
    assert s.targets is a                   # mtime 未变 → 同一对象(缓存)
    (tmp_path / "t.yaml").write_text("site: {url: 'https://b.org/x'}\n", encoding="utf-8")
    st = (tmp_path / "t.yaml").stat()
    os.utime(tmp_path / "t.yaml", (st.st_atime + 5, st.st_mtime + 5))
    assert s.targets["site"]["url"] == "https://b.org/x"   # mtime 变 → 重新读盘


def test_run_cache_invalidates_on_same_mtime_tick_rewrite(tmp_path, monkeypatch):
    """同刻度重写窗口(review fix 1):文件系统把重写落在同一 mtime 刻度(秒级粒度)时,
    仅靠 st_mtime 判等的旧键会返回陈旧缓存;键升 (st_mtime_ns, st_size) 后仍失效。
    模拟:改写后 stat 谎报 st_mtime 恒为旧值(同刻),st_mtime_ns 传真实值。"""
    import pathlib
    import geo.shared.config as cfg
    run = tmp_path / "run.yaml"
    run.write_text("week: 3\nmode: audit\nscope: core\n", encoding="utf-8")
    (tmp_path / "t.yaml").write_text("site: {url: 'https://x.com'}\n", encoding="utf-8")
    s = cfg.Settings(run_path=run, targets_path=tmp_path / "t.yaml")
    assert s.run.week == 3
    stale_tick = run.stat().st_mtime        # 首版 mtime = "旧刻度"

    # 同 size 重写(week 3→4),ns 级 mtime 变化;再把 stat 谎报成旧刻度
    run.write_text("week: 4\nmode: audit\nscope: core\n", encoding="utf-8")
    real_stat = pathlib.Path.stat

    def fake_stat(self, *a, **kw):
        st = real_stat(self)
        return SimpleNamespace(st_mtime=stale_tick, st_mtime_ns=st.st_mtime_ns,
                               st_size=st.st_size)
    monkeypatch.setattr(pathlib.Path, "stat", fake_stat)

    assert s.run.week == 4                  # 旧键(仅 st_mtime)在此会命中缓存返回 3
