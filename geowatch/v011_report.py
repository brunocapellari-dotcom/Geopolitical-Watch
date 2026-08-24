from __future__ import annotations

from .backfill_planner import BackfillPlanner
from .critical_infrastructure import CriticalInfrastructureGraph
from .global_profiles import GlobalProfileRegistry
from .graph_audit import audit_strategic_graph
from .historical_corpus import HistoricalCorpus
from .profile_enrichment import ProfileEnrichmentQueue
from .readiness import current_code_readiness_estimate
from .release_audit import ReleaseAudit
from .source_activation import SourceActivationRegistry


def build_acceleration_report(*, env: dict[str,str] | None=None, reviewed_terms: set[str] | None=None) -> dict:
    activation=SourceActivationRegistry.from_json().evaluate(env=env or {}, reviewed_terms=reviewed_terms or set())
    queue=BackfillPlanner.from_json().queue(activation, per_source_limit=2)
    profiles=GlobalProfileRegistry.from_files().coverage()
    progress=ProfileEnrichmentQueue.from_files().progress()
    infrastructure=CriticalInfrastructureGraph.from_json().summary()
    history=HistoricalCorpus.from_json().summary()
    graph=audit_strategic_graph()
    enabled={row["source_id"] for row in activation["sources"] if row["configured_enabled"]}
    release=ReleaseAudit.from_files().evaluate(enabled_sources=enabled,evidence={})
    return {
        "schema_version":"geowatch-v011-acceleration-report-v1",
        "source_activation":activation,
        "next_backfill_windows":queue,
        "country_profiles":profiles,
        "profile_priorities":progress,
        "critical_infrastructure":infrastructure,
        "historical_corpus":history,
        "strategic_graph_audit":graph,
        "readiness":current_code_readiness_estimate(),
        "release_audit":release,
        "external_gates_are_not_faked":True,
    }
