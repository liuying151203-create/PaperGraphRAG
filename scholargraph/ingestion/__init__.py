"""Scientific-paper ingestion adapters."""

from scholargraph.ingestion.models import PaperIngestionReceipt, PaperMetadata
from scholargraph.ingestion.service import enqueue_scientific_pdf

__all__ = [
    "PaperIngestionReceipt",
    "PaperMetadata",
    "enqueue_scientific_pdf",
]
