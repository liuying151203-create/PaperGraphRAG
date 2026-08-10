"""Validated contracts for reproducible ScholarGraph ablation runs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scholargraph.retrieval import EvidenceTrace, RetrievalStrategy


class QuestionCategory(StrEnum):
    FACT = "fact"
    CROSS_DOCUMENT = "cross_document"
    DATASET = "dataset"
    METHOD = "method"
    RELATION = "relation"
    MULTI_HOP = "multi_hop"


class EvaluationPaper(BaseModel):
    paper_id: str
    title: str
    authors: list[str]
    year: int
    source_url: str
    pdf_url: str
    filename: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationQuestion(BaseModel):
    query_id: str
    question: str
    category: QuestionCategory
    reference_answer: str
    expected_answer_terms: list[list[str]] = Field(default_factory=list)
    expected_evidence_terms: list[list[str]] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationDataset(BaseModel):
    dataset_id: str
    version: str
    description: str
    papers: list[EvaluationPaper]
    questions: list[EvaluationQuestion]

    model_config = ConfigDict(extra="forbid", frozen=True)


class AblationConfig(BaseModel):
    top_k: int = Field(default=40, ge=1)
    chunk_top_k: int = Field(default=20, ge=1)
    max_entity_tokens: int = Field(default=6000, ge=1)
    max_relation_tokens: int = Field(default=8000, ge=1)
    max_total_tokens: int = Field(default=30000, ge=1)
    enable_rerank: bool = False
    generation_prompt: str = (
        "Answer the evaluation question using only retrieved evidence. "
        "Cite source reference ids in square brackets."
    )
    llm_id: str = "configured-query-role"
    embedding_id: str = "configured-embedding"
    collection_key: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationMetrics(BaseModel):
    answer_correctness: float | None = None
    evidence_recall: float | None = None
    faithfulness: float | None = None
    citation_validity: float | None = None
    metric_notes: list[str] = Field(default_factory=list)


class EvaluationRecord(BaseModel):
    run_id: str
    dataset_id: str
    query_id: str
    category: QuestionCategory
    retrieval_mode: RetrievalStrategy
    query: str
    answer: str
    retrieved_evidence: EvidenceTrace = Field(default_factory=EvidenceTrace)
    latency: float
    token_usage: dict[str, Any] | None = None
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    status: str = "success"
    error: str | None = None


class EvaluationModeSummary(BaseModel):
    retrieval_mode: RetrievalStrategy
    completed: int
    failed: int
    answer_correctness: float | None
    evidence_recall: float | None
    faithfulness: float | None
    citation_validity: float | None
    latency: float | None


class EvaluationRunSummary(BaseModel):
    run_id: str
    dataset_id: str
    dataset_version: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    config: AblationConfig
    modes: list[EvaluationModeSummary]
    record_count: int
    failed_count: int

