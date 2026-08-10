"""Frontend-stable retrieval and evidence contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lightrag.constants import MAX_QUERY_CHARS, MAX_QUERY_TOKEN_BUDGET, MAX_QUERY_TOP_K


class RetrievalStrategy(StrEnum):
    """ScholarGraph strategies independent of LightRAG's internal mode names."""

    VECTOR = "VECTOR"
    GRAPH = "GRAPH"
    HYBRID = "HYBRID"


STRATEGY_MODE = {
    RetrievalStrategy.VECTOR: "naive",
    RetrievalStrategy.GRAPH: "hybrid",
    RetrievalStrategy.HYBRID: "mix",
}


class ScholarQueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=MAX_QUERY_CHARS)
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = Field(default=40, ge=1, le=MAX_QUERY_TOP_K)
    chunk_top_k: int = Field(default=20, ge=1, le=MAX_QUERY_TOP_K)
    max_entity_tokens: int = Field(
        default=6000, ge=1, le=MAX_QUERY_TOKEN_BUDGET
    )
    max_relation_tokens: int = Field(
        default=8000, ge=1, le=MAX_QUERY_TOKEN_BUDGET
    )
    max_total_tokens: int = Field(
        default=30000, ge=1, le=MAX_QUERY_TOKEN_BUDGET
    )
    enable_rerank: bool = True
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    user_prompt: str | None = Field(default=None, max_length=MAX_QUERY_CHARS)
    collection_key: str | None = Field(default=None, min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class EvidenceSource(BaseModel):
    reference_id: str
    file_path: str
    paper_id: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    zotero_item_key: str | None = None
    zotero_attachment_key: str | None = None


class VectorEvidence(BaseModel):
    reference_id: str
    chunk_id: str
    file_path: str
    content: str
    score: float | None = None
    section: str | None = None
    page: int | str | None = None
    paper: EvidenceSource | None = None


class GraphEntityEvidence(BaseModel):
    entity_name: str
    entity_type: str
    description: str = ""
    source_id: str = ""
    file_path: str = "unknown_source"


class GraphRelationEvidence(BaseModel):
    source: str
    target: str
    relation: str
    description: str = ""
    weight: float = 1.0
    source_id: str = ""
    file_path: str = "unknown_source"


class EvidenceTrace(BaseModel):
    sources: list[EvidenceSource] = Field(default_factory=list)
    vector: list[VectorEvidence] = Field(default_factory=list)
    entities: list[GraphEntityEvidence] = Field(default_factory=list)
    relations: list[GraphRelationEvidence] = Field(default_factory=list)


class ScholarQueryResponse(BaseModel):
    status: str
    message: str
    answer: str
    strategy: RetrievalStrategy
    lightrag_mode: str
    evidence: EvidenceTrace
    response_time: float
    metadata: dict[str, Any] = Field(default_factory=dict)
