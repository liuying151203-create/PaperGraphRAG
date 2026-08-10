"""Adapter from Zotero sync records to LightRAG's existing ingestion API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from scholargraph.ingestion import PaperMetadata, enqueue_scientific_pdf
from scholargraph.zotero.models import ZoteroAttachment, ZoteroPaper

if TYPE_CHECKING:
    from lightrag import LightRAG


class ZoteroRAGGateway(Protocol):
    """Minimal derived-index operations required by the sync service."""

    async def index_pdf(
        self, pdf_path: Path, paper: ZoteroPaper, attachment: ZoteroAttachment
    ) -> str: ...

    async def delete_document(self, document_id: str) -> None: ...


class LightRAGZoteroGateway:
    """Use MinerU ingestion and attribution-safe LightRAG deletion."""

    def __init__(
        self,
        rag: LightRAG,
        *,
        parse_engine: str = "mineru",
        process_options: str = "P",
    ) -> None:
        self.rag = rag
        self.parse_engine = parse_engine
        self.process_options = process_options

    async def index_pdf(
        self, pdf_path: Path, paper: ZoteroPaper, attachment: ZoteroAttachment
    ) -> str:
        receipt = await enqueue_scientific_pdf(
            self.rag,
            pdf_path,
            PaperMetadata(
                paper_id=paper.key,
                title=paper.title,
                authors=list(paper.authors),
                year=paper.year,
                doi=paper.doi,
                source_path=str(pdf_path),
                zotero_item_key=paper.key,
                zotero_attachment_key=attachment.key,
                collection_keys=list(paper.collections),
                tags=list(paper.tags),
            ),
            parse_engine=self.parse_engine,
            process_options=self.process_options,
        )
        return receipt.document_id

    async def delete_document(self, document_id: str) -> None:
        result = await self.rag.adelete_by_doc_id(document_id)
        if result.status not in {"success", "not_found"}:
            raise RuntimeError(
                f"LightRAG could not delete {document_id}: {result.message}"
            )
