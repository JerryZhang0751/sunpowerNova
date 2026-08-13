# src/geo/research/features.py
from __future__ import annotations
from collections import Counter, defaultdict
from urllib.parse import urlparse
from geo.research.models import ResearchCorpus, FeatureAggregates, FeatureBucket

LOW_CONF_THRESHOLD = 5

def _low(n: int) -> bool:
    return n < LOW_CONF_THRESHOLD

def _domain_type(host: str) -> str:
    # coarse classifier; P2+ authority deferred → 'unknown'
    h = (host or "").lower()
    if any(w in h for w in ("wikipedia.","wikimedia.")): return "wiki"
    if any(w in h for w in ("reddit.","forum.","community.")): return "ugc_forum"
    if any(w in h for w in ("news.","cnet.","techcrunch.","theverge.")): return "news_review"
    if any(w in h for w in ("tesla.","enphase.","solaredge.","byd.","sonnen.","lg.","bluetti.")): return "manufacturer"
    return "other"

def aggregate(corpus: ResearchCorpus) -> FeatureAggregates:
    platforms = defaultdict(lambda: {"n":0,"mention":0,"cited":0})
    intent_hits = Counter()
    fmt = {k: {"cited":0,"plats":set()} for k in
           ["comparison_table","qa","list","definition","spec_card"]}
    src_dim = {"domain_type":Counter(),"page_type":Counter(),"schema":Counter(),
               "has_publish_date":0,"ugc":0,"resolved":0}
    resolved_n = 0

    for it in corpus.items:
        m = it.l1.model
        platforms[m]["n"] += 1
        if it.l1.l2.mentioned: platforms[m]["mention"] += 1
        if it.l1.l2.cited_with_link: platforms[m]["cited"] += 1
        intent_hits[it.prompt.intent] += 1
        for cited, l3 in it.sources:
            if l3 is None: continue
            resolved_n += 1
            src_dim["resolved"] += 1
            st, se = l3.structural or {}, l3.semantic or {}
            if st.get("table_count",0)>0: fmt["comparison_table"]["cited"]+=1; fmt["comparison_table"]["plats"].add(m)
            if se.get("has_faq_block"): fmt["qa"]["cited"]+=1; fmt["qa"]["plats"].add(m)
            if st.get("ul_count",0)>0: fmt["list"]["cited"]+=1; fmt["list"]["plats"].add(m)
            if se.get("has_definition_segment"): fmt["definition"]["cited"]+=1; fmt["definition"]["plats"].add(m)
            if se.get("page_type")=="product" or se.get("datapoint_count",0)>=8:
                fmt["spec_card"]["cited"]+=1; fmt["spec_card"]["plats"].add(m)
            parsed_host = urlparse(cited.url).hostname
            domain_type = _domain_type(parsed_host)
            src_dim["domain_type"][domain_type] += 1
            if domain_type == "ugc_forum":
                src_dim["ugc"] += 1
            src_dim["page_type"][se.get("page_type","unknown")] += 1
            for s in st.get("schema_types",[]): src_dim["schema"][s] += 1
            if se.get("has_publish_date"): src_dim["has_publish_date"] += 1

    formats = [FeatureBucket(k, v["cited"], resolved_n, sorted(v["plats"]), _low(resolved_n))
               for k,v in fmt.items()]
    # convert Counters to plain dict for JSON stability
    src_dim = {k:(dict(v) if isinstance(v,Counter) else v) for k,v in src_dim.items()}
    plats = {m:{"n":d["n"],"mention_rate":round(d["mention"]/d["n"],3) if d["n"] else 0.0,
                "citation_rate":round(d["cited"]/d["n"],3) if d["n"] else 0.0} for m,d in platforms.items()}
    covered_intents = {it.prompt.intent for it in corpus.items}
    topic_gaps = [q for q in corpus.gsc_queries if q not in covered_intents]  # coarse gap heuristic
    return FeatureAggregates(week=corpus.week, coverage=corpus.coverage, formats=formats,
        sources=src_dim, platforms=plats,
        problem_space={"intent_clusters":[{"intent":k,"n":v} for k,v in intent_hits.items()],
                       "topic_gaps":topic_gaps})
