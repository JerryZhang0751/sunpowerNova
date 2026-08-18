# 探针：Moonshot kimi-k3 联网搜索工具 schema 实测（2026-08-18）
# 背景：research/kimi.py 的 builtin_tools 被 400 拒（"only function and plugin are supported"）
# 候选：① builtin_function/$web_search（Moonshot 文档经典格式）② plugin 式 ③ 无 tools 让模型自带联网
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openai import OpenAI
from geo.shared.config import settings

Q = "智谱 GLM 的网页搜索爬虫 User-Agent 叫什么？给出处 URL。"

CANDIDATES = {
    "builtin_function_$web_search":
        [{"type": "builtin_function", "function": {"name": "$web_search"}}],
    "builtin_function_web_search":
        [{"type": "builtin_function", "function": {"name": "web_search"}}],
    "plugin_web_search":
        [{"type": "plugin", "plugins": [{"type": "web_search"}]}],
}

def probe(name, tools=None, extra=None):
    c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=180)
    kw = dict(model="kimi-k3", temperature=1,
              messages=[{"role": "system", "content": "联网搜索查证。回答先给结论再列来源 URL，查不到就说无法确认，禁止杜撰。"},
                        {"role": "user", "content": Q}])
    if tools: kw["tools"] = tools
    if extra: kw.update(extra)
    try:
        r = c.chat.completions.create(**kw)
        msg = r.choices[0].message
        text = (msg.content or "")[:200].replace("\n", " ")
        # 工具调用痕迹（builtin function 的调用记录在 choices/tool_calls）
        tc = [t.function.name for t in (getattr(msg, "tool_calls", None) or [])]
        print(f"[OK]   {name}: tool_calls={tc} | {text}")
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)[:160]}")

if __name__ == "__main__":
    for name, tools in CANDIDATES.items():
        probe(name, tools)
