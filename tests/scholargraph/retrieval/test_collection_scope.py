from __future__ import annotations

import pytest

from lightrag.operate import (
    _attach_chunk_provenance,
    _filter_search_result_by_document_metadata,
)


class FakeChunkStorage:
    def __init__(self) -> None:
        self.rows = {
            "chunk-a": {
                "content": "Allowed",
                "document_metadata": {
                    "title": "Paper A",
                    "collection_keys": ["COLL-A", "COLL-SHARED"],
                },
                "page": 4,
            },
            "chunk-b": {
                "content": "Rejected",
                "document_metadata": {
                    "title": "Paper B",
                    "collection_keys": ["COLL-B"],
                },
            },
        }
        self.global_config = {"enable_content_headings": False}

    async def get_by_ids(self, ids):
        return [self.rows.get(chunk_id) for chunk_id in ids]


@pytest.mark.asyncio
async def test_collection_filter_applies_to_vector_and_graph_provenance() -> None:
    storage = FakeChunkStorage()
    result = await _filter_search_result_by_document_metadata(
        {
            "vector_chunks": [
                {"chunk_id": "chunk-a", "content": "Allowed"},
                {"chunk_id": "chunk-b", "content": "Rejected"},
            ],
            "final_entities": [
                {
                    "entity_name": "Shared method",
                    "source_id": "chunk-a<SEP>chunk-b",
                    "file_path": "a.pdf<SEP>b.pdf",
                }
            ],
            "final_relations": [
                {
                    "src_id": "Method",
                    "tgt_id": "Dataset",
                    "source_id": "chunk-b",
                    "file_path": "b.pdf",
                }
            ],
            "chunk_tracking": {"chunk-a": {}, "chunk-b": {}},
        },
        storage,  # type: ignore[arg-type]
        {"collection_keys": "COLL-A"},
    )

    assert [chunk["chunk_id"] for chunk in result["vector_chunks"]] == ["chunk-a"]
    assert result["final_entities"][0]["source_id"] == "chunk-a"
    assert result["final_entities"][0]["file_path"] == "a.pdf"
    assert result["final_relations"] == []
    assert set(result["chunk_tracking"]) == {"chunk-a"}


@pytest.mark.asyncio
async def test_chunk_provenance_attaches_metadata_without_rendering_it() -> None:
    storage = FakeChunkStorage()
    chunks = [{"chunk_id": "chunk-a", "content": "Allowed"}]

    await _attach_chunk_provenance(
        chunks,
        storage,  # type: ignore[arg-type]
        include_headings=False,
        include_document_metadata=True,
    )

    assert chunks[0]["document_metadata"]["title"] == "Paper A"
    assert chunks[0]["page"] == 4
