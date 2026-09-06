from __future__ import annotations
import json, time, logging
from pathlib import Path
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession, Request
from geo.shared.config import settings, REPO
from geo.shared.storage import snapshot_dir
from geo.shared.io_utils import atomic_write_text
from urllib.parse import urlparse, quote

log = logging.getLogger("fetch.gsc")

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# 每个请求必须带显式超时——经代理的挂起端点会卡死 snapshot_node(原 httplib2
# 时代教训,transport 无关保留下来的不变量)。
GSC_TIMEOUT_S = 60.0

# Bug#3(w4): v2rayN 节点对 Google 出口分钟级双态振荡(TLS 1s↔35s),GSC 流程=
# token+query 两次独立 TLS,单次落坏窗口即 60s 超时——拉取段重试提命中率。
SNAPSHOT_ATTEMPTS = 3
SNAPSHOT_RETRY_BACKOFF_S = 15.0

# Bug#2(w4): .env 历史值 'geo-agent/gsc-*.json' 是仓库根相对——按 CWD 解析时
# 换个目录启动即 FileNotFoundError。回退链消灭该陷阱,三种历史用法全兼容。
def _resolve_gsc_key(v: str) -> Path:
    if not v:
        raise ValueError("GSC_KEY_FILE 未配置(.env 缺失或为空)")
    p = Path(v)
    if p.is_absolute():
        return p
    for cand in (p, REPO.parent / p, REPO / p):
        if cand.exists():
            return cand.resolve()
    raise ValueError(
        f"GSC 私钥未找到,已试: {p.resolve()}(CWD), {REPO.parent / p}(仓库根), {REPO / p}; "
        "请将 .env GSC_KEY_FILE 写绝对路径或把文件放到上述位置")

# 传输层持久修复(2026-09-06): httplib2 在代理下连接挂死(w4 实证,OS 层 Errno 60,
# 120s 超时也不救;httpx/requests 同代理秒通)——迁 AuthorizedSession 直连 REST。
# 关键: AuthorizedSession 默认给 token 刷新另建裸 session(只吃 HTTP(S)_PROXY 环境变量,
# 不继承主 session.proxies)——注入 auth_request 使 token 刷新也显式走代理,
# 任意代理切换只改 targets.yaml,零环境变量依赖。
def _gsc_session() -> AuthorizedSession:
    creds = service_account.Credentials.from_service_account_file(
        str(_resolve_gsc_key(settings.gsc_key_file)), scopes=SCOPES)
    proxies = ({"http": settings.proxy, "https": settings.proxy}
               if settings.proxy else None)
    auth_sess = requests.Session()
    if proxies:
        auth_sess.proxies = proxies
    sess = AuthorizedSession(creds, auth_request=Request(session=auth_sess))
    if proxies:
        sess.proxies = proxies
    return sess

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
    last_err: Exception | None = None
    for attempt in range(1, SNAPSHOT_ATTEMPTS + 1):
        try:
            sess = _gsc_session()
            body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
            url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
                   f"{quote(site, safe='')}/searchAnalytics/query")
            r = sess.post(url, json=body, timeout=GSC_TIMEOUT_S)
            r.raise_for_status()
            out["rows"] = r.json().get("rows", [])
            last_err = None
            break
        except Exception as e:
            last_err = e
            log.warning("w%s gsc 快照拉取第 %d/%d 次失败: %s",
                        week, attempt, SNAPSHOT_ATTEMPTS, e)
            if attempt < SNAPSHOT_ATTEMPTS:
                time.sleep(SNAPSHOT_RETRY_BACKOFF_S)
    if last_err is not None:
        out["degraded"] = True; out["error"] = f"{type(last_err).__name__}: {last_err}"
    atomic_write_text(out_path, json.dumps(out, ensure_ascii=False, indent=2))
    return out
