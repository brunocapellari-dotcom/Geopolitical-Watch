from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import Relationship

_ADAPTER_METHOD = "geowatch-temporal-graph-adapter"


def validate_derived_relationship(relationship: Relationship) -> Relationship:
    if relationship.semantic_class != "derived":
        raise ValueError("temporal graph adapter accepts derived relationships only")
    if not relationship.evidence_ids and not relationship.derived_from:
        raise ValueError("derived relationship requires evidence_ids or derived_from lineage")
    method = relationship.derivation_method or _ADAPTER_METHOD
    version = relationship.derivation_version or "v1"
    return replace(
        relationship,
        derivation_method=method,
        derivation_version=version,
    )


def persist_derived_relationships(store, relationships: Iterable[Relationship]) -> int:
    rows = [validate_derived_relationship(row) for row in relationships]
    return store.upsert_relationships(rows)
