import re

from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION

def test_load_full_and_core():
    full = load_prompts("full"); core = load_prompts("core")
    assert len(full) == 43 and len(core) == 15
    ids = {r.id for r in core}
    assert ids == {"C01","C04","C07","S02","S04","D01","D04","D07","K01","K03","M01","M03","B01","B02","G01"}

def test_prompt_set_version_format():
    # T5(2026-09-02): 原 `PROMPT_SET_VERSION == PROMPT_SET_VERSION` 恒真假绿;
    # 改为真判别——版本号必须是 prompt blob 的 sha1[:12] 十六进制指纹。
    assert re.fullmatch(r"[0-9a-f]{12}", PROMPT_SET_VERSION), \
        "prompt_set_version 应为 prompt blob 的 sha1[:12] 十六进制"
