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

def _fetch_sitemap_urls(c, site: str) -> tuple[bool, list[str]]:
    """抓取 sitemap 并返回 (present, page_urls)。

    依次试 sitemap-index.xml(Astro/标准 sitemapindex)与 sitemap.xml。只有当响应
    解析出 <sitemap>(index)或 <url>(urlset)时才算“sitemap 存在”——404 的 HTML 页或
    空响应不算（旧实现 bool(text) 会把 404 HTML 误判为存在、把 SSL 异常误判为缺失）。
    遇到 index 则跟随各子 sitemap 收集页面 <loc>。
    """
    page_urls: list[str] = []
    for name in ("sitemap-index.xml", "sitemap.xml"):
        try:
            r = c.get(f"{site}/{name}")
        except Exception:
            continue
        if r.status_code != 200 or not r.text:
            continue
        try:
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            continue
        if soup.find("sitemap"):                       # sitemapindex → 跟随子 sitemap
            for idx_loc in soup.find_all("loc"):
                child = (idx_loc.text or "").strip()
                if not child.endswith(".xml"):
                    continue
                try:
                    cr = c.get(child)
                except Exception:
                    continue
                if cr.status_code != 200:
                    continue
                try:
                    csoup = BeautifulSoup(cr.text, "xml")
                    page_urls += [p_loc.text.strip() for p_loc in csoup.find_all("loc")]
                except Exception:
                    pass
            return True, page_urls
        if soup.find("url"):                            # urlset → 直接取页面 loc
            return True, [loc.text.strip() for loc in soup.find_all("loc")]
        # 既非 index 也非 urlset（如 404 HTML 页）→ 不是 sitemap，继续下一个候选
    return False, page_urls


def snapshot_static_signals(week:int, rule_version:str) -> dict:
    site = settings.targets["site"]["url"]; pages = settings.targets["site"]["pages"]
    out = {"week":week, "rule_version":rule_version, "site":site, "pages":[]}
    with httpx.Client(timeout=20.0, follow_redirects=True, proxy=settings.proxy) as c:
        try: robots = c.get(f"{site}/robots.txt").text
        except Exception: robots = ""
        out["robots_ai"] = _robots_allows_ai(robots)
        # sitemap：sitemap-index.xml(Astro/标准)→回退 sitemap.xml；按 <sitemap>/<url> 判真并跟随 index
        sitemap_present, sitemap_urls = _fetch_sitemap_urls(c, site)
        out["sitemap_present"] = sitemap_present
        norm_sitemap_urls = {u.rstrip("/") for u in sitemap_urls if u}
        for path in pages:
            url = site.rstrip("/") + path
            rec = {"url":url, "path":path, "https": url.startswith("https://")}
            try:
                r = c.get(url); rec["http_status"]=r.status_code
                soup = BeautifulSoup(r.text,"lxml")
                st = extract_structural(soup)
                rec.update(st)
                rec["has_viewport"] = bool(soup.find("meta", attrs={"name":"viewport"}))
                rec["in_sitemap"] = (url.rstrip("/") in norm_sitemap_urls) if norm_sitemap_urls else False
            except Exception as e:
                rec["http_status"]=None; rec["error"]=f"{type(e).__name__}: {e}"
            out["pages"].append(rec)
    (snapshot_dir(week)/"static_signals.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
