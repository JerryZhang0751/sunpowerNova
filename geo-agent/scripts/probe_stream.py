#!/usr/bin/env python3
"""Test whether stream=true sidesteps the relay's 60s total timeout
for heavy-reasoning models (qwen3.7-plus, doubao-seed-2.1-pro)."""
import json, os, urllib.request, urllib.error, time

env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); env[k.strip()] = v.strip()
BASE = env["OPENAI_BASE_URL"].rstrip("/"); KEY = env["OPENAI_API_KEY"]

PROMPT = "Name 2 European home solar battery brands with official websites. Be brief."
for MODEL in ("qwen3.7-plus", "doubao-seed-2.1-pro"):
    body = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.2, "stream": True, "enable_search": True}
    req = urllib.request.Request(f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    print(f"\n=== {MODEL}  stream=true ===")
    t0 = time.time(); got = 0; first = None; chunks = 0; full = []
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data:"): continue
                payload = line[5:].strip()
                if payload == "[DONE]": break
                chunks += 1
                if first is None: first = time.time() - t0
                try:
                    d = json.loads(payload)
                    delta = d.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta: full.append(delta)
                except Exception: pass
        print(f"first_token={first:.1f}s  total={time.time()-t0:.1f}s  chunks={chunks}  content_len={len(''.join(full))}")
        print("".join(full)[:400])
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} after {time.time()-t0:.1f}s: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"ERR after {time.time()-t0:.1f}s: {repr(e)[:200]}")
