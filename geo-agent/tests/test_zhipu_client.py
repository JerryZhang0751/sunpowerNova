import json
from pathlib import Path
from geo.collect.zhipu_client import parse_zhipu_response, strip_noise

FX = Path(__file__).parent / "fixtures/raw"

def load(pid):
    return json.loads((FX / f"zhipu_{pid}.json").read_text(encoding="utf-8"))

def test_strip_noise():
    assert strip_noise("a<GUIDContent>x</GUIDContent>b") == "ab"

def test_parse_zhipu():
    fx = load("C01")
    out = parse_zhipu_response(fx["response"])
    assert out["answer"].strip() and "<" not in out["answer"][:1]  # noise stripped
    assert out["search_results"] and all("url" in s for s in out["search_results"])
