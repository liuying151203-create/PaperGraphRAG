"""Single-pass ScholarGraph query adapter over LightRAG."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lightrag.base import QueryParam
from scholargraph.retrieval.models import (
    STRATEGY_MODE,
    EvidenceSource,
    EvidenceTrace,
    GraphEntityEvidence,
    GraphRelationEvidence,
    ScholarQueryRequest,
    ScholarQueryResponse,
    VectorEvidence,
)

if TYPE_CHECKING:
    from lightrag import LightRAG


class ScholarRetrievalService:
    """Map stable strategies and expose LightRAG's existing raw evidence."""

    def __init__(self, rag: LightRAG) -> None:
        self.rag = rag

    async def query(self, request: ScholarQueryRequest) -> ScholarQueryResponse:
        mode = STRATEGY_MODE[request.strategy]
        param = QueryParam(
            mode=mode,  # type: ignore[arg-type]
            stream=False,
            top_k=request.top_k,
            chunk_top_k=request.chunk_top_k,
            max_entity_tokens=request.max_entity_tokens,
            max_relation_tokens=request.max_relation_tokens,
            max_total_tokens=request.max_total_tokens,
            enable_rerank=request.enable_rerank,
            conversation_history=request.conversation_history,
            user_prompt=request.user_prompt,
            include_document_metadata=True,
            document_metadata_filter={"collection_keys": request.collection_key}
            if request.collection_key
            else None,
        )
        started = time.perf_counter()
        raw = await self.rag.aquery_llm(request.query.strip(), param=param)
        elapsed = round(time.perf_counter() - started, 3)
        data = raw.get("data") if isinstance(raw, dict) else None
        data = data if isinstance(data, dict) else {}
        llm_response = raw.get("llm_response") if isinstance(raw, dict) else None
        llm_response = llm_response if isinstance(llm_response, dict) else {}
        answer = llm_response.get("content")
        if not isinstance(answer, str) or not answer:
            answer = "No relevant context found for the query."

        return ScholarQueryResponse(
            status=str(raw.get("status", "failure")),
            message=str(raw.get("message", "Query returned no result")),
            answer=answer,
            strategy=request.strategy,
            lightrag_mode=mode,
            evidence=_build_evidence(data),
            response_time=elapsed,
            metadata=raw.get("metadata", {})
            if isinstance(raw.get("metadata"), dict)
            else {},
        )


def _build_evidence(data: dict[str, Any]) -> EvidenceTrace:
    chunks = [item for item in data.get("chunks", []) if isinstance(item, dict)]
    references = [
        item for item in data.get("references", []) if isinstance(item, dict)
    ]
    source_by_reference: dict[str, EvidenceSource] = {}
    for reference in references:
        reference_id = str(reference.get("reference_id", ""))
        source_by_reference[reference_id] = EvidenceSource(
            reference_id=reference_id,
            file_path=str(reference.get("file_path", "unknown_source")),
        )

    vector_evidence: list[VectorEvidence] = []
    for chunk in chunks:
        reference_id = str(chunk.get("reference_id", ""))
        metadata = chunk.get("document_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        file_path = str(chunk.get("file_path", "unknown_source"))
        paper_source = EvidenceSource(
            reference_id=reference_id,
            file_path=file_path,
            paper_id=_optional_str(metadata.get("paper_id")),
            title=_optional_str(metadata.get("title")),
            authors=[str(value) for value in metadata.get("authors", [])]
            if isinstance(metadata.get("authors"), list)
            else [],
            year=_optional_int(metadata.get("year")),
            doi=_optional_str(metadata.get("doi")),
            zotero_item_key=_optional_str(metadata.get("zotero_item_key")),
            zotero_attachment_key=_optional_str(
                metadata.get("zotero_attachment_key")
            ),
        )
        existing = source_by_reference.get(reference_id)
        if existing is None or paper_source.title:
            source_by_reference[reference_id] = paper_source
        score = chunk.get("distance")
        vector_evidence.append(
            VectorEvidence(
                reference_id=reference_id,
                chunk_id=str(chunk.get("chunk_id", "")),
                file_path=file_path,
                content=str(chunk.get("content", "")),
                score=float(score) if isinstance(score, (int, float)) else None,
                section=_chunk_section(chunk),
                page=chunk.get("page")
                if isinstance(chunk.get("page"), (int, str))
                else None,
                paper=paper_source,
            )
        )

    entities = [
        GraphEntityEvidence(
            entity_name=str(item.get("entity_name", "")),
            entity_type=str(item.get("entity_type", "UNKNOWN")),
            description=str(item.get("description", "")),
            source_id=str(item.get("source_id", "")),
            file_path=str(item.get("file_path", "unknown_source")),
        )
        for item in data.get("entities", [])
        if isinstance(item, dict)
    ]
    relations = [
        GraphRelationEvidence(
            source=str(item.get("src_id", "")),
            target=str(item.get("tgt_id", "")),
            relation=str(item.get("keywords", "")),
            description=str(item.get("description", "")),
            weight=float(item.get("weight", 1.0)),
            source_id=str(item.get("source_id", "")),
            file_path=str(item.get("file_path", "unknown_source")),
        )
        for item in data.get("relationships", [])
        if isinstance(item, dict)
    ]
    return EvidenceTrace(
        sources=list(source_by_reference.values()),
        vector=vector_evidence,
        entities=entities,
        relations=relations,
    )


def _chunk_section(chunk: dict[str, Any]) -> str | None:
    section = chunk.get("section")
    if isinstance(section, str) and section:
        return section
    headings = chunk.get("content_headings")
    if isinstance(headings, list) and headings:
        return " / ".join(str(value) for value in headings)
    if isinstance(headings, str) and headings:
        return headings
    return None


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
