from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.sources import faostat,usgs_mcs,eia_international

FAOSTAT_IDS=[
    "d24a448b-3b62-4c09-8c1d-4a39bb599876",
    "955a7b61-ce56-4a04-adf5-61a3012eec84",
    "d5b0de53-e1d6-4060-b1d0-8443d4e13d5f",
    "4e50bf79-ddf5-41b1-8608-468eca2697e2",
    "2f264bb6-1238-459a-bf8b-0e2d0a16804a",
]


def main()->int:
    out=Path("generated/strategic_sources"); out.mkdir(parents=True,exist_ok=True)
    fao=[]
    for dataset_id in FAOSTAT_IDS:
        try:
            row=faostat.catalog_smoke(dataset_id); row["status"]="ok"
        except Exception as exc:
            row={"dataset_id":dataset_id,"status":"error","error":f"{type(exc).__name__}: {exc}"}
        fao.append(row)
    try:
        usgs=usgs_mcs.fetch_release_metadata(); files=usgs_mcs.file_inventory(usgs); usgs_summary={"status":"ok","sciencebase_item_id":usgs["sciencebase_item_id"],"url":usgs["url"],"file_count":len(files),"files":files[:50]}
    except Exception as exc:
        usgs_summary={"status":"error","error":f"{type(exc).__name__}: {exc}","file_count":0}
    try:
        manifest=eia_international.fetch_bulk_manifest(); entries=eia_international.international_bulk_entries(manifest); eia={"status":"ok","international_bulk_entries":len(entries),"entries":entries[:20],"activation":eia_international.activation_status()}
    except Exception as exc:
        eia={"status":"error","error":f"{type(exc).__name__}: {exc}","international_bulk_entries":0,"activation":eia_international.activation_status()}
    payload={
        "schema_version":"geowatch-strategic-public-sources-v1","faostat":fao,"usgs_mcs":usgs_summary,"eia":eia,
        "faostat_catalog_successes":sum(r.get("status")=="ok" for r in fao),"faostat_smart_csv_discoveries":sum(bool(r.get("smart_csv_discovered")) for r in fao),
        "source_access_is_not_equivalent_to_complete_numeric_backfill":True,
        "credentials_do_not_block_public_bulk_or_other_sources":True,
    }
    (out/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    # FAOSTAT pages and EIA bulk manifest are public. ScienceBase can be intermittently protected by edge services,
    # so metadata failure is reported but does not hide the other public source results.
    core_pass=payload["faostat_catalog_successes"]>=4 and eia.get("status")=="ok" and eia.get("international_bulk_entries",0)>0
    return 0 if core_pass else 2

if __name__=="__main__": raise SystemExit(main())
