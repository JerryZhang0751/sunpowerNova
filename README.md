# SunPower Nova

SunHestia GEO 实验 + 多 Agent GEO/SEO 平台（双线一体）。

## 这是什么

- **实验**：验证 GEO 方法能否可复现地提升光储站点 sunhestia.com 在 LLM 答案中的
  被引率（周迭代 w1..wN，固定 15 核心 prompt × 3 模型采集，评估分数与 GSC 遥测对照）。
- **平台**：6 环节闭环 —— 采集（3 家官方 API 原生联网）→ 研究（Kimi）→
  生成（Kimi + 人审）→ 评估（GEO/SEO 双确定性评分）→ 规则迭代（RulesKeeper）→
  HTML 报告；LangGraph 静态 DAG 编排。
- **权威设计文档**：`docs/superpowers/specs/`（当前权威 = 2026-07-29 整合设计 v1.1
  及后续修订）；周迭代操作知识在会话记忆的 runbook 里，不入库。

## 快速上手

环境要求：Python 3.11（管线）、Node 20+（站点）；本机代理 `127.0.0.1:10808`
是 GSC 与外站抓取的硬依赖。

```bash
# 1) 安装依赖（二选一；requirements.lock 为 CI 使用的完整锁）
python3.11 -m pip install -r geo-agent/requirements.lock
python3.11 -m pip install -e "geo-agent[dev]"   # 开发安装（editable + pytest）

# 2) 跑测试（全新机器：装好上面依赖后直接 pytest）
cd geo-agent && pytest tests/

#    本机当前约定（.venv 被沙箱封锁的临时替代：依赖装在 /tmp/pylibs312）：
cd geo-agent && PYTHONPATH=/tmp/pylibs312 python3.12 -m pytest tests/ \
    -p no:cacheprovider --timeout=120

# 3) 跑一次周迭代（仓库根目录；week 等参数读 geo-agent/run.yaml）
python3.11 -m geo.orchestrate.graph
python3.11 -m geo.orchestrate.graph --week 4     # 指定周

# 4) 构建站点
cd site && npm install && npm run build          # 发布前先 npm run check（必须 0 错误）
```

注意：周迭代会真实调用付费 API 并可能发布页面，操作前先读 runbook 知识
（快照预热、week 手改规则、resume 三验证等）；日常只跑测试与站点构建即可。

## 新机器迁移清单（仓库不含的部分）

1. `geo-agent/.env`（4 个模型 API key）+ GSC 服务账号私钥 JSON（放 `geo-agent/` 下）
2. `geo-agent/data/`（实验数据）+ `geo-agent/state/runs.sqlite`（DAG checkpoint）+
   `geo-agent/reports/`（历史报告）
3. `site/.cf_token`（部署凭据）+ Cloudflare 账号 ID（见 `site/DEPLOY.md`）
4. 本机代理（GSC/外站抓取硬依赖）+ Python 3.11 + Node 20+
5. git 推送凭据（HTTPS + `gh auth login`）

## 目录

- `geo-agent/` — GEO/SEO 平台（`src/geo/`：collect / fetch / research / generate /
  assess / rules / report / orchestrate + eval）
- `site/` — Astro 静态站点（Cloudflare Pages；部署流程见 `site/DEPLOY.md`）
- `docs/superpowers/specs/` — 权威设计文档
- `docs/superpowers/plans/` — 各阶段实现计划
- `docs/archive/` — 整合设计之前的归档历史
