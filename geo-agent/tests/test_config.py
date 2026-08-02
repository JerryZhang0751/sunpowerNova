from textwrap import dedent
from pathlib import Path
import geo.shared.config as cfg

def test_settings_loads_env_and_yaml(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DASHSCOPE_API_KEY=k1\nARK_API_KEY=k2\nBIGMODEL_API_KEY=k3\n"
                   "MOONSHOT_API_KEY=k4\nGSC_KEY_FILE=/tmp/x.json\n")
    run = tmp_path / "run.yaml"; run.write_text("week: 1\nmode: audit\nscope: core\n")
    tgt = tmp_path / "targets.yaml"; tgt.write_text("site: {url: 'https://sunhestia.com', pages: ['/']}\n")
    s = cfg.Settings(_env_file=env, run_path=run, targets_path=tgt)
    assert s.dashscope_api_key == "k1"
    assert s.run.week == 1 and s.run.scope == "core"
    assert str(tgt.parent) in str(s.targets_path) or s.targets["site"]["url"].startswith("https://sunhestia")
