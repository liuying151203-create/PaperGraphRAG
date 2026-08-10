"""Canonical academic relationship ontology and validation."""

from __future__ import annotations

import re
from enum import Enum

from scholargraph.academic.schema import AcademicEntityType


class AcademicRelation(str, Enum):
    PROPOSES = "PROPOSES"
    ADDRESSES = "ADDRESSES"
    EVALUATED_ON = "EVALUATED_ON"
    USES_METRIC = "USES_METRIC"
    BASED_ON = "BASED_ON"
    COMPARES_WITH = "COMPARES_WITH"
    OUTPERFORMS = "OUTPERFORMS"
    ATTACKS = "ATTACKS"
    DEFENDS_AGAINST = "DEFENDS_AGAINST"
    CITES = "CITES"


RELATION_SIGNATURES: dict[
    AcademicRelation, tuple[AcademicEntityType, AcademicEntityType]
] = {
    AcademicRelation.PROPOSES: (AcademicEntityType.PAPER, AcademicEntityType.METHOD),
    AcademicRelation.ADDRESSES: (AcademicEntityType.METHOD, AcademicEntityType.TASK),
    AcademicRelation.EVALUATED_ON: (
        AcademicEntityType.METHOD,
        AcademicEntityType.DATASET,
    ),
    AcademicRelation.USES_METRIC: (
        AcademicEntityType.METHOD,
        AcademicEntityType.METRIC,
    ),
    AcademicRelation.BASED_ON: (AcademicEntityType.METHOD, AcademicEntityType.MODEL),
    AcademicRelation.COMPARES_WITH: (
        AcademicEntityType.METHOD,
        AcademicEntityType.METHOD,
    ),
    AcademicRelation.OUTPERFORMS: (
        AcademicEntityType.METHOD,
        AcademicEntityType.METHOD,
    ),
    AcademicRelation.ATTACKS: (AcademicEntityType.ATTACK, AcademicEntityType.MODEL),
    AcademicRelation.DEFENDS_AGAINST: (
        AcademicEntityType.DEFENSE,
        AcademicEntityType.ATTACK,
    ),
    AcademicRelation.CITES: (AcademicEntityType.PAPER, AcademicEntityType.PAPER),
}


_RELATION_ALIASES: dict[AcademicRelation, tuple[str, ...]] = {
    AcademicRelation.PROPOSES: ("proposes", "introduced", "introduces", "presents"),
    AcademicRelation.ADDRESSES: ("addresses", "solves", "designed for"),
    AcademicRelation.EVALUATED_ON: (
        "evaluated on",
        "experimented on",
        "benchmarked on",
        "benchmark on",
        "tested on",
    ),
    AcademicRelation.USES_METRIC: (
        "uses metric",
        "evaluated using",
        "measured by",
        "scored by",
    ),
    AcademicRelation.BASED_ON: ("based on", "builds on", "derived from", "extends"),
    AcademicRelation.COMPARES_WITH: (
        "compares with",
        "compared with",
        "compared against",
        "baseline comparison",
    ),
    AcademicRelation.OUTPERFORMS: (
        "outperforms",
        "outperformed",
        "surpasses",
        "improves upon",
    ),
    AcademicRelation.ATTACKS: ("attacks", "compromises"),
    AcademicRelation.DEFENDS_AGAINST: (
        "defends against",
        "defence against",
        "mitigates",
        "robust against",
        "protects from",
    ),
    AcademicRelation.CITES: ("cites", "references"),
}


def normalize_relation_keyword(value: object) -> AcademicRelation | None:
    """Return a canonical relation for a known extracted phrase."""

    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    if not text:
        return None

    enum_candidate = text.upper().replace(" ", "_")
    try:
        return AcademicRelation(enum_candidate)
    except ValueError:
        pass

    for relation, aliases in _RELATION_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
                return relation
    return None


def validate_relation_signature(
    relation: AcademicRelation,
    source_type: AcademicEntityType,
    target_type: AcademicEntityType,
    *,
    allow_reverse: bool = True,
) -> bool:
    """Validate endpoint types against the v1 ontology.

    ``allow_reverse`` defaults to true because LightRAG's current graph merge
    treats relationships as undirected and sorts endpoint keys.
    """

    expected = RELATION_SIGNATURES[relation]
    actual = (source_type, target_type)
    return actual == expected or (allow_reverse and actual == tuple(reversed(expected)))
