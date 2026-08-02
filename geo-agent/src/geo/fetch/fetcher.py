from __future__ import annotations
import time, httpx, trafilatura
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.models import L3Source
from geo.shared.storage import sha1_url, source_dir
from geo.fetch.meta_llm import extract_semantic

def extract_structural(soup: BeautifulSoup) -> dict:
    # On-page text signals the SEO scorer needs; captured at snapshot/fetch time
    # so the analyst can feed REAL title/meta_desc instead of fabricating them.
    canon_link = soup.find("link", rel="canonical")
    canon = canon_link.get("href") if canon_link else None
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = (desc_tag.get("content") or "").strip() if desc_tag else ""
    schemas = []
    for s in soup.find_all("script", type="application/ld+json"):
        import json
        try:
            j = json.loads(s.string or "{}")
            t = j.get("@type", "")
            schemas += [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
        except Exception: pass
    h_counts = {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1,7)}
    return {"canonical": canon, "title": title, "meta_desc": meta_desc,
            "schema_types": list(dict.fromkeys(schemas)),
            "h_counts": h_counts, "table_count": len(soup.find_all("table")),
            "ul_count": len(soup.find_all(["ul","ol"]))}

def fetch_source(url: str, fetcher_kimi=True) -> L3Source:
    sha = sha1_url(url); sd = source_dir(sha)
    text_path = sd/"text.md"; meta_path = sd/"meta.json"
    if text_path.exists():               # 跨周去重：已抓过直接读
        import json
        return L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
    t0 = time.time(); status = None; text = ""; js_only = False; structural = {}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, proxy=settings.proxy) as c:
            r = c.get(url); status = r.status_code
        text = trafilatura.extract(r.text) or ""
        if not text.strip(): js_only = True
        structural = extract_structural(BeautifulSoup(r.text, "lxml"))
    except Exception:
        js_only = True
    semantic = extract_semantic(text) if (fetcher_kimi and text.strip()) else {}
    rec = L3Source(url=url, sha1=sha, http_status=status, text=text,
                   structural=structural, semantic=semantic, js_only=js_only,
                   fetched_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    text_path.write_text(text, encoding="utf-8")
    import json; meta_path.write_text(rec.model_dump_json(), encoding="utf-8")
    return rec
