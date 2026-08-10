"""ScholarGraph extensions built on top of LightRAG."""

from scholargraph.academic import (
    AcademicEntityType,
    AcademicRelation,
    academic_addon_params,
    normalize_academic_extraction,
)
from scholargraph.ingestion import (
    PaperIngestionReceipt,
    PaperMetadata,
    enqueue_scientific_pdf,
)

__all__ = [
    "AcademicEntityType",
    "AcademicRelation",
    "PaperIngestionReceipt",
    "PaperMetadata",
    "academic_addon_params",
    "enqueue_scientific_pdf",
    "normalize_academic_extraction",
]
