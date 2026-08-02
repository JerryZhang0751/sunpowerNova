from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION

def test_load_full_and_core():
    full = load_prompts("full"); core = load_prompts("core")
    assert len(full) == 43 and len(core) == 15
    ids = {r.id for r in core}
    assert ids == {"C01","C04","C07","S02","S04","D01","D04","D07","K01","K03","M01","M03","B01","B02","G01"}

def test_version_stable_across_scope():
    assert PROMPT_SET_VERSION == PROMPT_SET_VERSION   # 模块级常量，全量 csv 指纹
