from __future__ import annotations

import pytest

from scholargraph.retrieval import (
    RetrievalStrategy,
    ScholarQueryRequest,
    ScholarRetrievalService,
)


class FakeRag:
    def __init__(self) -> None:
        self.params = []

    async def aquery_llm(self, query, param):
        self.params.append((query, param))
        return {
            "status": "success",
            "message": "Query processed successfully",
            "data": {
                "references": [
                    {"reference_id": "1", "file_path": "ATTACHAB.pdf"}
                ],
                "chunks": [
                    {
                        "reference_id": "1",
                        "chunk_id": "chunk-1",
                        "file_path": "ATTACHAB.pdf",
                        "content": "MetaGraph is evaluated on ACM.",
                        "distance": 0.87,
                        "content_headings": ["Experiments", "Datasets"],
                        "page": 7,
                        "document_metadata": {
                            "paper_id": "PAPERABC",
                            "title": "MetaGraph",
                            "authors": ["Ada Lovelace"],
                            "year": 2025,
                            "doi": "10.1000/metagraph",
                            "zotero_item_key": "PAPERABC",
                            "zotero_attachment_key": "ATTACHAB",
                        },
                    }
                ],
                "entities": [
                    {
                        "entity_name": "MetaGraph",
                        "entity_type": "method",
                        "description": "A graph method",
                        "source_id": "chunk-1",
                        "file_path": "ATTACHAB.pdf",
                    }
                ],
                "relationships": [
                    {
                        "src_id": "MetaGraph",
                        "tgt_id": "ACM",
                        "keywords": "EVALUATED_ON",
                        "description": "Evaluated on ACM",
                        "weight": 1.0,
                        "source_id": "chunk-1",
                        "file_path": "ATTACHAB.pdf",
                    }
                ],
            },
            "metadata": {"query_mode": param.mode},
            "llm_response": {
                "content": "MetaGraph was evaluated on ACM [1].",
                "is_streaming": False,
            },
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy", "expected_mode"),
    [
        (RetrievalStrategy.VECTOR, "naive"),
        (RetrievalStrategy.GRAPH, "hybrid"),
        (RetrievalStrategy.HYBRID, "mix"),
    ],
)
async def test_strategy_mapping_and_single_pass_evidence(
    strategy: RetrievalStrategy, expected_mode: str
) -> None:
    rag = FakeRag()
    response = await ScholarRetrievalService(rag).query(  # type: ignore[arg-type]
        ScholarQueryRequest(query="Which dataset is used?", strategy=strategy)
    )

    assert len(rag.params) == 1
    assert rag.params[0][1].mode == expected_mode
    assert response.answer == "MetaGraph was evaluated on ACM [1]."
    assert response.strategy is strategy
    assert response.lightrag_mode == expected_mode
    assert response.evidence.sources[0].title == "MetaGraph"
    assert response.evidence.sources[0].zotero_item_key == "PAPERABC"
    assert response.evidence.vector[0].score == 0.87
    assert response.evidence.vector[0].section == "Experiments / Datasets"
    assert response.evidence.vector[0].page == 7
    assert response.evidence.entities[0].entity_type == "method"
    assert response.evidence.relations[0].relation == "EVALUATED_ON"
    assert response.response_time >= 0


@pytest.mark.asyncio
async def test_missing_answer_uses_explicit_fallback() -> None:
    class EmptyRag:
        async def aquery_llm(self, query, param):
            return {
                "status": "failure",
                "message": "no results",
                "data": {},
                "metadata": {},
                "llm_response": {"content": None},
            }

    response = await ScholarRetrievalService(EmptyRag()).query(  # type: ignore[arg-type]
        ScholarQueryRequest(query="Unknown scientific question")
    )

    assert response.status == "failure"
    assert response.answer == "No relevant context found for the query."
    assert response.evidence.sources == []


@pytest.mark.asyncio
async def test_collection_scope_maps_to_document_metadata_filter() -> None:
    rag = FakeRag()
    await ScholarRetrievalService(rag).query(  # type: ignore[arg-type]
        ScholarQueryRequest(
            query="Which dataset is used?",
            collection_key="COLLECT1",
        )
    )

    param = rag.params[0][1]
    assert param.include_document_metadata is True
    assert param.document_metadata_filter == {"collection_keys": "COLLECT1"}
