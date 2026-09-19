from textwrap import dedent
from pathlib import Path
import yaml
import geo.shared.config as cfg
from geo.shared.config import RunSpec, REPO

def test_settings_loads_env_and_yaml(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DASHSCOPE_API_KEY=k1\nARK_API_KEY=k2\nBIGMODEL_API_KEY=k3\n"
                   "MOONSHOT_API_KEY=k4\nGSC_KEY_FILE=/tmp/x.json\n")
    run = tmp_path / "run.yaml"; run.write_text("mode: audit\nscope: core\nruns: 2\n")
    tgt = tmp_path / "targets.yaml"; tgt.write_text("site: {url: 'https://sunhestia.com', pages: ['/']}\n")
    s = cfg.Settings(_env_file=env, run_path=run, targets_path=tgt)
    assert s.dashscope_api_key == "k1"
    assert s.run.runs == 2 and s.run.scope == "core"
    assert str(tgt.parent) in str(s.targets_path) or s.targets["site"]["url"].startswith("https://sunhestia")


def test_run_yaml_keys_match_run_spec_fields():
    """run.yaml 与 RunSpec 字段集一致——多余键=死配置,缺失键=靠默认值漂移,都该显式。"""
    data = yaml.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
    assert set(data.keys()) == set(RunSpec.model_fields.keys()), \
        f"run.yaml keys={sorted(data)} vs RunSpec fields={sorted(RunSpec.model_fields)}"
