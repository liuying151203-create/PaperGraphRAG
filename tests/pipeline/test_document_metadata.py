from __future__ import annotations

import asyncio
from uuid import uuid4

import numpy as np
import pytest

from lightrag import LightRAG
from lightrag.kg.shared_storage import finalize_share_data, initialize_share_data
from lightrag.utils import EmbeddingFunc, Tokenizer, compute_mdhash_id
from lightrag.utils_pipeline import (
    MAX_DOCUMENT_METADATA_BYTES,
    doc_status_reset_metadata,
    normalize_document_metadata,
)

pytestmark = pytest.mark.offline


class _TokenizerImpl:
    def encode(self, content: str) -> list[int]:
        return [ord(ch) for ch in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


async def _embedding(texts: list[str]) -> np.ndarray:
    return np.ones((len(texts), 8), dtype=float)


async def _llm(*args, **kwargs) -> str:
    return "ok"


def _chunking(*args) -> list[dict]:
    content = args[1]
    return [{"tokens": len(content), "content": content, "chunk_order_index": 0}]


@pytest.fixture(autouse=True)
def _shared_storage():
    initialize_share_data()
    yield
    finalize_share_data()


def test_document_metadata_is_json_safe_and_bounded() -> None:
    normalized = normalize_document_metadata({"authors": ("Alice", "Bob")})
    assert normalized == {"authors": ["Alice", "Bob"]}

    with pytest.raises(TypeError, match="JSON object"):
        normalize_document_metadata(["not", "an", "object"])
    with pytest.raises(ValueError, match="64 KiB"):
        normalize_document_metadata({"payload": "x" * MAX_DOCUMENT_METADATA_BYTES})


def test_document_metadata_survives_retry_reset() -> None:
    metadata = {"paper_id": "paper-1", "title": "Graph Retrieval"}
    reset = doc_status_reset_metadata(
        {
            "metadata": {
                "document_metadata": metadata,
                "parse_start_time": 123,
                "parse_warnings": {"warning": 1},
            }
        }
    )

    assert reset == {"document_metadata": metadata}


def test_document_metadata_survives_full_pipeline(tmp_path) -> None:
    async def _run() -> None:
        rag = LightRAG(
            working_dir=str(tmp_path / "wd"),
            workspace=f"metadata-{uuid4().hex[:8]}",
            llm_model_func=_llm,
            embedding_func=EmbeddingFunc(
                embedding_dim=8,
                max_token_size=8192,
                func=_embedding,
            ),
            tokenizer=Tokenizer("metadata-test", _TokenizerImpl()),
            chunking_func=_chunking,
            max_parallel_insert=1,
        )
        await rag.initialize_storages()
        try:
            metadata = {
                "paper_id": "paper-1",
                "title": "Graph Retrieval",
                "authors": ["Alice", "Bob"],
                "year": 2025,
                "doi": "10.1000/example",
                "source_path": "/library/paper.pdf",
                "zotero_item_key": "ITEM1",
                "zotero_attachment_key": "ATT1",
            }
            await rag.apipeline_enqueue_documents(
                "paper body",
                file_paths="paper.pdf",
                process_options="!",
                document_metadata=metadata,
            )
            doc_id = compute_mdhash_id("paper.pdf", prefix="doc-")

            full_doc = await rag.full_docs.get_by_id(doc_id)
            pending = await rag.doc_status.get_by_id(doc_id)
            assert full_doc["document_metadata"] == metadata
            assert pending["metadata"]["document_metadata"] == metadata

            await rag.apipeline_process_enqueue_documents()

            processed = await rag.doc_status.get_by_id(doc_id)
            assert processed["status"] == "processed"
            assert processed["metadata"]["document_metadata"] == metadata
            assert processed["chunks_list"]
            chunk = await rag.text_chunks.get_by_id(processed["chunks_list"][0])
            assert chunk["document_metadata"] == metadata
        finally:
            await rag.finalize_storages()

    asyncio.run(_run())
