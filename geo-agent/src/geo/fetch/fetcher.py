from __future__ import annotations
import time, httpx, trafilatura
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.models import L3Source
from geo.shared.storage import sha1_url, source_dir
from geo.fetch.meta_llm import extract_semantic
from geo.fetch.url_guard import UnsafeURLError, resolve_safe_ips, MAX_REDIRECTS

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

def _safe_get(url: str, transport=None) -> httpx.Response:
    """手动重定向循环: 每一跳先过 SSRF 防线、按已验 IP pin 连接,跳数封顶。

    不用 follow_redirects=True——那会让 httpx 自动跟进 Location,模型注入的
    内网跳转在防线外执行(2026-08-24 审查#3)。
    2026-08-25 二次审查#3: 防线解析出的公网 IP 直接作为连接目标(URL 主机改写
    为该 IP,Host 头/SNI 保留原主机)——校验与连接共用同一次 DNS 结果,关闭
    rebinding 窗口;走代理时发给代理的 CONNECT 目标同样是 IP,代理侧不再自行
    解析域名。transport 仅供测试注入。
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        ips = resolve_safe_ips(current)               # 每跳验证(含首跳)
        u = httpx.URL(current)
        pinned = str(ips[0])                          # 连接目标 = 已验证 IP
        req_url = u.copy_with(host=pinned)
        client_kwargs = {"timeout": 30.0, "follow_redirects": False}
        if transport is not None:
            client_kwargs["transport"] = transport
        elif settings.proxy:
            client_kwargs["proxy"] = settings.proxy
        req_kwargs: dict = {}
        if pinned != u.host:                          # Host/SNI 保留原主机
            orig_host = u.raw_host.decode("ascii")    # ASCII/punycode 形式
            default_port = 443 if u.scheme == "https" else 80
            if u.port and u.port != default_port:
                orig_host = f"{orig_host}:{u.port}"
            req_kwargs["headers"] = {"Host": orig_host}
            if u.scheme == "https":
                req_kwargs["extensions"] = {"sni_hostname": orig_host}
        with httpx.Client(**client_kwargs) as c:
            r = c.get(req_url, **req_kwargs)
        if r.is_redirect:
            loc = r.headers.get("location", "")
            current = str(u.join(loc))
            continue
        return r
    raise UnsafeURLError(f"重定向超过 {MAX_REDIRECTS} 跳: {url!r}")

def fetch_source(url: str, fetcher_kimi=True, transport=None) -> L3Source:
    sha = sha1_url(url); sd = source_dir(sha)
    text_path = sd/"text.md"; meta_path = sd/"meta.json"
    if text_path.exists():               # 跨周去重：已抓过直接读
        import json
        return L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
    t0 = time.time(); status = None; text = ""; js_only = False; structural = {}
    try:
        r = _safe_get(url, transport); status = r.status_code
        text = trafilatura.extract(r.text) or ""
        if not text.strip(): js_only = True
        structural = extract_structural(BeautifulSoup(r.text, "lxml"))
    except UnsafeURLError:
        # 安全拦截必须上抛且不落盘——落盘空文本会既污染缓存又掩盖攻击面
        raise
    except Exception:
        js_only = True
    semantic = extract_semantic(text) if (fetcher_kimi and text.strip()) else {}
    rec = L3Source(url=url, sha1=sha, http_status=status, text=text,
                   structural=structural, semantic=semantic, js_only=js_only,
                   fetched_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    text_path.write_text(text, encoding="utf-8")
    import json; meta_path.write_text(rec.model_dump_json(), encoding="utf-8")
    return rec
