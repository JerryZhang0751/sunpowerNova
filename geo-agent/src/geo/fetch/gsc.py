from __future__ import annotations
import json, time, logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
from geo.shared.config import settings, REPO
from geo.shared.storage import snapshot_dir
from geo.shared.io_utils import atomic_write_text
import httplib2
from urllib.parse import urlparse

log = logging.getLogger("fetch.gsc")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# httplib2 has NO default timeout — without this a stalled Google endpoint
# (through the proxy) hangs snapshot_node forever (same incident class as the
# Kimi hang; every httpx call site in the repo sets 20-300s).
GSC_TIMEOUT_S = 60.0

def _build_service():
    creds = service_account.Credentials.from_service_account_file(settings.gsc_key_file, scopes=SCOPES)
    http = httplib2.Http(timeout=GSC_TIMEOUT_S)
    if settings.proxy:
        proxy_info = httplib2.proxy_info_from_url(settings.proxy)
        http = httplib2.Http(proxy_info=proxy_info, timeout=GSC_TIMEOUT_S)
    http = AuthorizedHttp(creds, http=http)   # google-auth 无 creds.authorize；用 AuthorizedHttp 包代理 httplib2
    return build("searchconsole", "v1", http=http, cache_discovery=False)

def _gsc_site_url() -> str:
    """Search Console 属性标识符：优先 config 的 gsc_site，否则按域名派生 sc-domain:<host>。"""
    site_cfg = settings.targets["site"]
    if site_cfg.get("gsc_site"):
        return site_cfg["gsc_site"]
    return f"sc-domain:{urlparse(site_cfg['url']).hostname}"

def snapshot_gsc(week:int, rule_version:str, days=28) -> dict:
    out_path = snapshot_dir(week)/"gsc.json"
    if out_path.exists():                       # 冻结守卫(2026-08-27 P1④)
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("w%s gsc 快照损坏,视为缺失重取", week); prev = None
        if prev is not None and not prev.get("degraded"):
            if prev.get("rule_version") != rule_version:
                log.warning("w%s gsc 快照已存在(规则版本 %s ≠ 请求 %s),按冻结语义跳过重取",
                            week, prev.get("rule_version"), rule_version)
            return prev                         # 干净快照=历史基线,不可被今日窗口重冻结
    site = _gsc_site_url()
    end = time.strftime("%Y-%m-%d", time.gmtime()); start = time.strftime("%Y-%m-%d", time.gmtime(time.time()-days*86400))
    out = {"week":week, "rule_version":rule_version, "site":site, "rows":[], "degraded":False}
    try:
        svc = _build_service()
        body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
        res = svc.searchanalytics().query(siteUrl=site, body=body).execute()
        out["rows"] = res.get("rows", [])
    except Exception as e:
        out["degraded"] = True; out["error"] = f"{type(e).__name__}: {e}"
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    return out
