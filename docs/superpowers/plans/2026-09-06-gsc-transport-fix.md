# GSC 传输层持久修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 gsc.py 的 GSC 传输层从 httplib2（代理下挂死，w4 实证）迁到 AuthorizedSession 直连 REST，token 刷新与查询都显式走 targets.yaml 代理——任意代理切换不再复现。

**Architecture:** 单文件改造（`gsc.py`）：删 `_build_service`（httplib2+googleapiclient+google_auth_httplib2），新增 `_gsc_session()`（requests+google-auth，注入带代理的 `auth_request` 消灭环境变量依赖），`snapshot_gsc` 拉取段直连 REST 端点。快照 schema/冻结守卫/重试循环零改动。合并门 = TEST_WEEK 真跑探针（真实代理+真实 API）。

**Tech Stack:** Python 3.12, requests 2.34.2 + google-auth 2.56.3（均在 requirements.lock）, pytest。

## Global Constraints

- **零改动**：快照 JSON 键集、冻结守卫（clean 冻结/degraded 重取）、degraded 语义、拉取段重试循环（`SNAPSHOT_ATTEMPTS=3`/`SNAPSHOT_RETRY_BACKOFF_S=15.0`）、`_resolve_gsc_key` 回退链、`GSC_TIMEOUT_S=60.0` 值、`_gsc_site_url`、评分语义、w1-w4 冻结产物（`geo-agent/data/` 历周）。
- 测试只增不减：基线 **577 / 0 failures / 2 skipped**，完成后 ≥578；黄金锁 `tests/test_v1_semantics.py` 2 passed 零漂移。
- 测试环境：`cd geo-agent && PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest ... -p no:cacheprovider --timeout=120`；EXIT=0 为准，计数用 `--junitxml` 解析。**不碰 `/tmp/pylibs312`**（已废弃，用 `$HOME/pylibs312`）。
- 新测试不依赖网络；真跑探针只写 TEST_WEEK(901) 目录且验后清理，不碰生产周。
- 分支 `gsc-transport-fix` 自 main=`2077949`；commit 显式路径、禁 `git add -A`、尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

---

### Task 1: 传输层改造 + 测试改写/新增（TDD）

**Files:**
- Modify: `geo-agent/src/geo/fetch/gsc.py`（imports 4 处、`GSC_TIMEOUT_S` 注释、删 `_build_service` 增 `_gsc_session`、`snapshot_gsc` 拉取段）
- Test: `geo-agent/tests/test_gsc.py`（import 行、6 用例改写、1 用例改名、1 用例新增）

**Interfaces:**
- Produces: `_gsc_session() -> google.auth.transport.requests.AuthorizedSession`（模块私有；凭据来自 `_resolve_gsc_key(settings.gsc_key_file)`；`settings.proxy` 非空时主 session 与 `auth_request` 注入 session 的 `.proxies` 均为 `{"http": settings.proxy, "https": settings.proxy}`，为空时两处均不设）。
- Consumes: 既有 `_resolve_gsc_key(v: str) -> Path`、`settings.gsc_key_file`/`settings.proxy`、`SCOPES`、`GSC_TIMEOUT_S`、`SNAPSHOT_ATTEMPTS`/`SNAPSHOT_RETRY_BACKOFF_S`。

- [ ] **Step 1: 改写/新增测试（先红）**

`tests/test_gsc.py` 顶部 import 区改为：

```python
import logging
import requests
from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path
from geo.fetch.gsc import snapshot_gsc, _gsc_session, _resolve_gsc_key, GSC_TIMEOUT_S
from geo.shared.config import settings
from geo.shared.weeks import TEST_WEEK
```

（`_build_service` 移出 import；新增 `_gsc_session`、`GSC_TIMEOUT_S`、`requests`。）

用例改写（意图全部保留，patch 对象/断言换新传输）：

