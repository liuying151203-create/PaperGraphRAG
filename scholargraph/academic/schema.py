"""Academic entity types used by ScholarGraph."""

from __future__ import annotations

from enum import Enum


class AcademicEntityType(str, Enum):
    PAPER = "Paper"
    METHOD = "Method"
    TASK = "Task"
    DATASET = "Dataset"
    METRIC = "Metric"
    MODEL = "Model"
    CONCEPT = "Concept"
    ATTACK = "Attack"
    DEFENSE = "Defense"

    @property
    def storage_value(self) -> str:
        """Return LightRAG's normalized lower-case entity type."""

        return self.value.lower()


_ENTITY_TYPE_ALIASES: dict[str, AcademicEntityType] = {
    "paper": AcademicEntityType.PAPER,
    "article": AcademicEntityType.PAPER,
    "publication": AcademicEntityType.PAPER,
    "method": AcademicEntityType.METHOD,
    "approach": AcademicEntityType.METHOD,
    "algorithm": AcademicEntityType.METHOD,
    "technique": AcademicEntityType.METHOD,
    "task": AcademicEntityType.TASK,
    "problem": AcademicEntityType.TASK,
    "dataset": AcademicEntityType.DATASET,
    "data set": AcademicEntityType.DATASET,
    "corpus": AcademicEntityType.DATASET,
    "benchmark": AcademicEntityType.DATASET,
    "metric": AcademicEntityType.METRIC,
    "measure": AcademicEntityType.METRIC,
    "evaluation metric": AcademicEntityType.METRIC,
    "model": AcademicEntityType.MODEL,
    "architecture": AcademicEntityType.MODEL,
    "framework": AcademicEntityType.MODEL,
    "concept": AcademicEntityType.CONCEPT,
    "theory": AcademicEntityType.CONCEPT,
    "principle": AcademicEntityType.CONCEPT,
    "attack": AcademicEntityType.ATTACK,
    "threat": AcademicEntityType.ATTACK,
    "adversarial attack": AcademicEntityType.ATTACK,
    "defense": AcademicEntityType.DEFENSE,
    "defence": AcademicEntityType.DEFENSE,
    "mitigation": AcademicEntityType.DEFENSE,
    "countermeasure": AcademicEntityType.DEFENSE,
}


def normalize_entity_type(value: object) -> AcademicEntityType:
    """Map an extracted label to the academic schema.

    Unknown LLM labels fall back to ``Concept``. LightRAG-injected structural
    entities (drawing/table/equation) are handled separately by the adapter.
    """

    normalized = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    return _ENTITY_TYPE_ALIASES.get(normalized, AcademicEntityType.CONCEPT)


ACADEMIC_ENTITY_TYPES_GUIDANCE = """Classify each academic entity using exactly one of these types:

- Paper: A scholarly paper, article, preprint, or publication
- Method: A proposed method, algorithm, technique, or approach
- Task: A research problem or prediction/reasoning task
- Dataset: A named dataset, corpus, or evaluation benchmark
- Metric: A named quantitative evaluation measure
- Model: A model, architecture, framework, or system used by a method
- Concept: A scientific concept, theory, principle, or topic
- Attack: An adversarial attack or threat technique
- Defense: A defense, mitigation, or countermeasure

Use Concept only when none of the more specific types applies. For relationship
keywords, prefer these canonical labels when supported by the text: PROPOSES,
ADDRESSES, EVALUATED_ON, USES_METRIC, BASED_ON, COMPARES_WITH, OUTPERFORMS,
ATTACKS, DEFENDS_AGAINST, CITES."""
