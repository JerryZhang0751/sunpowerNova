from __future__ import annotations
import json, time, logging
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from geo.shared.config import settings
from geo.shared.models import L1Record, L2Record, RunRecord, PromptRow
from geo.shared.storage import l1_path, append_run_records, read_run_records
from geo.shared.weeks import validate_production_week
from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION
from geo.collect.qwen_client import collect_qwen, QwenAPIError
from geo.collect.doubao_client import collect_doubao
from geo.collect.zhipu_client import collect_zhipu
from geo.collect.l2_parser import parse_l2

log = logging.getLogger("collector")
CLIENTS = {"qwen": collect_qwen, "doubao": collect_doubao, "zhipu": collect_zhipu}

# 数据质量门(整合设计: 采集成功率 ≥ 95% 才可流入后续环节)
COLLECTION_GATE = 0.95


class InvalidCollection(ValueError):
    """客户端返回不可用响应(超时空答/空答案)——不得写 L1、不得计 ok
    (2026-08-25 二次审查#5: 否则超时空答能以 status=ok 绕过 95% 门)。"""


# Bug#4(w4): DashScope/网络瞬时故障(如 "Response ended prematurely")单 pass 内
# 重试,免整轮裸跑续跑;API 级错误(配额/鉴权/HTTP 4xx5xx)不重试——烧额度且无效。
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 8.0
_RETRY_MSG = ("ended prematurely", "connection", "timed out")
_RETRYABLE_EXC = (httpx.TransportError, ConnectionError, TimeoutError)
_NO_RETRY_EXC = (QwenAPIError, InvalidCollection, httpx.HTTPStatusError)

def _is_retryable(e: Exception) -> bool:
    if isinstance(e, _NO_RETRY_EXC):
        return False
    if isinstance(e, _RETRYABLE_EXC):
        return True
    s = str(e).lower()          # dashscope SDK 异常类型不透明 → 消息子串兜底
    return any(p in s for p in _RETRY_MSG)

def _collect_with_retry(model: str, prompt: str) -> dict:
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return CLIENTS[model](prompt)
        except Exception as e:
            if attempt >= RETRY_ATTEMPTS or not _is_retryable(e):
                raise
            log.warning("collect %s 第 %d/%d 次传输类失败,%.0fs 后重试: %s",
                        model, attempt, RETRY_ATTEMPTS, RETRY_BACKOFF_S, e)
            time.sleep(RETRY_BACKOFF_S)
    raise AssertionError("unreachable")


def _l1_valid(p) -> bool:
    """盘上 L1 有效判据: 可解析且带非空答案。

    "文件存在即成功"会让空答案/崩溃截断的 L1 冒充有效(二次审查#5);空文件、
    截断文件一律不计入有效分子,续跑遇到也不得 skipped_exists。
    """
    try:
        return bool((json.loads(p.read_text(encoding="utf-8")).get("answer") or "").strip())
    except Exception:
        return False


def _one(model, row, run, week, rule_version, brand, comp):
    out = _collect_with_retry(model, row.prompt)
    if out.get("timeout"):
        raise InvalidCollection(f"{model} 响应超时(timeout=True),截断答案不可用")
    if not (out.get("answer") or "").strip():
        raise InvalidCollection(f"{model} 返回空答案")
    l2 = parse_l2(model, out, row, brand, comp)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    l1 = L1Record(week=week, model=model, prompt_id=row.id, run=run, answer=out["answer"],
                  l2=l2, usage=out.get("usage",{}), elapsed_s=out.get("elapsed_s",0.0),
                  search_triggered=bool(out.get("search_results")), ts_iso=ts,
                  prompt_set_version=PROMPT_SET_VERSION)
    p = l1_path(week, model, row.id, run)
    p.write_text(l1.model_dump_json(indent=2), encoding="utf-8")
    return RunRecord(week=week, model=model, prompt_id=row.id, run=run,
                     prompt_set_version=PROMPT_SET_VERSION, rule_snapshot_version=rule_version,
                     status="ok", l1_path=str(p))

