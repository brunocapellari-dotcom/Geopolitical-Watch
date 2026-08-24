from __future__ import annotations

import json
from pathlib import Path


def audit_strategic_graph(graph_path: str|Path="config/geopolitics/strategic_graph.json", sources_path: str|Path="config/geopolitics/strategic_sources.json") -> dict:
    graph=json.loads(Path(graph_path).read_text(encoding="utf-8")); sources=json.loads(Path(sources_path).read_text(encoding="utf-8"))
    nodes={row["id"] for row in graph.get("nodes",[])}; source_ids={row["source_id"] for row in sources.get("sources",[])}
    errors=[]; warnings=[]
    seen=set()
    for edge in graph.get("edges",[]):
        eid=edge.get("id")
        if not eid or eid in seen: errors.append({"edge_id":eid,"issue":"missing_or_duplicate_id"})
        seen.add(eid)
        for key in ("source","target"):
            if edge.get(key) not in nodes: errors.append({"edge_id":eid,"issue":f"unknown_{key}","value":edge.get(key)})
        if not edge.get("valid_from"): errors.append({"edge_id":eid,"issue":"missing_valid_from"})
        if not edge.get("source_ids"): errors.append({"edge_id":eid,"issue":"missing_source_ids"})
        for source_id in edge.get("source_ids",[]):
            if source_id not in source_ids: errors.append({"edge_id":eid,"issue":"unknown_source_id","value":source_id})
        if edge.get("refresh") not in {"structural",None} and not edge.get("valid_to"):
            warnings.append({"edge_id":eid,"issue":"open_ended_edge_requires_refresh"})
    return {"schema_version":"geowatch-strategic-graph-audit-v1","errors":errors,"warnings":warnings,"passed":not errors,"edge_count":len(graph.get("edges",[])),"node_count":len(nodes)}
