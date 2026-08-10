"""Append-only evaluation records and compact run summaries."""

from __future__ import annotations

import json
from pathlib import Path

from scholargraph.evaluation.models import EvaluationRecord, EvaluationRunSummary


class EvaluationStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, record: EvaluationRecord) -> None:
        path = self.root / f"{record.run_id}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(record.model_dump_json() + "\n")

    def save_summary(self, summary: EvaluationRunSummary) -> None:
        path = self.root / f"{summary.run_id}.summary.json"
        temporary = path.with_suffix(".summary.json.tmp")
        temporary.write_text(
            summary.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def list_summaries(self) -> list[EvaluationRunSummary]:
        summaries = [
            EvaluationRunSummary.model_validate_json(path.read_text(encoding="utf-8"))
            for path in self.root.glob("*.summary.json")
        ]
        return sorted(summaries, key=lambda item: item.created_at, reverse=True)

    def get_summary(self, run_id: str) -> EvaluationRunSummary | None:
        path = self.root / f"{_safe_run_id(run_id)}.summary.json"
        if not path.exists():
            return None
        return EvaluationRunSummary.model_validate_json(path.read_text(encoding="utf-8"))

    def get_records(self, run_id: str) -> list[EvaluationRecord]:
        path = self.root / f"{_safe_run_id(run_id)}.jsonl"
        if not path.exists():
            return []
        records: list[EvaluationRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(EvaluationRecord.model_validate(json.loads(line)))
        return records


def _safe_run_id(run_id: str) -> str:
    if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in run_id.lower()):
        raise ValueError("invalid evaluation run id")
    return run_id

