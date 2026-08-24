from __future__ import annotations
import json, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
from geo.shared.config import settings
from geo.shared.models import L1Record, L2Record, RunRecord, PromptRow
from geo.shared.storage import l1_path, append_run_records, read_run_records
from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION
from geo.collect.qwen_client import collect_qwen
from geo.collect.doubao_client import collect_doubao
from geo.collect.zhipu_client import collect_zhipu
from geo.collect.l2_parser import parse_l2

log = logging.getLogger("collector")
CLIENTS = {"qwen": collect_qwen, "doubao": collect_doubao, "zhipu": collect_zhipu}

# 数据质量门(整合设计: 采集成功率 ≥ 95% 才可流入后续环节)
COLLECTION_GATE = 0.95

@retry(reraise=True, stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
def _one(model, row, run, week, rule_version, brand, comp):
    out = CLIENTS[model](row.prompt)
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
    分母里);valid = 该键 L1 文件确实存在(盘上是权威)。无 manifest(历史周)
    返回 manifest=False,调用方按 legacy 处理(planned 无法追溯)。
    """
    recs = read_run_records(week)
    if not recs:
        return {"manifest": False, "per_model": {}, "min_success_rate": None}
    per: dict[str, dict] = {}
    for key in {(r.model, r.prompt_id, r.run) for r in recs}:
        m, pid, run = key
        d = per.setdefault(m, {"planned": 0, "valid": 0})
        d["planned"] += 1
        if l1_path(week, m, pid, run).exists():
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
    for (m, r, run, *_) in jobs:                       # 续跑去重
        if l1_path(week, m, r.id, run).exists():
            rec = _mk_rec(week, m, r.id, run, rule_version, "skipped_exists",
                          l1=str(l1_path(week,m,r.id,run)))
            recs.append(rec); append_run_records(week, [rec]); continue
    todo = [(m,r,run,week,rule_version,brand,comp) for (m,r,run,*_) in jobs
            if not l1_path(week,m,r.id,run).exists()]
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
    run_collection(settings.run.week, settings.run.providers, None, settings.run.runs, settings.run.rule_version)
