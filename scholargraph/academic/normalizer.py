"""ScholarGraph adapter for LightRAG extraction results."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scholargraph.academic.relations import (
    normalize_relation_keyword,
    validate_relation_signature,
)
from scholargraph.academic.schema import (
    ACADEMIC_ENTITY_TYPES_GUIDANCE,
    AcademicEntityType,
    normalize_entity_type,
)

_STRUCTURAL_ENTITY_TYPES = frozenset({"drawing", "table", "equation"})


def normalize_academic_extraction(
    nodes: dict,
    edges: dict,
    chunk_data: dict[str, Any] | None = None,
) -> tuple[dict, dict]:
    """Normalize parsed LightRAG records without changing their schema.

    Known entity aliases are mapped to the academic schema. Known relation
    phrases become canonical ontology values only when their endpoint types
    satisfy the relation signature. Unknown relations remain open text so the
    adapter does not discard source-grounded information.
    """

    del chunk_data
    normalized_nodes: dict = {}
    entity_types: dict[str, AcademicEntityType] = {}

    for entity_name, records in nodes.items():
        normalized_records = []
        for record in records:
            normalized = dict(record)
            raw_type = str(normalized.get("entity_type") or "").strip().lower()
            if raw_type not in _STRUCTURAL_ENTITY_TYPES:
                entity_type = normalize_entity_type(raw_type)
                normalized["entity_type"] = entity_type.storage_value
                entity_types[entity_name] = entity_type
            normalized_records.append(normalized)
        normalized_nodes[entity_name] = normalized_records

    normalized_edges: dict = {}
    for edge_key, records in edges.items():
        normalized_records = []
        for record in records:
            normalized = dict(record)
            relation = normalize_relation_keyword(normalized.get("keywords"))
            source_type = entity_types.get(str(normalized.get("src_id") or edge_key[0]))
            target_type = entity_types.get(str(normalized.get("tgt_id") or edge_key[1]))
            if (
                relation is not None
                and source_type is not None
                and target_type is not None
                and validate_relation_signature(relation, source_type, target_type)
            ):
                normalized["keywords"] = relation.value
            normalized_records.append(normalized)
        normalized_edges[edge_key] = normalized_records

    return normalized_nodes, normalized_edges


def academic_addon_params(
    base: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build LightRAG ``addon_params`` for academic extraction."""

    params = dict(base or {})
    params.update(
        {
            "entity_types_guidance": ACADEMIC_ENTITY_TYPES_GUIDANCE,
            "extraction_result_normalizer": normalize_academic_extraction,
        }
    )
    return params
