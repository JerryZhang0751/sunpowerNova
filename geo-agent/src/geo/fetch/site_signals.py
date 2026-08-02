from __future__ import annotations
import json, httpx
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.storage import snapshot_dir
from geo.fetch.fetcher import extract_structural

def _robots_allows_ai(robots_txt: str) -> dict:
    def allows(bot):
        import re
        block = re.search(rf"User-agent:\s*{re.escape(bot)}\s*\n(.*?)(?:\nUser-agent:|\Z)", robots_txt, re.S|re.I)
        if not block: return True
        return "Disallow: /" not in block.group(1)
    return {b: allows(b) for b in ("GPTBot","ClaudeBot","PerplexityBot","Googlebot")}

def snapshot_static_signals(week:int, rule_version:str) -> dict:
    site = settings.targets["site"]["url"]; pages = settings.targets["site"]["pages"]
    out = {"week":week, "rule_version":rule_version, "site":site, "pages":[]}
    with httpx.Client(timeout=20.0, follow_redirects=True, proxy=settings.proxy) as c:
        try: robots = c.get(f"{site}/robots.txt").text
        except Exception: robots = ""
        try: sitemap = c.get(f"{site}/sitemap.xml").text
        except Exception: sitemap = ""
        out["robots_ai"] = _robots_allows_ai(robots)
        out["sitemap_present"] = bool(sitemap)

        # Parse sitemap URLs for inclusion checking
        sitemap_urls = []
        if sitemap:
            try:
                sitemap_soup = BeautifulSoup(sitemap, "xml")
                sitemap_urls = [loc.text for loc in sitemap_soup.find_all("loc")]
            except Exception:
                sitemap_urls = []
        for path in pages:
            url = site.rstrip("/") + path
            rec = {"url":url, "path":path, "https": url.startswith("https://")}
            try:
                r = c.get(url); rec["http_status"]=r.status_code
                soup = BeautifulSoup(r.text,"lxml")
                st = extract_structural(soup)
                rec.update(st)
                rec["has_viewport"] = bool(soup.find("meta", attrs={"name":"viewport"}))
                rec["in_sitemap"] = (url in sitemap_urls) if sitemap_urls else False
            except Exception as e:
                rec["http_status"]=None; rec["error"]=f"{type(e).__name__}: {e}"
            out["pages"].append(rec)
    (snapshot_dir(week)/"static_signals.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
