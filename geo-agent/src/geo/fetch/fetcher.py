from __future__ import annotations
import time, httpx, trafilatura
from bs4 import BeautifulSoup
from geo.shared.config import settings
from geo.shared.models import L3Source
from geo.shared.storage import sha1_url, source_dir
from geo.shared.io_utils import atomic_write_text
from geo.fetch.meta_llm import extract_semantic
from geo.fetch.url_guard import UnsafeURLError, resolve_safe_ips, MAX_REDIRECTS

class FetchError(RuntimeError):
    """传输失败或非 2xx 终态:不落缓存、上抛,下次运行自然重试(2026-08-27 P1②)。"""

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
    """手动重定向循环: 每一跳先过 SSRF 防线,跳数封顶。

    不用 follow_redirects=True——那会让 httpx 自动跟进 Location,模型注入的
    内网跳转在防线外执行(2026-08-24 审查#3)。
    2026-08-25 二次审查#3: 直连时以防线解析出的公网 IP 为连接目标(Host 头/SNI
    保留原主机),关闭"校验一次 DNS、连接再解析一次"的 rebinding 窗口。
    2026-08-28 w2 实跑修复: 代理路径不再 pin IP。裸 IP CONNECT 在两种真实环境
    下不可用——(a)域名分流代理(xray/Clash)按域名匹配路由规则,IP 目标绕过
    规则后外站被直连拒收;(b)本机 getaddrinfo IPv6 优先而网络 IPv6 出口不
    通,双栈域名全灭(w2 research top-40 抓取 40/40 失败、sample_n 崩至 4)。
    语义: 代理模式=每跳仍过 resolve_safe_ips 校验(内网/保留地址照拒),但发
    原始域名交代理按域名路由;残余风险=代理侧二次解析的 rebinding 窗口,对
    受信本地代理接受(直连模式无此让步)。直连=保留 pin,优先 IPv4,无 A 记
    录才用 IPv6。URL 形态只由 settings.proxy 决定;transport 仅供测试注入
    网络层,不改变该判定(密闭性:测试显式 patch proxy)。
    """
    use_proxy = bool(settings.proxy)
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        ips = resolve_safe_ips(current)               # 每跳验证(含首跳)
        u = httpx.URL(current)
        client_kwargs = {"timeout": 30.0, "follow_redirects": False}
        if transport is not None:
            client_kwargs["transport"] = transport
        elif settings.proxy:
            client_kwargs["proxy"] = settings.proxy
        req_kwargs: dict = {}
        if use_proxy:
            req_url = u                               # 域名交代理路由(见 docstring)
        else:
            pinned = str(next((ip for ip in ips if ip.version == 4), ips[0]))
            req_url = u.copy_with(host=pinned)        # 连接目标 = 已验证 IP(v4 优先)
            if pinned != u.host:                      # Host/SNI 保留原主机
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

def fetch_source(url: str, week: int, fetcher_kimi=True, transport=None) -> L3Source:
    sha = sha1_url(url); sd = source_dir(week, sha)
    text_path = sd/"text.md"; meta_path = sd/"meta.json"
    if text_path.exists() and meta_path.exists():   # 完整对才算命中(text=完整标志,2026-09-02 D1)
        import json
        try:
            cached = L3Source(**json.loads(meta_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            cached = None   # 坏 meta(残缺 JSON/schema 漂移;pydantic ValidationError⊂ValueError)
            # → 视为 miss 重抓覆写(评审修复:与 analyst/corpus 读路径容错对称;否则
            # 异常被 fetch_node/fetch_topn 吞掉,坏 meta 永不覆写=URL 该周永久 failed)
        if cached is not None and not (cached.js_only and cached.http_status is None):
            return cached   # 存量毒化条目(js_only+status None)同样视为 miss 重抓
    status = None; text = ""; js_only = False; structural = {}
    try:
        r = _safe_get(url, transport); status = r.status_code
        if not (200 <= status < 300):
            raise FetchError(f"HTTP {status}: {url}")
        text = trafilatura.extract(r.text) or ""
        if not text.strip(): js_only = True
        structural = extract_structural(BeautifulSoup(r.text, "lxml"))
    except (UnsafeURLError, FetchError):
        # UnsafeURLError=安全拦截、FetchError=传输/HTTP失败:均上抛且不落盘。
        # 落盘空文本会永久毒化缓存(2026-08-24 审查 P1-2)。
        raise
    except Exception as e:
        raise FetchError(f"{type(e).__name__}: {e} ({url})") from e
    semantic = extract_semantic(text) if (fetcher_kimi and text.strip()) else {}
    rec = L3Source(url=url, sha1=sha, http_status=status, text=text,
                   structural=structural, semantic=semantic, js_only=js_only,
                   fetched_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    # 写序反转(2026-09-02 D1): meta 先、text 后——崩溃残留只可能是"孤儿 meta"
    # (读路径要求成对,判 miss 重抓自愈),不再产生旧序的孤儿 text.md(旧读路径
    # 见 text 就读 meta → FileNotFoundError 被 research 吞成永久 failed 的路径
    # 由此消灭)。text 用原子写;meta 同。
    import json; atomic_write_text(meta_path, rec.model_dump_json())
    atomic_write_text(sd/"text.md", text)
    return rec
