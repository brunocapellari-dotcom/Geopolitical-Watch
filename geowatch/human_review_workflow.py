from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter,defaultdict
from typing import Iterable

from .human_gold import VALID_LABELS,validate_reviewed_batch


def review_batch_csv(batch: dict) -> str:
    fields=["candidate_id","task_type","title","context","machine_label","machine_score","region","source_mix","human_label","reviewer","reviewed_at","notes"]
    buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=fields); writer.writeheader()
    for row in batch.get("items",[]):
        writer.writerow({k:("+".join(row.get(k) or []) if k=="source_mix" and isinstance(row.get(k),list) else row.get(k,"")) for k in fields})
    return buf.getvalue()


def import_review_csv(text: str, original_batch: dict) -> dict:
    originals={str(r.get("candidate_id")):dict(r) for r in original_batch.get("items",[])}; items=[]; unknown=[]
    for row in csv.DictReader(io.StringIO(text)):
        cid=str(row.get("candidate_id") or "")
        if cid not in originals: unknown.append(cid); continue
        base=originals[cid]
        mix=row.get("source_mix"); base.update({"human_label":row.get("human_label") or None,"reviewer":row.get("reviewer") or None,"reviewed_at":row.get("reviewed_at") or None,"notes":row.get("notes") or None})
        if mix: base["source_mix"]=[x for x in mix.split("+") if x]
        items.append(base)
    validated=validate_reviewed_batch({"items":items})
    return {"schema_version":"geowatch-human-review-import-v1","batch_id":original_batch.get("batch_id"),"validated":validated,"unknown_candidate_ids":unknown}


def render_review_html(batch: dict) -> str:
    cards=[]
    for row in batch.get("items",[]):
        task=str(row.get("task_type")); labels=sorted(VALID_LABELS.get(task,[])); options="".join(f"<option>{html.escape(x)}</option>" for x in labels)
        cards.append(f"<section data-candidate='{html.escape(str(row.get('candidate_id')))}'><h3>{html.escape(str(row.get('title') or row.get('candidate_id')))}</h3><p>{html.escape(str(row.get('context') or ''))}</p><p>Task: <b>{html.escape(task)}</b> | Machine: {html.escape(str(row.get('machine_label')))}</p><label>Human label <select>{options}</select></label><label> Notes <input></label></section>")
    return "<!doctype html><meta charset='utf-8'><title>Geowatch Human Review</title><style>body{font-family:system-ui;margin:24px}section{border:1px solid #ddd;padding:12px;margin:12px 0}label{margin-right:12px}</style><h1>Human review batch</h1><p>Labels shown here are not gold until reviewer identity and timestamp are stored in the imported review artifact.</p>"+"".join(cards)


def inter_rater_agreement(reviews: Iterable[dict]) -> dict:
    groups=defaultdict(list)
    for r in reviews:
        if r.get("candidate_id") and r.get("reviewer") and r.get("human_label"): groups[str(r["candidate_id"])].append(r)
    comparable=[vals for vals in groups.values() if len({v.get("reviewer") for v in vals})>=2]
    if not comparable: return {"schema_version":"geowatch-inter-rater-v1","items":0,"pairwise_agreement":None,"cohen_kappa":None,"insufficient_data":True}
    agree=total=0; marg_a=Counter(); marg_b=Counter()
    for vals in comparable:
        vals=sorted(vals,key=lambda r:str(r.get("reviewer")))[:2]; a,b=vals[0]["human_label"],vals[1]["human_label"]; total+=1; agree+=a==b; marg_a[a]+=1; marg_b[b]+=1
    po=agree/total; labels=set(marg_a)|set(marg_b); pe=sum((marg_a[l]/total)*(marg_b[l]/total) for l in labels); kappa=(po-pe)/(1-pe) if pe<1 else 1.0
    return {"schema_version":"geowatch-inter-rater-v1","items":total,"pairwise_agreement":round(po,6),"cohen_kappa":round(kappa,6),"insufficient_data":False}


def adjudication_queue(reviews: Iterable[dict]) -> dict:
    groups=defaultdict(list)
    for r in reviews:
        if r.get("candidate_id") and r.get("human_label"): groups[str(r["candidate_id"])].append(r)
    rows=[]
    for cid,vals in groups.items():
        labels=sorted({str(v.get("human_label")) for v in vals})
        if len(labels)>1:
            rows.append({"candidate_id":cid,"labels":labels,"reviewers":sorted({str(v.get("reviewer")) for v in vals if v.get("reviewer")}),"status":"needs_adjudication","adjudicated_label":None,"adjudicator":None,"adjudicated_at":None})
    return {"schema_version":"geowatch-adjudication-queue-v1","count":len(rows),"items":rows}


def finalize_gold(reviews: Iterable[dict], adjudications: Iterable[dict]=()) -> dict:
    adjud={str(r.get("candidate_id")):r for r in adjudications if r.get("adjudicated_label") and r.get("adjudicator") and r.get("adjudicated_at")}
    groups=defaultdict(list)
    for r in reviews:
        if r.get("candidate_id") and r.get("human_label") and r.get("reviewer") and r.get("reviewed_at"): groups[str(r["candidate_id"])].append(r)
    gold=[]; blocked=[]
    for cid,vals in groups.items():
        labels={str(v.get("human_label")) for v in vals}
        if len(labels)==1:
            chosen=vals[0]; gold.append({**chosen,"human_label":next(iter(labels)),"human_gold":True,"gold_method":"review_consensus"})
        elif cid in adjud:
            chosen=vals[0]; gold.append({**chosen,"human_label":adjud[cid]["adjudicated_label"],"human_gold":True,"gold_method":"adjudicated","adjudication":adjud[cid]})
        else: blocked.append(cid)
    return {"schema_version":"geowatch-human-gold-dataset-v1","count":len(gold),"items":gold,"blocked_disagreements":blocked,"gold_requires_human_review":True}
