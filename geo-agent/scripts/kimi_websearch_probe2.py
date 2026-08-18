# 探针2：$web_search 的完整轮次行为 + 无工具原生联网能力对照（2026-08-18）
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openai import OpenAI
from geo.shared.config import settings

Q = "智谱 GLM 的网页搜索/检索爬虫 User-Agent 叫什么？给出来源 URL。"
c = OpenAI(api_key=settings.moonshot_api_key, base_url=settings.moonshot_base_url, timeout=180)
MSGS = [{"role": "system", "content": "联网搜索查证。回答先给结论，再列「来源：<url>」至少一个；查不到就如实说无法确认，禁止杜编 URL。"},
        {"role": "user", "content": Q}]

def show(tag, r):
    m = r.choices[0].message
    tc = [t.function.name for t in (getattr(m, "tool_calls", None) or [])]
    print(f"--- {tag} finish={r.choices[0].finish_reason} tool_calls={tc}")
    print((m.content or "(empty)")[:600])

# A) $web_search 单轮：看返回的是中间 tool_call 还是终答
show("A: builtin_function/$web_search 单轮", c.chat.completions.create(
    model="kimi-k3", temperature=1, messages=MSGS,
    tools=[{"type": "builtin_function", "function": {"name": "$web_search"}}]))

# B) $web_search 双轮：把 tool_call 回传（模拟服务端已执行的回合）——Moonshot 文档式用法
r1 = c.chat.completions.create(
    model="kimi-k3", temperature=1, messages=MSGS,
    tools=[{"type": "builtin_function", "function": {"name": "$web_search"}}])
m1 = r1.choices[0].message
if getattr(m1, "tool_calls", None):
    msgs2 = MSGS + [{"role": "assistant", "content": m1.content or "",
                     "tool_calls": [{"id": t.id, "type": "function",
                                     "function": {"name": t.function.name,
                                                  "arguments": t.function.arguments}}
                                    for t in m1.tool_calls]},
                    {"role": "tool", "tool_call_id": m1.tool_calls[0].id,
                     "content": "(builtin executed server-side)"}]
    try:
        show("B: 双轮回传", c.chat.completions.create(
            model="kimi-k3", temperature=1, messages=msgs2,
            tools=[{"type": "builtin_function", "function": {"name": "$web_search"}}]))
    except Exception as e:
        print(f"--- B: 双轮回传 FAIL {str(e)[:200]}")

# C) 无工具直问：kimi-k3 是否原生联网
show("C: 无工具直问", c.chat.completions.create(model="kimi-k3", temperature=1, messages=MSGS))
