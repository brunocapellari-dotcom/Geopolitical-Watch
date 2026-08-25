from __future__ import annotations

import argparse
import json
from pathlib import Path

from _repo_path import ensure_repo_path

ensure_repo_path()

from geowatch.beta_digest import build_beta_digest, render_beta_digest_markdown
from geowatch.coverage_dashboard import build_source_coverage_dashboard
from geowatch.operational_intelligence import append_history, build_operational_snapshot, compare_snapshots
from geowatch.storage_factory import open_store


def _load(path: Path, default: dict) -> dict:
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError,OSError): return default


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",default="data/beta.db")
    parser.add_argument("--out",default="reports/beta_coverage.json")
    parser.add_argument("--run",default="beta-run.json")
    parser.add_argument("--episode-report",default="reports/episodes/latest.json")
    parser.add_argument("--state-dir",default="state/beta")
    args=parser.parse_args()
    store=open_store(args.db)
    try: coverage=build_source_coverage_dashboard(store)
    finally: store.close()
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding="utf-8")

    run=_load(Path(args.run),{})
    episode_report=_load(Path(args.episode_report),{"generated_at":run.get("generated_at"),"episodes":[],"episode_count":0})
    state_dir=Path(args.state_dir); state_dir.mkdir(parents=True,exist_ok=True)
    previous=_load(state_dir/"latest_snapshot.json",{}) or None
    snapshot=build_operational_snapshot(
        generated_at=str(run.get("generated_at") or episode_report.get("generated_at") or ""),
        source_results=list(run.get("source_results") or []),coverage=coverage,episode_report=episode_report,
        alerts_generated=int(run.get("alerts_generated") or 0),alerts_enqueued=int(run.get("alerts_enqueued") or 0),
    )
    delta=compare_snapshots(previous,snapshot)
    history=append_history(_load(state_dir/"history.json",{}),snapshot)
    (state_dir/"latest_snapshot.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
    (state_dir/"history.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
    (Path("reports")/"beta_delta.json").write_text(json.dumps(delta,ensure_ascii=False,indent=2),encoding="utf-8")
    (Path("reports")/"beta_operational_history.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")

    health=snapshot["health"]
    digest=build_beta_digest(episode_report,coverage,run_health={
        "degraded":health["degraded"],"conflict_coverage_available":bool(any(r.get("status")=="ok" and r.get("source_id")=="gdelt_conflict_news" for r in run.get("source_results") or [])),
        "transient_source_errors":health["transient_errors"],"structural_source_errors":health["structural_errors"],
    })
    digest["operational_health_class"]=health["status"]
    digest["delta_from_previous_run"]=delta
    Path("reports/beta_digest.json").write_text(json.dumps(digest,ensure_ascii=False,indent=2),encoding="utf-8")
    Path("reports/beta_digest.md").write_text(render_beta_digest_markdown(digest)+"\n## What changed since previous run\n\n"+"\n".join(f"- {row.get('type')}: {row}" for row in delta.get("changes",[])[:30])+"\n",encoding="utf-8")
    print(json.dumps({"coverage":coverage,"health":health,"delta":delta,"history_snapshots":history["snapshot_count"]},ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__": raise SystemExit(main())
