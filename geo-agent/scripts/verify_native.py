#!/usr/bin/env python3
"""Verify NATIVE web-search fidelity for ChatGPT / Gemini / Qwen via the relay.
Goal: confirm each uses the PLATFORM's own search (faithful to real users),
not litellm's own RAG injection and not parametric knowledge.

Signals:
  Gemini  -> vertex_ai_citation_metadata with real URLs = native Google grounding
  Qwen    -> enable_search injection + native search_results metadata = native DashScope
  ChatGPT -> /responses endpoint w/ web_search tool -> annotations[url_citation] = native OpenAI
"""
import json, os, urllib.request, urllib.error

env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); env[k.strip()] = v.strip()
BASE = env["OPENAI_BASE_URL"].rstrip("/"); KEY = env["OPENAI_API_KEY"]

PROMPT = ("What are the top residential solar battery brands in Europe in 2026, "
          "with their official website URLs? Use web search and cite sources.")

def extract_urls(obj, found):
    """Recursively collect http(s) URLs from any nested structure."""
    if isinstance(obj, str):
        import re
        for m in re.findall(r"https?://[^\s\"'<>)\]]+", obj):
            found.add(m.split("?")[0].rstrip(".,"))
    elif isinstance(obj, dict):
        for v in obj.values(): extract_urls(v, found)
    elif isinstance(obj, list):
        for v in obj: extract_urls(v, found)

def stream_chat(model, extra_body, label):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.2, "stream": True, **extra_body}
    req = urllib.request.Request(f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    print(f"\n========== {label}  ({model})  extra={extra_body} ==========")
    content = []; top_keys = set(); meta_payloads = {}; usage = None
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                for line in raw.decode(errors="replace").split("\n"):
                    line = line.strip()
                    if not line.startswith("data:"): continue
                    pay = line[5:].strip()
                    if pay == "[DONE]": continue
                    try: d = json.loads(pay)
                    except: continue
                    for k in d: top_keys.add(k)
                    if d.get("usage"): usage = d["usage"]
                    for k, v in d.items():
                        if k not in ("choices","usage","id","model","object","created"):
                            meta_payloads[k] = v
                    ch = (d.get("choices") or [{}])[0]
                    delta = ch.get("delta", {})
                    if delta.get("content"): content.append(delta["content"])
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:400]}"); return
    except Exception as e:
        print(f"  ERR: {repr(e)[:200]}"); return
    txt = "".join(content)
    urls_meta = set(); extract_urls(meta_payloads, urls_meta)
    urls_text = set(); extract_urls(txt, urls_text)
    print(f"  top_keys: {sorted(top_keys)}")
    print(f"  usage.prompt_tokens: {(usage or {}).get('prompt_tokens')}  (bare≈30; 大幅上涨=有注入)")
    print(f"  URLs in METADATA fields: {len(urls_meta)}  -> {sorted(urls_meta)[:5]}")
    print(f"  URLs in content text  : {len(urls_text)}")
    # dump the decisive metadata fields
    for k in ("vertex_ai_citation_metadata","vertex_ai_grounding_metadata","vertex_ai_url_context_metadata","search_results","annotations"):
        if k in meta_payloads:
            print(f"  [meta] {k}: {json.dumps(meta_payloads[k], ensure_ascii=False)[:500]}")
    print(f"  content[:200]: {txt[:200]!r}")

# --- Gemini (auto-grounding) ---
stream_chat("turing/gemini-3.5-flash", {}, "Gemini auto-ground")
# --- Qwen enable_search ---
stream_chat("qwen3.7-plus", {"enable_search": True}, "Qwen enable_search")

# --- ChatGPT via /responses + web_search tool (native OpenAI search) ---
print("\n========== ChatGPT via /responses + web_search tool ==========")
for m in ("turing/gpt-5.5", "gpt-5.5"):
    body = {"model": m, "input": [{"role": "user", "content": PROMPT}],
            "tools": [{"type": "web_search"}], "stream": False}
    req = urllib.request.Request(f"{BASE}/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
        urls = set(); extract_urls(d, urls)
        # find annotations
        ann = d.get("annotations") or []
        out = d.get("output", [])
        print(f"  model={m}: OK  top_keys={list(d.keys())}  annotations={len(ann)}  urls={len(urls)}")
        if ann: print(f"    annotations[:2]: {json.dumps(ann[:2], ensure_ascii=False)[:400]}")
        if urls: print(f"    urls: {sorted(urls)[:5]}")
        break
    except urllib.error.HTTPError as e:
        print(f"  model={m}: HTTP {e.code} {e.read().decode()[:200]}")
    except Exception as e:
        print(f"  model={m}: ERR {repr(e)[:150]}")
