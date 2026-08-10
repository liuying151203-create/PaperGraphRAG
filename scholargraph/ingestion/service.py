"""Minimal scientific-PDF adapter over LightRAG's native pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lightrag.constants import FULL_DOCS_FORMAT_PENDING_PARSE
from lightrag.utils import compute_mdhash_id, generate_track_id
from lightrag.utils_pipeline import input_dir_path, normalize_document_file_path
from scholargraph.ingestion.models import PaperIngestionReceipt, PaperMetadata

if TYPE_CHECKING:
    from lightrag import LightRAG


async def enqueue_scientific_pdf(
    rag: LightRAG,
    source_path: str | Path,
    metadata: PaperMetadata,
    *,
    track_id: str | None = None,
    parse_engine: str = "mineru",
    process_options: str = "P",
    start_processing: bool = True,
) -> PaperIngestionReceipt:
    """Enqueue one staged PDF through MinerU and the existing RAG pipeline.

    The source must already live under LightRAG's configured ``INPUT_DIR``.
    This function intentionally performs no PDF parsing and creates no parallel
    index: MinerU emits the structured sidecar, then LightRAG owns chunking,
    embedding, entity/relation extraction, storage, retries, and deletion.
    """
    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Scientific PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError("Scientific paper ingestion currently accepts PDF files only")

    configured_input = input_dir_path().resolve()
    try:
        source.relative_to(configured_input)
    except ValueError as exc:
        raise ValueError(
            f"Scientific PDF must be staged under INPUT_DIR: {configured_input}"
        ) from exc

    canonical_file_path = normalize_document_file_path(source.name)
    resolved_track_id = track_id or generate_track_id("scholar_pdf")
    await rag.apipeline_enqueue_documents(
        "",
        file_paths=str(source),
        track_id=resolved_track_id,
        docs_format=FULL_DOCS_FORMAT_PENDING_PARSE,
        parse_engine=parse_engine,
        process_options=process_options,
        document_metadata=metadata.to_document_metadata(),
    )
    if start_processing:
        await rag.apipeline_process_enqueue_documents()

    return PaperIngestionReceipt(
        track_id=resolved_track_id,
        document_id=compute_mdhash_id(canonical_file_path, prefix="doc-"),
        file_path=canonical_file_path,
        parse_engine=parse_engine,
        process_options=process_options,
    )