def _mk_rec(week:int, model:str, pid:str, run:int, rule_version:str,
            status:str, l1:str = "", error:str = "") -> RunRecord:
    return RunRecord(week=week, model=model, prompt_id=pid, run=run,
                     prompt_set_version=PROMPT_SET_VERSION, rule_snapshot_version=rule_version,
                     status=status, l1_path=l1, error=error)

def collection_health(week:int) -> dict:
    """从 runs.jsonl 计算 per-model 计划/有效/成功率。

    planned = manifest 中唯一 (model,prompt_id,run) 键数(先注册后执行,崩溃也在
    分母里);valid = 该键 L1 存在且可解析且带非空答案(_l1_valid,盘上是权威)。
    无 manifest(历史周)返回 manifest=False,调用方按 legacy 处理。
    """
    recs = read_run_records(week)
    if not recs:
        return {"manifest": False, "per_model": {}, "min_success_rate": None}
    per: dict[str, dict] = {}
    for key in {(r.model, r.prompt_id, r.run) for r in recs}:
        m, pid, run = key
        d = per.setdefault(m, {"planned": 0, "valid": 0})
        d["planned"] += 1
        if _l1_valid(l1_path(week, m, pid, run)):
            d["valid"] += 1
    rates = []
    for d in per.values():
        d["success_rate"] = round(d["valid"] / d["planned"], 3) if d["planned"] else None
        if d["success_rate"] is not None:
            rates.append(d["success_rate"])
    return {"manifest": True, "per_model": per,
            "min_success_rate": min(rates) if rates else None}

def run_collection(week:int, models:list[str], prompt_ids:list[str]|None, runs:int,
                   rule_version:str) -> list[RunRecord]:
    brand = settings.targets["site"].get("brand_terms", ["SunHestia","sunhestia.com"])
    comp = ["Tesla","Enphase","SolarEdge","Canadian Solar","BYD","sonnen","LG","Panasonic",
            "Generac","Franklin","Bluetti","Huawei"]
    rows = load_prompts(settings.run.scope)
    if prompt_ids: ids=set(prompt_ids); rows=[r for r in rows if r.id in ids]
    jobs = [(m, r, run, week, rule_version, brand, comp) for m in models for r in rows for run in range(1, runs+1)]
    recs = []
    for (m, r, run, *_) in jobs:                       # 续跑去重(只跳过有效 L1)
        if _l1_valid(l1_path(week, m, r.id, run)):
            rec = _mk_rec(week, m, r.id, run, rule_version, "skipped_exists",
                          l1=str(l1_path(week,m,r.id,run)))
            recs.append(rec); append_run_records(week, [rec]); continue
    # 空/截断的既有 L1 不跳过——进 todo 重采覆写,否则坏文件永久占位
    todo = [(m,r,run,week,rule_version,brand,comp) for (m,r,run,*_) in jobs
            if not _l1_valid(l1_path(week,m,r.id,run))]
    # 先注册后执行(2026-08-24 审查#5): 每个 job 先落 planned,进程崩溃也留在分母
    append_run_records(week, [_mk_rec(week, m, r.id, run, rule_version, "planned",
                                      l1=str(l1_path(week, m, r.id, run)))
                              for (m, r, run, *_) in todo])
    with ThreadPoolExecutor(max_workers=3) as ex:       # 3 家并行
        futs = {ex.submit(_one, *j): j for j in todo}
        for f in as_completed(futs):
            j = futs[f]
            try:
                recs.append(f.result())
                append_run_records(week, [recs[-1]])
            except Exception as e:
                # 失败同样落 manifest:planned 分母不丢、error 可追溯(不再只记日志)
                log.error("fail %s: %s", j, e)
                rec = _mk_rec(week, j[0], j[1].id, j[2], rule_version, "failed", error=str(e))
                recs.append(rec); append_run_records(week, [rec])
    return recs

if __name__ == "__main__":
    run_collection(validate_production_week(settings.run.week), settings.run.providers, None, settings.run.runs, settings.run.rule_version)
