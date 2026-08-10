"""Data contracts for read-only Zotero synchronization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class IndexStatus(StrEnum):
    """Lifecycle state of one Zotero attachment in the derived index."""

    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    EXCLUDED = "excluded"


class SyncAction(StrEnum):
    """Observable action performed for one attachment mapping."""

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    SKIP = "skip"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ZoteroServerInfo:
    """Identity and protocol information for one local Zotero instance."""

    api_version: int
    server_id: str | None


@dataclass(frozen=True, slots=True)
class ZoteroAttachment:
    """A Zotero child attachment that may provide a paper PDF."""

    key: str
    version: int
    parent_item_key: str
    title: str
    content_type: str
    link_mode: str
    filename: str
    md5: str | None = None

    @property
    def is_pdf(self) -> bool:
        """Return whether the attachment is a file-backed PDF."""
        return self.content_type.lower() == "application/pdf" and self.link_mode in {
            "imported_file",
            "imported_url",
            "linked_file",
        }


@dataclass(frozen=True, slots=True)
class ZoteroPaper:
    """Bibliographic fields required by ScholarGraph ingestion and UI."""

    key: str
    version: int
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    doi: str | None = None
    collections: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ZoteroChanges:
    """One consistent version-window response from the Zotero Local API."""

    library_version: int
    items: tuple[dict[str, object], ...]
    deleted_item_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ZoteroMapping:
    """Persistent mapping from a Zotero PDF attachment to a RAG document."""

    item_key: str
    attachment_key: str
    zotero_version: int
    item_version: int
    attachment_version: int
    rag_document_id: str | None
    pdf_path: Path
    pdf_hash: str | None
    metadata_hash: str | None
    index_status: IndexStatus
    last_sync_time: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ZoteroSyncState:
    """Committed version checkpoint for one Zotero library."""

    library_key: str
    server_id: str | None
    library_version: int
    last_sync_time: str


@dataclass(frozen=True, slots=True)
class SyncEvent:
    """Per-attachment result emitted by a synchronization run."""

    action: SyncAction
    item_key: str
    attachment_key: str
    rag_document_id: str | None = None
    message: str | None = None


@dataclass(slots=True)
class SyncReport:
    """Summary of a complete version-based polling run."""

    previous_version: int
    observed_version: int
    committed_version: int
    events: list[SyncEvent] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return all(event.action is not SyncAction.FAIL for event in self.events)

    def count(self, action: SyncAction) -> int:
        return sum(event.action is action for event in self.events)
