from __future__ import annotations

from pathlib import Path

import pytest

from scholargraph.ingestion import PaperMetadata, enqueue_scientific_pdf


class _FakeRAG:
    def __init__(self) -> None:
        self.enqueue_calls: list[tuple[tuple, dict]] = []
        self.process_calls = 0

    async def apipeline_enqueue_documents(self, *args, **kwargs):
        self.enqueue_calls.append((args, kwargs))
        return kwargs["track_id"]

    async def apipeline_process_enqueue_documents(self) -> None:
        self.process_calls += 1


@pytest.mark.asyncio
async def test_enqueue_scientific_pdf_reuses_pending_parse_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    paper = input_dir / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    rag = _FakeRAG()
    metadata = PaperMetadata(
        paper_id="paper-1",
        title="Graph Retrieval",
        authors=["Alice"],
        year=2025,
        doi="10.1000/example",
        source_path=str(paper),
    )

    receipt = await enqueue_scientific_pdf(
        rag,
        paper,
        metadata,
        track_id="track-1",
    )

    assert receipt.track_id == "track-1"
    assert receipt.file_path == "paper.pdf"
    assert receipt.parse_engine == "mineru"
    assert receipt.process_options == "P"
    assert rag.process_calls == 1
    args, kwargs = rag.enqueue_calls[0]
    assert args == ("",)
    assert kwargs["docs_format"] == "pending_parse"
    assert kwargs["parse_engine"] == "mineru"
    assert kwargs["document_metadata"]["paper_id"] == "paper-1"


@pytest.mark.asyncio
async def test_enqueue_scientific_pdf_requires_staged_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    metadata = PaperMetadata(
        paper_id="paper-1",
        title="Graph Retrieval",
        source_path=str(outside),
    )

    with pytest.raises(ValueError, match="staged under INPUT_DIR"):
        await enqueue_scientific_pdf(_FakeRAG(), outside, metadata)
