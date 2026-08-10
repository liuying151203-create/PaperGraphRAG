from __future__ import annotations

from pathlib import Path

import pytest

from scholargraph.evaluation import (
    AblationConfig,
    EvaluationRunner,
    EvaluationStore,
    load_evaluation_dataset,
)
from scholargraph.retrieval import (
    EvidenceSource,
    EvidenceTrace,
    ScholarQueryResponse,
    VectorEvidence,
)


class FakeRetrieval:
    def __init__(self) -> None:
        self.requests = []

    async def query(self, request):
        self.requests.append(request)
        return ScholarQueryResponse(
            status="success",
            message="ok",
            answer="Graph Attention Networks use masked self-attentional layers for neighbor importance [1].",
            strategy=request.strategy,
            lightrag_mode="naive",
            evidence=EvidenceTrace(
                sources=[
                    EvidenceSource(
                        reference_id="1",
                        file_path="1710.10903_gat.pdf",
                        title="Graph Attention Networks",
                    )
                ],
                vector=[
                    VectorEvidence(
                        reference_id="1",
                        chunk_id="chunk-1",
                        file_path="1710.10903_gat.pdf",
                        content="Masked self-attentional layers weight neighboring nodes.",
                    )
                ],
            ),
            response_time=0.01,
            metadata={"token_usage": {"total_tokens": 42}},
        )


@pytest.mark.asyncio
async def test_runner_controls_all_three_modes_and_persists_records(tmp_path: Path) -> None:
    dataset = load_evaluation_dataset()
    retrieval = FakeRetrieval()
    store = EvaluationStore(tmp_path)
    config = AblationConfig(top_k=12, chunk_top_k=6, enable_rerank=False)

    summary = await EvaluationRunner(  # type: ignore[arg-type]
        retrieval, store
    ).run(dataset, config, query_ids={"fact-gat-attention"})

    assert [request.strategy.value for request in retrieval.requests] == [
        "VECTOR",
        "GRAPH",
        "HYBRID",
    ]
    assert all(request.top_k == 12 for request in retrieval.requests)
    assert all(request.chunk_top_k == 6 for request in retrieval.requests)
    assert all(request.user_prompt == config.generation_prompt for request in retrieval.requests)
    assert summary.record_count == 3
    assert summary.failed_count == 0
    assert {mode.retrieval_mode.value for mode in summary.modes} == {
        "VECTOR",
        "GRAPH",
        "HYBRID",
    }
    records = store.get_records(summary.run_id)
    assert len(records) == 3
    assert all(record.token_usage == {"total_tokens": 42} for record in records)
    assert store.get_summary(summary.run_id) == summary


@pytest.mark.asyncio
async def test_runner_records_failed_cells_without_fabricating_metrics(tmp_path: Path) -> None:
    class FailingRetrieval:
        async def query(self, request):
            raise RuntimeError("provider unavailable")

    dataset = load_evaluation_dataset()
    store = EvaluationStore(tmp_path)
    summary = await EvaluationRunner(  # type: ignore[arg-type]
        FailingRetrieval(), store
    ).run(dataset, AblationConfig(), query_ids={"fact-gat-attention"})

    assert summary.failed_count == 3
    records = store.get_records(summary.run_id)
    assert all(record.answer == "" for record in records)
    assert all(record.metrics.answer_correctness is None for record in records)
    assert all(record.error == "provider unavailable" for record in records)

