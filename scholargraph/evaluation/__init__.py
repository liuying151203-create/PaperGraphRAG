"""ScholarGraph evaluation and ablation toolkit."""

from scholargraph.evaluation.dataset import (
    DEFAULT_DATASET_PATH,
    load_evaluation_dataset,
)
from scholargraph.evaluation.metrics import FaithfulnessJudge, score_evaluation_result
from scholargraph.evaluation.models import (
    AblationConfig,
    EvaluationDataset,
    EvaluationMetrics,
    EvaluationModeSummary,
    EvaluationPaper,
    EvaluationQuestion,
    EvaluationRecord,
    EvaluationRunSummary,
    QuestionCategory,
)
from scholargraph.evaluation.runner import DEFAULT_ABLATION_STRATEGIES, EvaluationRunner
from scholargraph.evaluation.store import EvaluationStore

__all__ = [
    "DEFAULT_ABLATION_STRATEGIES",
    "DEFAULT_DATASET_PATH",
    "AblationConfig",
    "EvaluationDataset",
    "EvaluationMetrics",
    "EvaluationModeSummary",
    "EvaluationPaper",
    "EvaluationQuestion",
    "EvaluationRecord",
    "EvaluationRunSummary",
    "EvaluationRunner",
    "EvaluationStore",
    "FaithfulnessJudge",
    "QuestionCategory",
    "load_evaluation_dataset",
    "score_evaluation_result",
]
