"""Transparent deterministic metrics plus an optional faithfulness judge."""

from __future__ import annotations

import re
from typing import Protocol

from scholargraph.evaluation.models import EvaluationMetrics, EvaluationQuestion
from scholargraph.retrieval import EvidenceTrace


class FaithfulnessJudge(Protocol):
    async def score(self, answer: str, evidence: EvidenceTrace) -> float | None: ...


async def score_evaluation_result(
    question: EvaluationQuestion,
    answer: str,
    evidence: EvidenceTrace,
    *,
    faithfulness_judge: FaithfulnessJudge | None = None,
) -> EvaluationMetrics:
    """Score explicit lexical expectations without inventing semantic grades."""
    notes = [
        "answer_correctness is deterministic expected-term coverage, not an LLM judge"
    ]
    correctness = _group_recall(answer, question.expected_answer_terms)
    evidence_text = _evidence_text(evidence)
    evidence_recall = _group_recall(evidence_text, question.expected_evidence_terms)
    citation_validity = _citation_validity(answer, evidence)
    faithfulness = None
    if faithfulness_judge is not None:
        faithfulness = await faithfulness_judge.score(answer, evidence)
    else:
        notes.append("faithfulness is unavailable because no judge was configured")
    return EvaluationMetrics(
        answer_correctness=correctness,
        evidence_recall=evidence_recall,
        faithfulness=faithfulness,
        citation_validity=citation_validity,
        metric_notes=notes,
    )


def _group_recall(text: str, expected_groups: list[list[str]]) -> float | None:
    if not expected_groups:
        return None
    normalized = _normalize(text)
    matched = sum(
        any(_normalize(alternative) in normalized for alternative in group)
        for group in expected_groups
    )
    return round(matched / len(expected_groups), 4)


def _citation_validity(answer: str, evidence: EvidenceTrace) -> float | None:
    citations = re.findall(r"\[(\d+)\]", answer)
    if not citations:
        return None
    valid_ids = {source.reference_id for source in evidence.sources}
    return round(sum(citation in valid_ids for citation in citations) / len(citations), 4)


def _evidence_text(evidence: EvidenceTrace) -> str:
    values: list[str] = []
    for source in evidence.sources:
        values.extend([source.file_path, source.title or "", source.paper_id or ""])
    for chunk in evidence.vector:
        values.extend([chunk.content, chunk.file_path, chunk.section or ""])
    for entity in evidence.entities:
        values.extend([entity.entity_name, entity.entity_type, entity.description])
    for relation in evidence.relations:
        values.extend(
            [relation.source, relation.target, relation.relation, relation.description]
        )
    return "\n".join(values)


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())

