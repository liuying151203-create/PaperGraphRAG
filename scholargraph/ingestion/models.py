"""Validated metadata contracts for scientific-paper ingestion."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


class PaperMetadata(BaseModel):
    """Stable paper identity and citation metadata carried by LightRAG."""

    paper_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=2000)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1000, le=9999)
    doi: str | None = Field(default=None, max_length=512)
    source_path: str = Field(min_length=1, max_length=4096)
    zotero_item_key: str | None = Field(default=None, max_length=128)
    zotero_attachment_key: str | None = Field(default=None, max_length=128)
    collection_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "paper_id",
        "title",
        "source_path",
        "zotero_item_key",
        "zotero_attachment_key",
        mode="before",
    )
    @classmethod
    def _strip_scalar(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("authors", "collection_keys", "tags", mode="before")
    @classmethod
    def _normalize_authors(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise ValueError("metadata value must be a list of strings")  # noqa: TRY004
        authors: list[str] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("metadata lists must contain non-empty strings")
            author = raw.strip()
            if author not in seen:
                seen.add(author)
                authors.append(author)
        return authors

    @field_validator("doi", mode="before")
    @classmethod
    def _normalize_doi(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        doi = _DOI_PREFIX_RE.sub("", value.strip()).strip().lower()
        return doi or None

    def to_document_metadata(self) -> dict[str, object]:
        """Return the JSON-ready payload accepted by LightRAG ingestion."""
        return self.model_dump(exclude_none=True, mode="json")


class PaperIngestionReceipt(BaseModel):
    """Identifiers needed to track a scientific-paper ingestion run."""

    track_id: str
    document_id: str
    file_path: str
    parse_engine: str
    process_options: str

    model_config = ConfigDict(frozen=True)
