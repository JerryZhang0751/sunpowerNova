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


# ---- 回归锁(2026-09-02 审核缺口 A3): MODELS 单一事实源 ----
def test_collector_model_defaults_match_registry():
    """A3-①: 三个 collector 的 model 默认值必须逐一等于 MODELS 注册表 api_code
    (默认值在 import 期固化,两边漂移即在此暴露)。"""
    import inspect
    from geo.shared.config import MODELS
    from geo.collect.qwen_client import collect_qwen
    from geo.collect.doubao_client import collect_doubao
    from geo.collect.zhipu_client import collect_zhipu
    for fn, key in ((collect_qwen, "qwen"), (collect_doubao, "doubao"),
                    (collect_zhipu, "zhipu")):
        params = inspect.signature(fn).parameters
        assert "model" in params, f"{fn.__name__} 缺 model 参数"
        assert params["model"].default == MODELS[key]["api_code"], \
            f"{fn.__name__} 的 model 默认值与 MODELS['{key}']['api_code'] 不一致"


def test_no_bare_api_code_literals_outside_registry():
    """A3-②: src/geo 全部 .py(注册表 shared/config.py 除外)不得出现裸 api_code
    字面量——新增/改名模型只能改 MODELS,漂移即红。"""
    import geo
    from pathlib import Path
    from geo.shared.config import MODELS
    root = Path(geo.__file__).parent
    literals = sorted({MODELS[k]["api_code"] for k in MODELS})
    assert len(literals) >= 4                       # 注册表本体健全(qwen/doubao/zhipu/kimi)
    offenders = []
    for p in sorted(root.rglob("*.py")):
        if p.relative_to(root).as_posix() == "shared/config.py":
            continue                                # 唯一事实源豁免
        text = p.read_text(encoding="utf-8")
        offenders += [f"{p.relative_to(root).as_posix()}: {lit}"
                      for lit in literals if lit in text]
    assert not offenders, f"api_code 字面量越出 MODELS 注册表: {offenders}"
