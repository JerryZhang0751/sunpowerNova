# tests/test_run_yaml_example.py
# backlog 2026-09-02 守卫补强: run.yaml.example 的 rule_version 曾滞后于 run.yaml
# (example 停在 geo-seo-v2,run.yaml 已到 v4)——升版时必须同步 example,本锁防复发。
import yaml
from geo.shared.config import REPO


def test_example_rule_version_matches_current():
    ex = yaml.safe_load((REPO / "run.yaml.example").read_text(encoding="utf-8"))
    cur = yaml.safe_load((REPO / "run.yaml").read_text(encoding="utf-8"))
    assert ex["rule_version"] == cur["rule_version"], \
        "run.yaml.example 版本滞后——升版时同步 example(防 v1 滞后复发)"
