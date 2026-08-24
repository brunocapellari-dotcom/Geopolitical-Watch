from __future__ import annotations

import hashlib
from typing import Iterable


def build_postmortem(*,subject_type:str,subject_id:str,created_at:str,initial_thesis:str,available_evidence_ids:Iterable[str],forecast_ids:Iterable[str],observed_outcome:str,error_class:str|None,causal_review:list[str],method_changes:list[str]) -> dict:
    fingerprint=f"{subject_type}|{subject_id}|{created_at}|{observed_outcome}"
    return {
        "schema_version":"geowatch-postmortem-v1",
        "postmortem_id":"pm_"+hashlib.sha256(fingerprint.encode()).hexdigest()[:20],
        "subject_type":subject_type,"subject_id":subject_id,"created_at":created_at,
        "initial_thesis":initial_thesis,"available_evidence_ids":sorted(set(available_evidence_ids)),"forecast_ids":sorted(set(forecast_ids)),
        "observed_outcome":observed_outcome,"error_class":error_class,"causal_review":causal_review,"method_changes":method_changes,
        "governance":{"outcome_does_not_rewrite_original_forecast":True,"lessons_are_proposals_not_facts":True,"evidence_snapshot_must_be_preserved":True},
    }


def learning_proposals(postmortem:dict)->list[dict]:
    rows=[]
    for index,change in enumerate(postmortem.get("method_changes",[]),1):
        pid="kp_"+hashlib.sha256(f"{postmortem['postmortem_id']}|{index}|{change}".encode()).hexdigest()[:20]
        rows.append({"proposal_id":pid,"source_postmortem_id":postmortem["postmortem_id"],"proposal_type":"method_change","proposal":change,"status":"pending_review","auto_apply":False})
    return rows


def error_taxonomy()->list[str]:
    return ["data_gap","source_latency","entity_resolution","episode_merge_error","episode_split_error","base_rate_neglect","overreaction_to_signal","underreaction_to_signal","analogy_failure","model_miscalibration","resolution_rule_problem","unknown"]
