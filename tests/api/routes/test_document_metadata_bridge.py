from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_original_argv = sys.argv[:]
sys.argv = [sys.argv[0]]
_document_routes = importlib.import_module("lightrag.api.routers.document_routes")
sys.argv = _original_argv

pipeline_enqueue_file = _document_routes.pipeline_enqueue_file


class _BridgeRAG:
    def __init__(self) -> None:
        self.addon_params = {}
        self.calls: list[dict] = []

    async def apipeline_enqueue_documents(self, input: str, **kwargs):
        self.calls.append({"input": input, **kwargs})
        return kwargs["track_id"]

    async def apipeline_enqueue_error_documents(self, *args, **kwargs):
        raise AssertionError("valid MinerU enqueue must not create an error document")


@pytest.mark.asyncio
async def test_document_route_bridge_forwards_metadata_to_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LIGHTRAG_PARSER", "pdf:mineru,*:legacy")
    monkeypatch.setenv("MINERU_API_MODE", "local")
    monkeypatch.setenv("MINERU_LOCAL_ENDPOINT", "http://mineru.example")
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    metadata = {"paper_id": "paper-1", "title": "Graph Retrieval"}
    rag = _BridgeRAG()

    success, track_id = await pipeline_enqueue_file(
        rag,
        paper,
        "track-1",
        document_metadata=metadata,
    )

    assert success is True
    assert track_id == "track-1"
    assert rag.calls[0]["parse_engine"] == "mineru"
    assert rag.calls[0]["document_metadata"] == metadata
