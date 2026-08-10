from __future__ import annotations

import pytest

from scholargraph.evaluation import (
    EvaluationQuestion,
    QuestionCategory,
    score_evaluation_result,
)
from scholargraph.retrieval import EvidenceSource, EvidenceTrace, VectorEvidence


@pytest.mark.asyncio
async def test_metrics_are_transparent_and_do_not_invent_faithfulness() -> None:
    question = EvaluationQuestion(
        query_id="q1",
        question="How?",
        category=QuestionCategory.FACT,
        reference_answer="Uses attention on neighbors.",
        expected_answer_terms=[["attention"], ["neighbor", "neighbour"]],
        expected_evidence_terms=[["paper-a"], ["masked attention"]],
    )
    evidence = EvidenceTrace(
        sources=[EvidenceSource(reference_id="1", file_path="paper-a.pdf")],
        vector=[
            VectorEvidence(
                reference_id="1",
                chunk_id="chunk-1",
                file_path="paper-a.pdf",
                content="The method uses masked attention.",
            )
        ],
    )

    metrics = await score_evaluation_result(
        question,
        "It uses attention over every neighbor [1] and cites an absent source [9].",
        evidence,
    )

    assert metrics.answer_correctness == 1.0
    assert metrics.evidence_recall == 1.0
    assert metrics.citation_validity == 0.5
    assert metrics.faithfulness is None
    assert "no judge" in metrics.metric_notes[1]


@pytest.mark.asyncio
async def test_optional_faithfulness_judge_is_recorded() -> None:
    class Judge:
        async def score(self, answer, evidence):
            return 0.75

    question = EvaluationQuestion(
        query_id="q1",
        question="How?",
        category=QuestionCategory.FACT,
        reference_answer="Answer",
    )
    metrics = await score_evaluation_result(
        question,
        "Answer",
        EvidenceTrace(),
        faithfulness_judge=Judge(),
    )

    assert metrics.faithfulness == 0.75

