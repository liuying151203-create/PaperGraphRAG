"""Sequential, controlled Vector/Graph/Hybrid ablation runner."""

from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import UTC, datetime
from statistics import fmean
from typing import Any
from uuid import uuid4

from scholargraph.evaluation.metrics import FaithfulnessJudge, score_evaluation_result
from scholargraph.evaluation.models import (
    AblationConfig,
    EvaluationDataset,
    EvaluationMetrics,
    EvaluationModeSummary,
    EvaluationRecord,
    EvaluationRunSummary,
)
from scholargraph.evaluation.store import EvaluationStore
from scholargraph.retrieval import (
    EvidenceTrace,
    RetrievalStrategy,
    ScholarQueryRequest,
    ScholarRetrievalService,
)

DEFAULT_ABLATION_STRATEGIES = (
    RetrievalStrategy.VECTOR,
    RetrievalStrategy.GRAPH,
    RetrievalStrategy.HYBRID,
)


class EvaluationRunner:
    def __init__(
        self,
        retrieval: ScholarRetrievalService,
        store: EvaluationStore,
        *,
        faithfulness_judge: FaithfulnessJudge | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.store = store
        self.faithfulness_judge = faithfulness_judge

    async def run(
        self,
        dataset: EvaluationDataset,
        config: AblationConfig,
        *,
        strategies: Iterable[RetrievalStrategy] = DEFAULT_ABLATION_STRATEGIES,
        query_ids: set[str] | None = None,
    ) -> EvaluationRunSummary:
        run_id = _new_run_id()
        selected_questions = [
            question
            for question in dataset.questions
            if query_ids is None or question.query_id in query_ids
        ]
        records: list[EvaluationRecord] = []
        strategy_list = tuple(strategies)
        for question in selected_questions:
            for strategy in strategy_list:
                started = time.perf_counter()
                try:
                    response = await self.retrieval.query(
                        ScholarQueryRequest(
                            query=question.question,
                            strategy=strategy,
                            top_k=config.top_k,
                            chunk_top_k=config.chunk_top_k,
                            max_entity_tokens=config.max_entity_tokens,
                            max_relation_tokens=config.max_relation_tokens,
                            max_total_tokens=config.max_total_tokens,
                            enable_rerank=config.enable_rerank,
                            user_prompt=config.generation_prompt,
                            collection_key=config.collection_key,
                        )
                    )
                    metrics = (
                        await score_evaluation_result(
                            question,
                            response.answer,
                            response.evidence,
                            faithfulness_judge=self.faithfulness_judge,
                        )
                        if response.status == "success"
                        else EvaluationMetrics(
                            metric_notes=[
                                "query returned failure; metrics were not computed"
                            ]
                        )
                    )
                    record = EvaluationRecord(
                        run_id=run_id,
                        dataset_id=dataset.dataset_id,
                        query_id=question.query_id,
                        category=question.category,
                        retrieval_mode=strategy,
                        query=question.question,
                        answer=response.answer,
                        retrieved_evidence=response.evidence,
                        latency=round(time.perf_counter() - started, 3),
                        token_usage=_token_usage(response.metadata),
                        metrics=metrics,
                        status=response.status,
                        error=None if response.status == "success" else response.message,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve failed cell
                    record = EvaluationRecord(
                        run_id=run_id,
                        dataset_id=dataset.dataset_id,
                        query_id=question.query_id,
                        category=question.category,
                        retrieval_mode=strategy,
                        query=question.question,
                        answer="",
                        retrieved_evidence=EvidenceTrace(),
                        latency=round(time.perf_counter() - started, 3),
                        metrics=EvaluationMetrics(
                            metric_notes=["query failed; metrics were not computed"]
                        ),
                        status="failure",
                        error=str(exc),
                    )
                self.store.append(record)
                records.append(record)

        summary = _summarize_run(run_id, dataset, config, strategy_list, records)
        self.store.save_summary(summary)
        return summary


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"eval-{stamp}-{uuid4().hex[:8]}"


def _token_usage(metadata: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("token_usage", "usage"):
        value = metadata.get(key)
        if isinstance(value, dict):
            return value
    return None


def _summarize_run(
    run_id: str,
    dataset: EvaluationDataset,
    config: AblationConfig,
    strategies: tuple[RetrievalStrategy, ...],
    records: list[EvaluationRecord],
) -> EvaluationRunSummary:
    mode_summaries: list[EvaluationModeSummary] = []
    for strategy in strategies:
        mode_records = [record for record in records if record.retrieval_mode is strategy]
        completed = [record for record in mode_records if record.status == "success"]
        mode_summaries.append(
            EvaluationModeSummary(
                retrieval_mode=strategy,
                completed=len(completed),
                failed=len(mode_records) - len(completed),
                answer_correctness=_mean_metric(completed, "answer_correctness"),
                evidence_recall=_mean_metric(completed, "evidence_recall"),
                faithfulness=_mean_metric(completed, "faithfulness"),
                citation_validity=_mean_metric(completed, "citation_validity"),
                latency=round(fmean(record.latency for record in mode_records), 3)
                if mode_records
                else None,
            )
        )
    return EvaluationRunSummary(
        run_id=run_id,
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        config=config,
        modes=mode_summaries,
        record_count=len(records),
        failed_count=sum(record.status != "success" for record in records),
    )


def _mean_metric(records: list[EvaluationRecord], name: str) -> float | None:
    values = [getattr(record.metrics, name) for record in records]
    available = [value for value in values if value is not None]
    return round(fmean(available), 4) if available else None
