#!/usr/bin/env python3
"""Verify whether turing/gemini-3.6-flash on the relay can do REAL native web
search, and characterize the shape of its citation URLs.

Background (see memory [[relay-no-native-search]]):
- 2026-07-26 the relay looked search-dead across ChatGPT / Gemini-3.5 / Qwen.
- 2026-08-02 re-test of the NEW model `turing/gemini-3.6-flash` found it DOES
  ground when called with `tools=[{type:"web_search"}]`, BUT its citation URLs
  are vertex-redirect (non-canonical): groundingChunks[].web.uri is a
  `vertexaisearch.cloud.google.com/grounding-api-redirect/<token>` link and the
  `title` field holds the source hostname. It also does not search every prompt.
  This script reproduces that finding.

Method:
  1. GET /models      -> confirm the model exists on the relay.
  2. H1 decisive test (ground truth = sunhestia.com homepage H1) under two
     triggers: plain vs tools=[{type:"web_search"}]. Only a live fetch returns
     the right H1.
  3. Dump groundingChunks[].web.{uri,title} to show the vertex-redirect shape,
     and flag zero-citation runs (no grounding metadata).

Credentials: read from env, falling back to geo-agent/.env, as
OPENAI_BASE_URL / OPENAI_API_KEY (the relay convention).
2026-09-02: the relay endpoint is RETIRED -- its URL is no longer committed in
this file. The endpoint comes from the RELAY_BASE_URL environment variable
(fallback is a placeholder); the API key is likewise supplied via env and is
never written into this file:
    RELAY_BASE_URL=https://<your-endpoint>/v1 OPENAI_API_KEY=<key> \
    python3 verify_gemini36.py
Keys are never hardcoded in this file.
"""
import json
import os
import re
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# Relay retired (2026-09-02): endpoint via env var; no real URL committed here.
DEFAULT_BASE = os.environ.get("RELAY_BASE_URL", "<RELAY_BASE_URL>")
MODEL = "turing/gemini-3.6-flash"
# sunhestia.com homepage H1 (site/src/pages/index.astro) -- only a live fetch knows it.
TRUTH = "your roof. your power. your storage."
H1_PROMPT = ("Open the website https://sunhestia.com/ and report the EXACT main H1 "
             "heading displayed on its homepage. Quote it verbatim. Use web search/browsing.")
NOISE_HOSTS = {"google.com", "www.google.com", "w3.org", "www.w3.org",
               "vertexaisearch.cloud.google.com", "schema.org", "www.schema.org",
               "gstatic.com", "www.gstatic.com"}


def load_env():
    env = {}
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY"):  # real env wins over .env
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def host(u):
    m = re.match(r"https?://([^/]+)", u or "")
    return m.group(1).lower() if m else ""


def as_obj(x):
    if isinstance(x, list):
        return x[0] if x else {}
    return x if isinstance(x, dict) else {}


def best_meta(bags):
    """Merge streamed metadata; per key keep the longest-JSON value (most complete)."""
    m = {}
    for b in bags:
        for k, v in b.items():
            s = json.dumps(v, ensure_ascii=False)
            if k not in m or len(s) > len(json.dumps(m[k], ensure_ascii=False)):
                m[k] = v
    return m


def stream_chat(base, key, label, extra):
    body = {"model": MODEL, "messages": [{"role": "user", "content": H1_PROMPT}],
            "temperature": 0.0, "stream": True, **extra}
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    print(f"\n===== {label} | extra={extra} =====")
    content, bags, usage = [], [], None
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            for raw in r:
                for line in raw.decode(errors="replace").split("\n"):
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    pay = line[5:].strip()
                    if pay == "[DONE]":
                        continue
                    try:
                        d = json.loads(pay)
                    except Exception:
                        continue
                    if d.get("usage"):
                        usage = d["usage"]
                    bag = {k: v for k, v in d.items()
                           if k not in ("choices", "usage", "id", "model", "object", "created")}
                    if bag:
                        bags.append(bag)
                    ch = (d.get("choices") or [{}])[0]
                    if ch.get("delta", {}).get("content"):
                        content.append(ch["delta"]["content"])
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        return
    except Exception as e:
        print(f"  ERR {repr(e)[:160]}")
        return
    txt = "".join(content)
    meta = best_meta(bags)
    gm = as_obj(meta.get("vertex_ai_grounding_metadata"))
    gc = gm.get("groundingChunks") if isinstance(gm, dict) else None
    hit = TRUTH in txt.lower()
    print(f"  H1 correct? {'YES (live fetch)' if hit else 'NO (no live search)'}")
    print(f"  prompt_tokens={(usage or {}).get('prompt_tokens')} "
          f"completion_tokens={(usage or {}).get('completion_tokens')} "
          f"(bare prompt~35; jump = grounding injection)")
    print(f"  grounding_metadata.keys: "
          f"{list(gm.keys()) if isinstance(gm, dict) and gm else 'NONE (zero-citation run)'}")
    if isinstance(gc, list) and gc:
        print(f"  groundingChunks (first 5) -- uri=vertex-redirect, title=source hostname:")
        for c in gc[:5]:
            w = c.get("web") if isinstance(c, dict) else {}
            print(f"     uri  = {w.get('uri')!r}")
            print(f"     title= {w.get('title')!r}")
    else:
        print("  groundingChunks: none")
    print(f"  reply[:240]: {txt[:240]!r}")


def main():
    env = load_env()
    base = env.get("OPENAI_BASE_URL", DEFAULT_BASE).rstrip("/")
    key = env.get("OPENAI_API_KEY")
    if not key:
        print("ERROR: set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) in env or geo-agent/.env")
        return

    print("########## STEP 1: GET /models ##########")
    try:
        req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        data = d.get("data") if isinstance(d, dict) else d
        ids = [m.get("id") if isinstance(m, dict) else str(m) for m in (data or [])]
        print(f"  models listed: {len(ids)} | TARGET {MODEL!r} present? {MODEL in ids}")
    except Exception as e:
        print(f"  /models ERR {repr(e)[:160]}")

    print("\n########## STEP 2: H1 decisive test (two triggers) ##########")
    stream_chat(base, key, "A: plain (auto-ground?)", {})
    stream_chat(base, key, "B: tools=[{type:web_search}]", {"tools": [{"type": "web_search"}]})


if __name__ == "__main__":
    main()
