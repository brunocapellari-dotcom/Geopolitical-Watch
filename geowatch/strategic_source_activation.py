from __future__ import annotations

import os
from pathlib import Path
import json


def load_activation(path: str|Path="config/geopolitics/external_data_activation_v014.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def activation_preflight(config: dict, env: dict[str,str] | None=None) -> dict:
    env=env or dict(os.environ); rows=[]
    for src in config.get("sources",[]):
        required=bool(src.get("credential_required")); key=src.get("credential_env")
        credential_present=bool(key and env.get(str(key))) if required else True
        status="ready_for_live_schema_validation" if credential_present and src.get("status")=="public_ready" else "credential_available_pending_validation" if credential_present and required else "blocked_by_credential" if required else str(src.get("status") or "unknown")
        rows.append({"source_id":src.get("source_id"),"credential_required":required,"credential_present":credential_present,"activation_status":status,"activation_gate":src.get("activation_gate")})
    return {"schema_version":"geowatch-strategic-source-preflight-v1","sources":rows,"blocked_count":sum(r["activation_status"]=="blocked_by_credential" for r in rows),"blocked_source_does_not_block_others":True}
