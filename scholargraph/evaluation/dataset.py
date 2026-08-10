"""Load the checked-in ScholarGraph development evaluation dataset."""

from __future__ import annotations

import json
from pathlib import Path

from scholargraph.evaluation.models import EvaluationDataset

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "scholargraph"
    / "evaluation"
    / "graph_rag_dev_v1.json"
)


def load_evaluation_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> EvaluationDataset:
    """Load and validate one immutable evaluation manifest."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    dataset = EvaluationDataset.model_validate(payload)
    paper_ids = [paper.paper_id for paper in dataset.papers]
    query_ids = [question.query_id for question in dataset.questions]
    if len(paper_ids) != len(set(paper_ids)):
        raise ValueError("evaluation dataset contains duplicate paper_id values")
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("evaluation dataset contains duplicate query_id values")
    if not 5 <= len(dataset.papers) <= 10:
        raise ValueError("development dataset must contain 5 to 10 papers")
    return dataset