```python
def _resp(json_data=None, status=200):
    m = MagicMock()
    m.status_code = status
    if status >= 400:
        m.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    m.json.return_value = json_data or {}
    return m

def test_gsc_degrades_on_auth_error(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    with patch("geo.fetch.gsc._gsc_session", return_value=MagicMock(
            post=MagicMock(return_value=_resp(status=403)))):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True and out["rows"] == []

def test_gsc_http_sets_timeout(iso_snapshots, monkeypatch):
    """每个 GSC 请求必须带显式超时——否则经代理的挂起会卡死 snapshot_node
    (原 httplib2 教训,transport 无关地保下来)。"""
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": []})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert sess.post.call_args.kwargs.get("timeout") == GSC_TIMEOUT_S

def test_gsc_happy(iso_snapshots):
    sess = MagicMock()
    sess.post.return_value = _resp({"rows": [{"keys": ["solar battery"], "clicks": 3,
                                              "impressions": 50, "ctr": 0.06, "position": 4.2}]})
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["rows"][0]["keys"] == ["solar battery"] and out["degraded"] is False

def test_gsc_proxy_applied_when_set():
    """settings.proxy 非空 → 主 session 与 token 刷新 session 两处 proxies 都设置;
    为空 → 两处都不设。(原 httplib2 proxy_info 断言的 transport 无关化)"""
    with patch("geo.fetch.gsc.settings") as mock_settings, \
         patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
         patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
        mock_settings.proxy = "http://127.0.0.1:10808"
        mock_settings.gsc_key_file = "/tmp/fake-key.json"
        sess = _gsc_session()
    want = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}
    assert dict(sess.proxies) == want
    assert dict(sess._auth_request.session.proxies) == want   # token 刷新走代理
    with patch("geo.fetch.gsc.settings") as mock_settings, \
         patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
         patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
        mock_settings.proxy = None
        mock_settings.gsc_key_file = "/tmp/fake-key.json"
        sess = _gsc_session()
    assert not sess.proxies and not sess._auth_request.session.proxies

def test_gsc_retry_succeeds_third_attempt(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.side_effect = [TimeoutError("timed out"), TimeoutError("timed out"),
                             _resp({"rows": [{"keys": ["solar battery"], "clicks": 3,
                                              "impressions": 50, "ctr": 0.06, "position": 4.2}]})]
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is False and len(out["rows"]) == 1

def test_gsc_retry_exhausted_degrades(iso_snapshots, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sess = MagicMock()
    sess.post.side_effect = TimeoutError("timed out")
    with patch("geo.fetch.gsc._gsc_session", return_value=sess):
        out = snapshot_gsc(week=TEST_WEEK, rule_version="t")
    assert out["degraded"] is True and "TimeoutError" in out["error"]
    assert sess.post.call_count == 3
```

`test_build_service_resolves_relative_key` **改名**为 `test_gsc_session_resolves_relative_key` 并改写（原意图=`_build_service` 用回退链解析 key，移植到 `_gsc_session`；这是 spec §4 表遗漏的第 6 个改写用例，plan 补上）：

```python
def test_gsc_session_resolves_relative_key(tmp_path):
    root = tmp_path / "proj"; geo_dir = root / "geo-agent"; geo_dir.mkdir(parents=True)
    (geo_dir / "gsc-rel.json").write_text("{}", encoding="utf-8")
    from unittest.mock import patch as _patch
    with _patch("geo.fetch.gsc.REPO", geo_dir):
        with _patch("geo.fetch.gsc.settings") as mock_settings:
            mock_settings.proxy = None
            mock_settings.gsc_key_file = "geo-agent/gsc-rel.json"
            with _patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file") as mc:
                _gsc_session()
    mc.assert_called_once()
    assert Path(mc.call_args.args[0]) == geo_dir / "gsc-rel.json"
```

新增防复发回归锁（spec §4）：

```python
# ---- 传输层持久修复(2026-09-06): token 刷新显式走代理,零环境变量依赖 ----------

def test_gsc_session_token_refresh_proxied():
    """AuthorizedSession 默认给 token 刷新另建裸 session(只吃 HTTP(S)_PROXY 环境变量,
    不继承主 session.proxies)——w4 事故根因之一。本锁断言注入路径使两处都显式走代理。"""
    from google.auth.transport.requests import AuthorizedSession
    for proxy in ("http://127.0.0.1:10808", None):
        with patch("geo.fetch.gsc.settings") as mock_settings, \
             patch("geo.fetch.gsc._resolve_gsc_key", return_value=Path("/tmp/fake-key.json")), \
             patch("geo.fetch.gsc.service_account.Credentials.from_service_account_file"):
            mock_settings.proxy = proxy
            mock_settings.gsc_key_file = "/tmp/fake-key.json"
            sess = _gsc_session()
        assert isinstance(sess, AuthorizedSession)
        if proxy:
            want = {"http": proxy, "https": proxy}
            assert dict(sess.proxies) == want
            assert dict(sess._auth_request.session.proxies) == want
        else:
            assert not sess.proxies and not sess._auth_request.session.proxies
```

注意：`test_gsc_proxy_applied_when_set` 与 `test_gsc_session_token_refresh_proxied` 覆盖面有重叠——前者锁「proxies 正确设置」，后者锁「AuthorizedSession 注入结构 + 两态」；均保留（spec 各列各的）。

- [ ] **Step 2: 跑测试验证红**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest tests/test_gsc.py -p no:cacheprovider --timeout=120 -q`
Expected: **collection error**（`ImportError: cannot import name '_gsc_session'`）——旧 gsc.py 无该符号，RED 成立（其余未改写用例随 collection 不可见，属预期）。

- [ ] **Step 3: 实现 gsc.py 传输层**

imports 区（现 1-10 行）改为：

```python
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
```

（删 `googleapiclient.discovery`/`google_auth_httplib2`/`import httplib2` 三行。）

`GSC_TIMEOUT_S` 注释改写（值不动）：

```python
# 每个请求必须带显式超时——经代理的挂起端点会卡死 snapshot_node(原 httplib2
# 时代教训,transport 无关保留下来的不变量)。
GSC_TIMEOUT_S = 60.0
```

删整个 `_build_service()`，原位新增：

```python
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
```

`snapshot_gsc` 重试循环内的三行：

```python
            svc = _build_service()
            body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
            res = svc.searchanalytics().query(siteUrl=site, body=body).execute()
            out["rows"] = res.get("rows", [])
