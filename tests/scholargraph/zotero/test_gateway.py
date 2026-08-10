from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from scholargraph.zotero.gateway import LightRAGZoteroGateway
from scholargraph.zotero.models import ZoteroAttachment, ZoteroPaper


@pytest.mark.asyncio
async def test_gateway_reuses_scientific_ingestion_with_zotero_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    @dataclass
    class Receipt:
        document_id: str

    async def fake_enqueue(rag, source_path, metadata, **kwargs):
        captured.update(
            rag=rag,
            source_path=source_path,
            metadata=metadata.to_document_metadata(),
            kwargs=kwargs,
        )
        return Receipt(document_id="doc-zotero")

    monkeypatch.setattr(
        "scholargraph.zotero.gateway.enqueue_scientific_pdf", fake_enqueue
    )
    rag = object()
    gateway = LightRAGZoteroGateway(
        rag, parse_engine="mineru", process_options="P"  # type: ignore[arg-type]
    )
    paper = ZoteroPaper(
        key="PAPERABC",
        version=3,
        title="A Scientific Paper",
        authors=("Ada Lovelace",),
        year=2025,
        doi="10.1000/example",
        collections=("COLLECT1",),
        tags=("graph",),
    )
    attachment = ZoteroAttachment(
        key="ATTACHAB",
        version=4,
        parent_item_key="PAPERABC",
        title="PDF",
        content_type="application/pdf",
        link_mode="imported_file",
        filename="paper.pdf",
    )
    pdf_path = tmp_path / "ATTACHAB.pdf"

    document_id = await gateway.index_pdf(pdf_path, paper, attachment)

    assert document_id == "doc-zotero"
    assert captured["source_path"] == pdf_path
    assert captured["metadata"] == {
        "paper_id": "PAPERABC",
        "title": "A Scientific Paper",
        "authors": ["Ada Lovelace"],
        "year": 2025,
        "doi": "10.1000/example",
        "source_path": str(pdf_path),
        "zotero_item_key": "PAPERABC",
        "zotero_attachment_key": "ATTACHAB",
        "collection_keys": ["COLLECT1"],
        "tags": ["graph"],
    }
    assert captured["kwargs"] == {
        "parse_engine": "mineru",
        "process_options": "P",
    }


@pytest.mark.asyncio
async def test_gateway_accepts_idempotent_not_found_delete() -> None:
    @dataclass
    class Result:
        status: str
        message: str

    class Rag:
        async def adelete_by_doc_id(self, document_id: str) -> Result:
            assert document_id == "doc-zotero"
            return Result(status="not_found", message="already absent")

    await LightRAGZoteroGateway(Rag()).delete_document("doc-zotero")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_gateway_rejects_failed_lightrag_delete() -> None:
    @dataclass
    class Result:
        status: str
        message: str

    class Rag:
        async def adelete_by_doc_id(self, document_id: str) -> Result:
            return Result(status="not_allowed", message="pipeline busy")

    with pytest.raises(RuntimeError, match="pipeline busy"):
        await LightRAGZoteroGateway(Rag()).delete_document("doc-zotero")  # type: ignore[arg-type]
