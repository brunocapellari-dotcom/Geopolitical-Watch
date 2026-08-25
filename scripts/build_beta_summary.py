from __future__ import annotations

import argparse
import json
from pathlib import Path

from _repo_path import ensure_repo_path

ensure_repo_path()

from geowatch.beta_digest import build_beta_digest, render_beta_digest_markdown
from geowatch.coverage_dashboard import build_source_coverage_dashboard
from geowatch.operational_intelligence import append_history, build_operational_snapshot, compare_snapshots
from geowatch.prospective_forecasting import append_forecast_ledger,create_prospective_forecasts,resolve_forecasts,score_resolved_forecasts
from geowatch.source_resilience import append_source_history,summarize_source_history
from geowatch.storage_factory import open_store


def _load(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError,OSError): return default


def _daily_forecast_candidates(episodes: list[dict], ledger: dict, created_at: str) -> list[dict]:
    day=str(created_at)[:10]
    seen={(r.get("episode_id"),str(r.get("created_at"))[:10]) for r in ledger.get("forecasts",[])}
    return [r for r in episodes if (r.get("episode_id"),day) not in seen]


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",default="data/beta.db")
    parser.add_argument("--out",default="reports/beta_coverage.json")
    parser.add_argument("--run",default="beta-run.json")
    parser.add_argument("--episode-report",default="reports/episodes/latest.json")
    parser.add_argument("--state-dir",default="state/beta")
    parser.add_argument("--slo-config",default="config/operations/source_slo.json")
    args=parser.parse_args()
    store=open_store(args.db)
    try: coverage=build_source_coverage_dashboard(store)
    finally: store.close()
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding="utf-8")

    run=_load(Path(args.run),{})
    episode_report=_load(Path(args.episode_report),{"generated_at":run.get("generated_at"),"episodes":[],"episode_count":0})
    state_dir=Path(args.state_dir); state_dir.mkdir(parents=True,exist_ok=True)
    generated_at=str(run.get("generated_at") or episode_report.get("generated_at") or "")

    previous=_load(state_dir/"latest_snapshot.json",{}) or None
    snapshot=build_operational_snapshot(
        generated_at=generated_at,source_results=list(run.get("source_results") or []),coverage=coverage,episode_report=episode_report,
        alerts_generated=int(run.get("alerts_generated") or 0),alerts_enqueued=int(run.get("alerts_enqueued") or 0),
    )
    delta=compare_snapshots(previous,snapshot)
    history=append_history(_load(state_dir/"history.json",{}),snapshot)
    (state_dir/"latest_snapshot.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
    (state_dir/"history.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
    (Path("reports")/"beta_delta.json").write_text(json.dumps(delta,ensure_ascii=False,indent=2),encoding="utf-8")
    (Path("reports")/"beta_operational_history.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")

    source_history=append_source_history(_load(state_dir/"source_history.json",{}),generated_at=generated_at,source_results=list(run.get("source_results") or []),coverage=coverage,retention_days=365)
    (state_dir/"source_history.json").write_text(json.dumps(source_history,ensure_ascii=False,indent=2),encoding="utf-8")
    source_resilience=summarize_source_history(source_history,as_of=generated_at,slo_config=_load(Path(args.slo_config),{}))
    Path("reports/source_resilience.json").write_text(json.dumps(source_resilience,ensure_ascii=False,indent=2),encoding="utf-8")

    ledger=_load(state_dir/"forecast_ledger.json",{"forecasts":[]})
    episode_states={str(r.get("episode_id")):r for r in episode_report.get("episodes",[]) if r.get("episode_id")}
    ledger=resolve_forecasts(ledger,episode_states,resolved_at=generated_at)
    candidates=_daily_forecast_candidates(list(episode_report.get("episodes") or []),ledger,generated_at)
    ledger=append_forecast_ledger(ledger,create_prospective_forecasts(candidates,created_at=generated_at))
    (state_dir/"forecast_ledger.json").write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding="utf-8")
    forecast_score=score_resolved_forecasts(ledger)
    Path("reports/prospective_forecast_score.json").write_text(json.dumps(forecast_score,ensure_ascii=False,indent=2),encoding="utf-8")

    health=snapshot["health"]
    digest=build_beta_digest(episode_report,coverage,run_health={
        "degraded":health["degraded"],"conflict_coverage_available":bool(any(r.get("status")=="ok" and r.get("source_id")=="gdelt_conflict_news" for r in run.get("source_results") or [])),
        "transient_source_errors":health["transient_errors"],"structural_source_errors":health["structural_errors"],
    })
    digest["operational_health_class"]=health["status"]
    digest["delta_from_previous_run"]=delta
    digest["provider_resilience"]={"schema_version":source_resilience["schema_version"],"sources":source_resilience["sources"]}
    digest["prospective_forecasting"]={"ledger_count":ledger.get("forecast_count",0),"resolved_score":forecast_score}
    Path("reports/beta_digest.json").write_text(json.dumps(digest,ensure_ascii=False,indent=2),encoding="utf-8")
    Path("reports/beta_digest.md").write_text(render_beta_digest_markdown(digest)+"\n## What changed since previous run\n\n"+"\n".join(f"- {row.get('type')}: {row}" for row in delta.get("changes",[])[:30])+"\n",encoding="utf-8")
    print(json.dumps({"coverage":coverage,"health":health,"delta":delta,"history_snapshots":history["snapshot_count"],"source_history_observations":source_history["observation_count"],"forecast_ledger_count":ledger.get("forecast_count",0)},ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__": raise SystemExit(main())
