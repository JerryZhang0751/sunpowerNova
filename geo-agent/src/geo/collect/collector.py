from __future__ import annotations
import json, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
from geo.shared.config import settings
from geo.shared.models import L1Record, L2Record, RunRecord, PromptRow
from geo.shared.storage import l1_path
from geo.collect.prompts import load_prompts, PROMPT_SET_VERSION
from geo.collect.qwen_client import collect_qwen
from geo.collect.doubao_client import collect_doubao
from geo.collect.zhipu_client import collect_zhipu
from geo.collect.l2_parser import parse_l2

log = logging.getLogger("collector")
CLIENTS = {"qwen": collect_qwen, "doubao": collect_doubao, "zhipu": collect_zhipu}

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
            recs.append(RunRecord(week=week, model=m, prompt_id=r.id, run=run,
                prompt_set_version=PROMPT_SET_VERSION, rule_snapshot_version=rule_version,
                status="skipped_exists", l1_path=str(l1_path(week,m,r.id,run)))); continue
    todo = [(m,r,run,week,rule_version,brand,comp) for (m,r,run,*_) in jobs
            if not l1_path(week,m,r.id,run).exists()]
    with ThreadPoolExecutor(max_workers=3) as ex:       # 3 家并行
        futs = {ex.submit(_one, *j): j for j in todo}
        for f in as_completed(futs):
            try: recs.append(f.result())
            except Exception as e: log.error("fail %s: %s", futs[f], e)
    return recs

if __name__ == "__main__":
    run_collection(settings.run.week, settings.run.providers, None, settings.run.runs, settings.run.rule_version)
