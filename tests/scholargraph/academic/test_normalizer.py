from scholargraph.academic import (
    ACADEMIC_ENTITY_TYPES_GUIDANCE,
    AcademicEntityType,
    AcademicRelation,
    academic_addon_params,
    normalize_academic_extraction,
    normalize_entity_type,
    normalize_relation_keyword,
    validate_relation_signature,
)


def _node(name: str, entity_type: str) -> dict:
    return {
        "entity_name": name,
        "entity_type": entity_type,
        "description": f"Description of {name}",
        "source_id": "chunk-1",
    }


def _edge(source: str, target: str, keywords: str) -> dict:
    return {
        "src_id": source,
        "tgt_id": target,
        "keywords": keywords,
        "description": f"{source} relates to {target}",
        "source_id": "chunk-1",
    }


def test_entity_aliases_map_to_academic_schema():
    assert normalize_entity_type("algorithm") is AcademicEntityType.METHOD
    assert normalize_entity_type("evaluation_metric") is AcademicEntityType.METRIC
    assert normalize_entity_type("unrecognized") is AcademicEntityType.CONCEPT


def test_relation_aliases_map_to_canonical_ontology():
    assert normalize_relation_keyword("experimented on, benchmark") is (
        AcademicRelation.EVALUATED_ON
    )
    assert normalize_relation_keyword("DEFENDS_AGAINST") is (
        AcademicRelation.DEFENDS_AGAINST
    )
    assert normalize_relation_keyword("loosely associated") is None


def test_relation_signature_allows_light_rag_reverse_orientation():
    assert validate_relation_signature(
        AcademicRelation.PROPOSES,
        AcademicEntityType.METHOD,
        AcademicEntityType.PAPER,
    )
    assert not validate_relation_signature(
        AcademicRelation.PROPOSES,
        AcademicEntityType.DATASET,
        AcademicEntityType.METHOD,
    )


def test_extraction_adapter_normalizes_valid_records_and_preserves_open_relations():
    nodes = {
        "MetaGraph": [_node("MetaGraph", "algorithm")],
        "ACM": [_node("ACM", "benchmark")],
        "Node Classification": [_node("Node Classification", "problem")],
        "Figure 1": [_node("Figure 1", "drawing")],
    }
    edges = {
        ("MetaGraph", "ACM"): [
            _edge("MetaGraph", "ACM", "experimented on, benchmark on")
        ],
        ("MetaGraph", "Node Classification"): [
            _edge("MetaGraph", "Node Classification", "addresses")
        ],
        ("ACM", "Node Classification"): [
            _edge("ACM", "Node Classification", "experimented on")
        ],
        ("Figure 1", "MetaGraph"): [
            _edge("Figure 1", "MetaGraph", "associated with")
        ],
    }

    normalized_nodes, normalized_edges = normalize_academic_extraction(nodes, edges)

    assert normalized_nodes["MetaGraph"][0]["entity_type"] == "method"
    assert normalized_nodes["ACM"][0]["entity_type"] == "dataset"
    assert normalized_nodes["Node Classification"][0]["entity_type"] == "task"
    assert normalized_nodes["Figure 1"][0]["entity_type"] == "drawing"
    assert normalized_edges[("MetaGraph", "ACM")][0]["keywords"] == "EVALUATED_ON"
    assert (
        normalized_edges[("MetaGraph", "Node Classification")][0]["keywords"]
        == "ADDRESSES"
    )
    assert (
        normalized_edges[("ACM", "Node Classification")][0]["keywords"]
        == "experimented on"
    )
    assert nodes["MetaGraph"][0]["entity_type"] == "algorithm"


def test_academic_addon_params_preserves_base_configuration():
    params = academic_addon_params({"language": "English"})
    assert params["language"] == "English"
    assert params["entity_types_guidance"] == ACADEMIC_ENTITY_TYPES_GUIDANCE
    assert params["extraction_result_normalizer"] is normalize_academic_extraction
