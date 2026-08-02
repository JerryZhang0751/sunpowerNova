#!/usr/bin/env python3
"""Final test: does tools=[{type:web_search}] trigger search for 豆包/GLM?
Look for tool_calls, finish_reason=tool_calls, prompt_tok inflation."""
import json, os, urllib.request, time

env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); env[k.strip()] = v.strip()
BASE = env["OPENAI_BASE_URL"].rstrip("/"); KEY = env["OPENAI_API_KEY"]

PROMPT = ("What are the official websites of 2 European home solar battery brands? "
          "Search the web and cite exact URLs.")

def call(model):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.2, "stream": True,
            "tools": [{"type": "web_search"}]}
    req = urllib.request.Request(f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time(); full = []; usage = None; finish = []; toolcalls = []
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                for chunk in raw.decode(errors="replace").split("\n"):
                    chunk = chunk.strip()
                    if not chunk.startswith("data:"): continue
                    payload = chunk[5:].strip()
                    if payload == "[DONE]": continue
                    try:
                        d = json.loads(payload)
                        if d.get("usage"): usage = d["usage"]
                        ch = (d.get("choices") or [{}])[0]
                        if ch.get("finish_reason"): finish.append(ch["finish_reason"])
                        delta = ch.get("delta", {})
                        if delta.get("content"): full.append(delta["content"])
                        if delta.get("tool_calls"): toolcalls.append(delta["tool_calls"])
                    except Exception: pass
    except Exception as e:
        return f"ERR {repr(e)[:150]}"
    content = "".join(full)
    pt = (usage or {}).get("prompt_tokens", "?")
    return (f"prompt_tok={pt} finish={finish} tool_call_frags={len(toolcalls)} "
            f"urls={content.count('http')} t={time.time()-t0:.0f}s\n    content[:300]={content[:300]!r}")

for model, label in [("doubao-seed-2.1-pro", "豆包"), ("glm-5.2", "智谱GLM")]:
    print(f"\n### {label} ({model})  tools=[web_search]")
    print("  " + call(model))
