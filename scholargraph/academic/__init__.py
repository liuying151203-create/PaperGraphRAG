"""Academic ontology adapter for ScholarGraph."""

from scholargraph.academic.normalizer import (
    academic_addon_params,
    normalize_academic_extraction,
)
from scholargraph.academic.relations import (
    AcademicRelation,
    normalize_relation_keyword,
    validate_relation_signature,
)
from scholargraph.academic.schema import (
    ACADEMIC_ENTITY_TYPES_GUIDANCE,
    AcademicEntityType,
    normalize_entity_type,
)

__all__ = [
    "ACADEMIC_ENTITY_TYPES_GUIDANCE",
    "AcademicEntityType",
    "AcademicRelation",
    "academic_addon_params",
    "normalize_academic_extraction",
    "normalize_entity_type",
    "normalize_relation_keyword",
    "validate_relation_signature",
]
