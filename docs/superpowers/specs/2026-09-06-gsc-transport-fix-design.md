# GSC 传输层持久修复设计

> 日期：2026-09-06 ｜ 状态：已通审（用户批准设计，同日） ｜ 输入：`geo-agent/reports/w4/bug-log.md` Bug#3 终局节（根因反转：httplib2 传输层在代理下挂死）
> 基线：main=2f93805（577 tests） ｜ 分支：`gsc-transport-fix` ｜ 规模：单实现任务 + 真跑探针合并门

## 0. 用户决策记录（2026-09-06 brainstorming）

| 决策点 | 选择 |
|---|---|
| 传输方案 | **AuthorizedSession 直连 REST**（弃 googleapiclient/httplib2；否决保留 googleapiclient——discovery 文档获取是额外代理依赖且代理注入靠私有属性；否决纯 httpx 手铸 JWT——token 路径 400 未定位且失去自动刷新） |
| 验证深度 | **单测 + TEST_WEEK 真跑探针**（代理行为是本次 bug 核心变量，mock 测不出；否决仅单测+w5 首跑——风险后置） |
| 死依赖 | lock 不动（全量冻结既定），记 minor |

## 1. 根因与目标（背景）

w4 GSC 快照 30+ 次拉取全灭。09-06 连通矩阵确诊：**httplib2 传输层在该类代理下连接挂死**（OS 层 Errno 60，120s 超时也不救）；httpx/requests 对 oauth2/searchconsole/www.googleapis.com 全部 0.5-1.0s 秒通；官方未换地址。运维 monkeypatch（AuthorizedSession+env 代理）已实证秒通并完成 w4 补齐——本设计将其正式化为代码，**目标：后续任意代理切换（只改 targets.yaml）不再复现**。

## 2. 硬边界

- **零改动**：快照 JSON 键集、冻结守卫（clean 冻结/degraded 重取）、degraded 语义、w4-bugfixes 的拉取段重试循环（≤3 次/15s）、`_resolve_gsc_key` 回退链、`GSC_TIMEOUT_S=60.0` 值、`_gsc_site_url`、评分语义、w1-w4 冻结产物。
- 测试只增不减（基线 577/0/2）；黄金锁 2 passed 零漂移。
- 不跑生产周；真跑探针只写 TEST_WEEK(901) 测试目录且验后清理。
- commit 显式路径、禁 `git add -A`、尾行 Co-Authored-By。

## 3. 传输层改造（`src/geo/fetch/gsc.py`）

**imports**：删 `from googleapiclient.discovery import build`、`from google_auth_httplib2 import AuthorizedHttp`、`import httplib2`；增 `import requests`、`from google.auth.transport.requests import AuthorizedSession, Request`、`from urllib.parse import quote`（并入现有 urlparse import 行）。`service_account` import 保留。

**删 `_build_service()`**，增：

```python
def _gsc_session() -> AuthorizedSession:
    creds = service_account.Credentials.from_service_account_file(
        str(_resolve_gsc_key(settings.gsc_key_file)), scopes=SCOPES)
    proxies = ({"http": settings.proxy, "https": settings.proxy}
               if settings.proxy else None)
    auth_sess = requests.Session()
    if proxies:
        auth_sess.proxies = proxies   # token 刷新走代理(显式;默认内部裸 session 不继承主 proxies)
    sess = AuthorizedSession(creds, auth_request=Request(session=auth_sess))
    if proxies:
        sess.proxies = proxies        # 查询走代理
    return sess
```

**`snapshot_gsc` 拉取段**（重试循环内）替换 discovery 调用：

```python
            sess = _gsc_session()
            url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
                   f"{quote(site, safe='')}/searchAnalytics/query")
            r = sess.post(url, json=body, timeout=GSC_TIMEOUT_S)
            r.raise_for_status()
            out["rows"] = r.json().get("rows", [])
```

