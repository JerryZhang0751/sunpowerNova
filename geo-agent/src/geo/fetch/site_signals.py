from __future__ import annotations
import json, logging, httpx
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.storage import snapshot_dir
from geo.shared.io_utils import atomic_write_text
from geo.fetch.fetcher import extract_structural

log = logging.getLogger("fetch.site_signals")

def _parse_robots_groups(robots_txt: str) -> dict[str, list[tuple[str, str]]]:
    """按 User-agent 分组收集 (kind, path) 规则;组边界=下一个 User-agent 行(REP 惯例)。"""
    groups: dict[str, list[tuple[str, str]]] = {}
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    def flush():
        for a in agents:
            groups.setdefault(a, []).extend(rules)
    for line in robots_txt.splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        key, _, val = s.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent" and val:
            if rules:
                flush(); agents, rules = [val], []
            else:
                agents.append(val)          # 连续多 UA 行=同组
        elif key in ("disallow", "allow") and agents:
            rules.append((key, val))
    flush()
    return groups

def _group_allows(rules: list[tuple[str, str]]) -> bool:
    """站点根路径 "/" 的允许判定:仅计路径匹配根的规则(如 Disallow: /private 不匹配 "/" 不封根),
    最长路径规则优先,等长时 Disallow 胜;无任何匹配的规则 → True(该组未封禁根路径)。"""
    best_path, best_allow = "", None
    for kind, p in rules:
        if not p or not p.startswith("/"):
            continue
        if not "/".startswith(p):        # 规则路径不匹配被抓路径 "/" → 不影响根判定(非过度杀伤)
            continue
        if len(p) > len(best_path):
            best_path, best_allow = p, (kind == "allow")
        elif len(p) == len(best_path) and kind == "disallow":
            best_allow = False
    return True if best_allow is None else best_allow

def _robots_allows_ai(robots_txt: str) -> dict:
    groups = _parse_robots_groups(robots_txt)
    groups_lc = {k.lower(): v for k, v in groups.items()}   # REP:UA 名大小写不敏感(仅查询侧折叠)
    out = {}
    for b in ("GPTBot", "ClaudeBot", "PerplexityBot", "Googlebot"):
        rules = next((groups_lc[k] for k in (b.lower(), "*") if k in groups_lc), None)  # 专属组优先于 *
        out[b] = True if rules is None else _group_allows(rules)
    return out

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
    out_path = snapshot_dir(week)/"static_signals.json"
    if out_path.exists():                       # 干净才冻结(D2);旧格式无 degraded 键=falsy=冻结(黄金锁兼容)
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("w%s static_signals 快照损坏,视为缺失重取", week); prev = None
        if prev is not None and not prev.get("degraded"):
            log.info("w%s static_signals 快照已存在,跳过重取(冻结)", week)
            return prev
        if prev is not None:
            log.warning("w%s static_signals 快照 degraded,重取(robots 失败或 error 页)", week)
    site = settings.targets["site"]["url"]; pages = settings.targets["site"]["pages"]
    out = {"week":week, "rule_version":rule_version, "site":site, "pages":[]}
    robots_failed = False
    with httpx.Client(timeout=20.0, follow_redirects=True, proxy=settings.proxy) as c:
        try:
            r = c.get(f"{site}/robots.txt")
            # 5xx=服务器错误页(HTML body,httpx 不 raise)≠真实 robots → 拉取失败进 degraded;
            # 4xx(如 404)=REP 合法"无限制"→ 读 body(空/HTML 无组)→ 全允许,不算失败
            robots_failed = r.status_code >= 500
            robots = r.text
        except Exception:
            robots = None; robots_failed = True      # D3:未知≠允许,robots_ai=None→评分记 0
        out["robots_ai"] = None if robots_failed else _robots_allows_ai(robots)
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
    out["degraded"] = robots_failed or any(          # D2:degraded 快照可重取
        p.get("error") or p.get("http_status") != 200 for p in out["pages"])
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    return out
