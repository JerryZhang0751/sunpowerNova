#!/usr/bin/env python3
"""Decisive native-search probe: ask for LIVE content only a web fetch can return.
Known answer: sunhestia.com homepage H1 = 'Your roof. Your power. Your storage.'
Correct H1 => real live search/fetch happened (and our site is indexed by that backend).
Also checks metadata/usage to see WHICH mechanism fired."""
import json, os, urllib.request

env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); env[k.strip()]=v.strip()
BASE=env["OPENAI_BASE_URL"].rstrip("/"); KEY=env["OPENAI_API_KEY"]
TRUTH="your roof. your power. your storage"

PROMPT=("Open the website https://sunhestia.com/ and report the EXACT main H1 heading "
        "displayed on its homepage. Quote it verbatim. Use web search/browsing.")

def run(model, extra, label):
    body={"model":model,"messages":[{"role":"user","content":PROMPT}],
          "temperature":0.0,"stream":True,**extra}
    req=urllib.request.Request(f"{BASE}/chat/completions",data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    print(f"\n===== {label} | {model} | extra={extra} =====")
    content=[]; top=set(); meta={}; usage=None
    try:
        with urllib.request.urlopen(req,timeout=180) as r:
            for raw in r:
                for line in raw.decode(errors="replace").split("\n"):
                    line=line.strip()
                    if not line.startswith("data:"): continue
                    pay=line[5:].strip()
                    if pay=="[DONE]": continue
                    try: d=json.loads(pay)
                    except: continue
                    for k in d: top.add(k)
                    if d.get("usage"): usage=d["usage"]
                    for k,v in d.items():
                        if k not in ("choices","usage","id","model","object","created"): meta[k]=v
                    ch=(d.get("choices") or [{}])[0]; dl=ch.get("delta",{})
                    if dl.get("content"): content.append(dl["content"])
    except Exception as e:
        print(f"  ERR {repr(e)[:160]}"); return
    txt="".join(content); hit = TRUTH in txt.lower()
    print(f"  H1 correct? {'✅ YES (live fetch happened)' if hit else '❌ NO (no live search / not indexed)'}")
    print(f"  prompt_tokens={(usage or {}).get('prompt_tokens')} (bare≈35; 暴涨=注入)")
    for k in ("vertex_ai_citation_metadata","vertex_ai_grounding_metadata","search_results","annotations"):
        if k in meta:
            s=json.dumps(meta[k],ensure_ascii=False)
            print(f"  [meta] {k} (len={len(s)}): {s[:300]}")
    print(f"  reply[:280]: {txt[:280]!r}")

run("turing/gemini-3.5-flash", {}, "Gemini auto-ground")
run("qwen3.5-flash", {"enable_search": True}, "Qwen3.5-flash +enable_search")
run("qwen3.7-plus", {"enable_search": True}, "Qwen3.7-plus +enable_search")
run("turing/gpt-5.5", {}, "ChatGPT (chat, no param)")
