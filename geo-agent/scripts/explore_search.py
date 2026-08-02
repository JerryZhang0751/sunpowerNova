#!/usr/bin/env python3
"""Explore whether the relay can web-search for models without native search
(豆包 / DeepSeek / GLM), and whether enable_search triggers RAG injection.
Detection: prompt_tokens inflation (RAG injection) + URL presence in content."""
import json, os, urllib.request, time

env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); env[k.strip()] = v.strip()
BASE = env["OPENAI_BASE_URL"].rstrip("/"); KEY = env["OPENAI_API_KEY"]

PROMPT = ("What are the official websites of 2 residential home solar battery "
          "brands sold in Europe? Give exact URLs and one sentence each.")

def call(model, mode):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.2, "stream": True}
    if mode == "enable_search": body["enable_search"] = True
    elif mode == "tools": body["tools"] = [{"type": "web_search"}]
    req = urllib.request.Request(f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time(); full = []; usage = None; extra_keys = []
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            buf = b""
            for raw in r:
                buf += raw
                # SSE: split on double newline
            for chunk in buf.decode(errors="replace").split("\n"):
                chunk = chunk.strip()
                if not chunk.startswith("data:"): continue
                payload = chunk[5:].strip()
                if payload == "[DONE]": continue
                try:
                    d = json.loads(payload)
                    if d.get("usage"): usage = d["usage"]
                    for k in d:
                        if k not in extra_keys and k not in ("choices","usage","id","model","object","created"): extra_keys.append(k)
                    delta = d.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta: full.append(delta)
                except Exception: pass
    except Exception as e:
        return f"ERR {repr(e)[:120]}"
    content = "".join(full)
    n_urls = content.count("http")
    pt = (usage or {}).get("prompt_tokens", "?")
    ct = (usage or {}).get("completion_tokens", "?")
    return f"prompt_tok={pt:>5} compl_tok={ct:>5} urls={n_urls} t={time.time()-t0:.0f}s extra={extra_keys}"

MODELS = [
    ("doubao-seed-2.1-pro", "豆包"),
    ("deepseek-v4-pro", "DeepSeek"),
    ("glm-5.2", "智谱GLM"),
]
for model, label in MODELS:
    print(f"\n### {label}  ({model})")
    for mode in ("none", "enable_search"):
        print(f"  [{mode:13}] {call(model, mode)}")
