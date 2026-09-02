"""T2 (2026-09-02 backlog §3): MODELS 模型名单一事实源 + settings.run/targets mtime 缓存。"""
import os


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
