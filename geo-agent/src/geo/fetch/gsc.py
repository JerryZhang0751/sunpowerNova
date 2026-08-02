from __future__ import annotations
import json, time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from geo.shared.config import settings, REPO
from geo.shared.storage import snapshot_dir
import httplib2

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

def _build_service():
    creds = service_account.Credentials.from_service_account_file(settings.gsc_key_file, scopes=SCOPES)
    http = httplib2.Http()
    if settings.proxy:
        proxy_info = httplib2.proxy_info_from_url(settings.proxy)
        http = httplib2.Http(proxy_info=proxy_info)
    http = creds.authorize(http)
    return build("searchconsole", "v1", http=http, cache_discovery=False)

def snapshot_gsc(week:int, rule_version:str, days=28) -> dict:
    site = settings.targets["site"]["url"]
    end = time.strftime("%Y-%m-%d", time.gmtime()); start = time.strftime("%Y-%m-%d", time.gmtime(time.time()-days*86400))
    out = {"week":week, "rule_version":rule_version, "site":site, "rows":[], "degraded":False}
    try:
        svc = _build_service()
        body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
        res = svc.searchanalytics().query(siteUrl=site, body=body).execute()
        out["rows"] = res.get("rows", [])
    except Exception as e:
        out["degraded"] = True; out["error"] = f"{type(e).__name__}: {e}"
    (snapshot_dir(week)/"gsc.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