```

替换为：

```python
            sess = _gsc_session()
            body = {"startDate":start, "endDate":end, "dimensions":["query"], "rowLimit":1000}
            url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
                   f"{quote(site, safe='')}/searchAnalytics/query")
            r = sess.post(url, json=body, timeout=GSC_TIMEOUT_S)
            r.raise_for_status()
            out["rows"] = r.json().get("rows", [])
```

（`last_err`/`break`/`sleep`/写盘/冻结守卫全部不动。）

- [ ] **Step 4: 跑测试验证绿**

Run: `cd geo-agent && PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest tests/test_gsc.py -p no:cacheprovider --timeout=120 -q`
Expected: 全 PASS（含 7 个 `_resolve_gsc_key` 用例与 4 个冻结守卫用例——未触碰，应原样绿）。

- [ ] **Step 5: 全量 + 黄金锁 + 提交**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent" && PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest tests/test_v1_semantics.py -p no:cacheprovider -q && PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest tests/ -p no:cacheprovider --timeout=120 -o junit_family=xunit2 --junitxml=/tmp/junit_gsc.json -q > /dev/null 2>&1; echo EXIT=$?
python3.12 -c "import xml.etree.ElementTree as ET; s=ET.parse('/tmp/junit_gsc.json').getroot(); s=s if s.tag=='testsuite' else s.find('.//testsuite'); print(s.get('tests'), s.get('failures'), s.get('skipped'))"
cd .. && git status --porcelain
git add geo-agent/src/geo/fetch/gsc.py geo-agent/tests/test_gsc.py && git commit -m "fix(fetch): GSC 传输层迁 AuthorizedSession 直连 REST —— token 刷新显式走代理消灭 httplib2 代理挂死与 env 依赖(w4 Bug#3 持久修复)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

Expected: 黄金锁 2 passed；EXIT=0；计数 **578 / 0 / 2**（577+1 新增，7 改写保留/1 改名不增减总数）；`git status` 提交后干净。

---

### Task 2: TEST_WEEK 真跑探针（合并门，需代理 10808 在场）

**Files:** 无代码文件（真实验证 + 清理）。

**Interfaces:** Consumes Task 1 的 `snapshot_gsc`（经真实 `_gsc_session`→真实代理→真实 GSC API）。

- [ ] **Step 1: 代理在场检查**

Run: `nc -z 127.0.0.1 10808 && echo PROXY_UP`
Expected: PROXY_UP（不在场则本任务挂起等代理，不得跳过真跑直接合并）。

- [ ] **Step 2: 真跑探针**

```bash
cd "/Users/jerry/AiProject/sunpower nova/geo-agent" && PYTHONPATH="$HOME/pylibs312:src" python3.12 -c "
from geo.fetch.gsc import snapshot_gsc
from geo.shared.weeks import TEST_WEEK
snap = snapshot_gsc(TEST_WEEK, 'geo-seo-v5')
assert not snap.get('degraded') and snap.get('rows'), snap
print('LIVE OK rows=', len(snap['rows']))"
```

Expected: `LIVE OK rows= N`（N≈5-15，真实查询数据）。失败处置：**不合并**，记录输出（错误串/耗时）到报告，回设计排查（重点：token 刷新路径显式 proxies 与环境变量方式的行为差异）。

- [ ] **Step 3: 清理测试带目录**

```bash
rm -rf "/Users/jerry/AiProject/sunpower nova/geo-agent/data/snapshots/w901" && echo CLEANED
```

Expected: CLEANED（TEST_WEEK 目录验后即弃）。

---

### Task 3: 终局收口 — 评审 + 合并推送

**Files:** 无新文件。

- [ ] **Step 1: 终局评审**

对全分支 diff（`git diff main...gsc-transport-fix`，基准 main=`2077949`）做代码评审，逐条核对 spec §2 硬边界（快照键集/冻结守卫/重试循环/`_resolve_gsc_key`/`GSC_TIMEOUT_S` 值零改动；测试只增不减；无 git add -A）。MUST-FIX 则修复并重跑 Task 1 Step 5。

- [ ] **Step 2: 合并推送 + CI**

```bash
cd "/Users/jerry/AiProject/sunpower nova" && git checkout main && git merge --no-ff gsc-transport-fix -m "merge: GSC 传输层持久修复 —— AuthorizedSession 直连 REST,token 刷新显式走代理,代理切换零 env 依赖; 578tests, 黄金锁零漂移

Co-Authored-By: Claude Code <noreply@anthropic.com>" && git -c http.https://github.com.proxy=http://127.0.0.1:10808 -c credential.helper='!gh auth git-credential' push https://github.com/JerryZhang0751/sunpowerNova.git main:main && git update-ref refs/remotes/origin/main HEAD && sleep 20 && gh run list --limit 1
```

Expected: push 成功；CI 新 run → `gh run watch <id>` 至 **test+site 双绿**；`git branch -d gsc-transport-fix`。死依赖（googleapiclient/google-auth-httplib2/httplib2 留在 lock）在 merge message 或评审记录中记 minor（spec §0 既定：lock 不动）。