（原 `svc = _build_service(); res = svc.searchanalytics().query(siteUrl=site, body=body).execute(); out["rows"] = res.get("rows", [])` 整体替换；`site` 变量、`body` 构造、`last_err`/break/sleep 重试骨架、`atomic_write_text`/`return` 全部不动。）`GSC_TIMEOUT_S` 注释更新为新语义（requests 单请求超时；保留 httplib2 历史教训一句话）。

**错误面**：网络异常/超时 → 现有 `except Exception` → 重试循环（不变）；HTTP 4xx/5xx → `raise_for_status` 抛 `requests.HTTPError` → 同一 except → 重试后 degraded（error 字符串格式 `{type}: {e}` 自动适配）。

## 4. 测试（`tests/test_gsc.py`）

**既有用例改写（意图不变，patch 对象换）**：

| 用例 | 改写 |
|---|---|
| `test_gsc_happy` | patch `geo.fetch.gsc._gsc_session` 返回 MagicMock，`post.return_value` = mock response（`raise_for_status` no-op、`json.return_value={"rows":[...]}`）；断言不变 |
| `test_gsc_degrades_on_auth_error` | 同上，`post` 抛/返回 403（`raise_for_status.side_effect=requests.HTTPError("403")`）→ degraded；断言不变 |
| `test_gsc_retry_succeeds_third_attempt` / `test_gsc_retry_exhausted_degrades` | `post.side_effect` 序列替换原 execute side_effect（[超时,超时,正常 response] / 恒 TimeoutError），call_count 断言对象改 `sess.post`；断言不变 |
| `test_gsc_http_sets_timeout` | patch `_gsc_session`，捕获 `post` 调用 kwargs，断言 `timeout == GSC_TIMEOUT_S`（transport 无关的意图：每个 GSC 请求必带超时） |
| `test_gsc_proxy_applied_when_set` | 重写为直测 `_gsc_session()`：settings.proxy 设置时主 session 与 `auth_request` 挂的 session **两处** proxies 均为预期 dict；proxy=None 时两处均未设置（patch `_resolve_gsc_key` 与 `service_account.Credentials.from_service_account_file`） |

**新增**：`test_gsc_session_token_refresh_proxied` —— 构造真实 `AuthorizedSession`（凭据构造 patch 掉），断言 `sess._auth_request.session.proxies` 与 `sess.proxies` 都带代理（on）/都不带（off）两态。这是防复发的核心回归锁（默认实现只有 env 变量一条路——本修复消灭该依赖）。

目标计数：改写 5 + 新增 1，总数不低于基线（用例名保留，无删除）。

## 5. TEST_WEEK 真跑探针（合并门，需代理在场，不进 CI）

```bash
PYTHONPATH="$HOME/pylibs312:src" python3.12 -c "
from geo.fetch.gsc import snapshot_gsc
from geo.shared.weeks import TEST_WEEK
snap = snapshot_gsc(TEST_WEEK, 'geo-seo-v5')
assert not snap.get('degraded') and snap.get('rows'), snap
print('LIVE OK rows=', len(snap['rows']))"
rm -rf data/snapshots/w901   # 验后清理(测试带目录)
```

失败处置：真跑仍挂死 → **不合并**，回设计（排查 token 路径显式 proxies 与 env 方式的行为差异），记录后重新评审。

## 6. 执行策略

分支 `gsc-transport-fix` 自 main=2f93805；TDD（红=改写用例先在新接口上红/新增用例先红 → 绿=传输层改造）→ 全量 577+新增 EXIT=0 → 黄金锁 2 passed → `git status` 核对 → 真跑探针（§5）→ 终局评审 → `merge --no-ff` 回 main → push（HTTPS+代理通道）→ CI 双绿 → 分支删。测试环境：`PYTHONPATH="$HOME/pylibs312" python3.12 -m pytest ...`（junit 计数+EXIT 为准）。死依赖（googleapiclient/google-auth-httplib2/httplib2 留在 lock）记 minor 供终局评审 triage。
