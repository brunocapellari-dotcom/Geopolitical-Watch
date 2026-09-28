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
    if relationship.valid_from and relationship.valid_to and relationship.valid_to < relationship.valid_from:
        raise ValueError("valid_to must not precede valid_from")
    if relationship.confidence is not None and not 0.0 <= relationship.confidence <= 1.0:
        raise ValueError("relationship confidence must be between 0 and 1")
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
