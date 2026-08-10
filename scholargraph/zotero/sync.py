"""Version-based Zotero -> LightRAG incremental synchronization."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from lightrag.utils_pipeline import input_dir_path
from scholargraph.zotero.client import (
    ZoteroInstanceChangedError,
    item_is_deleted,
    parse_attachment,
    parse_paper,
)
from scholargraph.zotero.gateway import ZoteroRAGGateway
from scholargraph.zotero.mapping import ZoteroMappingStore
from scholargraph.zotero.models import (
    IndexStatus,
    SyncAction,
    SyncEvent,
    SyncReport,
    ZoteroAttachment,
    ZoteroChanges,
    ZoteroMapping,
    ZoteroPaper,
    ZoteroServerInfo,
    ZoteroSyncState,
)

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_-]")


class ZoteroReadClient(Protocol):
    async def probe(self) -> ZoteroServerInfo: ...

    async def fetch_changes(self, since: int) -> ZoteroChanges: ...

    async def get_items(self, keys: set[str]) -> dict[str, dict[str, object]]: ...

    async def get_children(self, item_key: str) -> tuple[dict[str, object], ...]: ...

    async def download_attachment(
        self, attachment_key: str, destination: Path
    ) -> str: ...


class ZoteroSyncService:
    """Maintain a derived LightRAG index from Zotero Local API versions."""

    def __init__(
        self,
        client: ZoteroReadClient,
        mappings: ZoteroMappingStore,
        gateway: ZoteroRAGGateway,
        *,
        staging_dir: str | Path | None = None,
        library_key: str = "users/0",
    ) -> None:
        self.client = client
        self.mappings = mappings
        self.gateway = gateway
        self.library_key = library_key
        configured_input = input_dir_path().resolve()
        self.staging_dir = (
            Path(staging_dir).resolve()
            if staging_dir is not None
            else (configured_input / "zotero").resolve()
        )
        try:
            self.staging_dir.relative_to(configured_input)
        except ValueError as exc:
            raise ValueError(
                f"Zotero staging_dir must be under INPUT_DIR: {configured_input}"
            ) from exc
        self._lock = asyncio.Lock()

    async def sync_once(self) -> SyncReport:
        """Apply one atomic version window; retry failures on the next poll."""
        async with self._lock:
            self.mappings.initialize()
            info = await self.client.probe()
            state = self.mappings.get_sync_state(self.library_key)
            if state is not None and state.server_id != info.server_id:
                raise ZoteroInstanceChangedError(
                    "Zotero-Server-ID changed; reset the ScholarGraph mapping "
                    "checkpoint before syncing another Zotero instance"
                )

            previous_version = state.library_version if state else 0
            changes = await self.client.fetch_changes(previous_version)
            report = SyncReport(
                previous_version=previous_version,
                observed_version=changes.library_version,
                committed_version=previous_version,
            )
            await self._apply_changes(changes, report)

            if report.succeeded:
                timestamp = _utc_now()
                self.mappings.set_sync_state(
                    ZoteroSyncState(
                        library_key=self.library_key,
                        server_id=info.server_id,
                        library_version=changes.library_version,
                        last_sync_time=timestamp,
                    )
                )
                report.committed_version = changes.library_version
            return report

    async def _apply_changes(
        self, changes: ZoteroChanges, report: SyncReport
    ) -> None:
        raw_by_key = {
            str(item["key"]): item
            for item in changes.items
            if isinstance(item.get("key"), str)
        }
        deletion_keys = set(changes.deleted_item_keys)
        deletion_keys.update(
            key for key, item in raw_by_key.items() if item_is_deleted(item)
        )
        deleted_attachments: set[str] = set()
        for mapping in self.mappings.list_matching_keys(deletion_keys):
            await self._delete_mapping(mapping, report)
            deleted_attachments.add(mapping.attachment_key)

        affected_parent_keys: set[str] = set()
        for key, raw in raw_by_key.items():
            if key in deletion_keys:
                continue
            attachment = parse_attachment(raw)
            if attachment is not None:
                affected_parent_keys.add(attachment.parent_item_key)
                continue
            if parse_paper(raw) is not None:
                affected_parent_keys.add(key)

        # Failed mappings are a durable retry queue. This also powers explicit
        # reindex requests when the Zotero object itself has not changed since
        # the last committed library version.
        affected_parent_keys.update(
            mapping.item_key
            for mapping in self.mappings.list()
            if mapping.index_status is IndexStatus.FAILED
        )

        missing_parent_keys = affected_parent_keys - raw_by_key.keys()
        if missing_parent_keys:
            raw_by_key.update(await self.client.get_items(missing_parent_keys))

        for item_key in sorted(affected_parent_keys):
            raw_parent = raw_by_key.get(item_key)
            paper = parse_paper(raw_parent) if raw_parent else None
            if paper is None or item_is_deleted(raw_parent):
                for mapping in self.mappings.list_for_item(item_key):
                    if mapping.attachment_key not in deleted_attachments:
                        await self._delete_mapping(mapping, report)
                continue

            children = await self.client.get_children(item_key)
            attachments = {
                attachment.key: attachment
                for raw_child in children
                if not item_is_deleted(raw_child)
                if (attachment := parse_attachment(raw_child)) is not None
                and attachment.is_pdf
            }
            existing = {
                mapping.attachment_key: mapping
                for mapping in self.mappings.list_for_item(item_key)
            }
            for removed_key in sorted(existing.keys() - attachments.keys()):
                if removed_key not in deleted_attachments:
                    await self._delete_mapping(existing[removed_key], report)
            for attachment in attachments.values():
                await self._sync_attachment(
                    paper,
                    attachment,
                    changes.library_version,
                    existing.get(attachment.key),
                    report,
                )

    async def _sync_attachment(
        self,
        paper: ZoteroPaper,
        attachment: ZoteroAttachment,
        library_version: int,
        current: ZoteroMapping | None,
        report: SyncReport,
    ) -> None:
        timestamp = _utc_now()
        pdf_path = self.staging_dir / f"{_safe_key(attachment.key)}.pdf"
        metadata_hash = _metadata_hash(paper, attachment)
        if current is not None and current.index_status is IndexStatus.EXCLUDED:
            self.mappings.upsert(
                replace(
                    current,
                    zotero_version=library_version,
                    item_version=paper.version,
                    attachment_version=attachment.version,
                    metadata_hash=metadata_hash,
                    last_sync_time=timestamp,
                    error=None,
                )
            )
            report.events.append(
                SyncEvent(
                    action=SyncAction.SKIP,
                    item_key=paper.key,
                    attachment_key=attachment.key,
                    message="Attachment is excluded from the derived index",
                )
            )
            return
        pdf_hash = current.pdf_hash if current else None
        needs_download = (
            current is None
            or current.attachment_version != attachment.version
            or not pdf_path.is_file()
            or current.index_status is IndexStatus.FAILED
        )
        deleted_old = False
        try:
            if needs_download:
                pdf_hash = await self.client.download_attachment(
                    attachment.key, pdf_path
                )
            needs_index = (
                current is None
                or current.rag_document_id is None
                or current.index_status is not IndexStatus.INDEXED
                or current.pdf_hash != pdf_hash
                or current.metadata_hash != metadata_hash
            )
            if not needs_index:
                self.mappings.upsert(
                    replace(
                        current,
                        zotero_version=library_version,
                        item_version=paper.version,
                        attachment_version=attachment.version,
                        pdf_path=pdf_path,
                        last_sync_time=timestamp,
                        error=None,
                    )
                )
                report.events.append(
                    SyncEvent(
                        action=SyncAction.SKIP,
                        item_key=paper.key,
                        attachment_key=attachment.key,
                        rag_document_id=current.rag_document_id,
                    )
                )
                return

            processing = ZoteroMapping(
                item_key=paper.key,
                attachment_key=attachment.key,
                zotero_version=library_version,
                item_version=paper.version,
                attachment_version=attachment.version,
                rag_document_id=current.rag_document_id if current else None,
                pdf_path=pdf_path,
                pdf_hash=pdf_hash,
                metadata_hash=metadata_hash,
                index_status=IndexStatus.PROCESSING,
                last_sync_time=timestamp,
            )
            self.mappings.upsert(processing)
            if current and current.rag_document_id:
                await self.gateway.delete_document(current.rag_document_id)
                deleted_old = True
            document_id = await self.gateway.index_pdf(pdf_path, paper, attachment)
            self.mappings.upsert(
                replace(
                    processing,
                    rag_document_id=document_id,
                    index_status=IndexStatus.INDEXED,
                )
            )
            report.events.append(
                SyncEvent(
                    action=(
                        SyncAction.UPDATE
                        if current and current.rag_document_id
                        else SyncAction.ADD
                    ),
                    item_key=paper.key,
                    attachment_key=attachment.key,
                    rag_document_id=document_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - persist per-item failure state
            failed_document_id = (
                None
                if current and deleted_old
                else current.rag_document_id if current else None
            )
            self.mappings.upsert(
                ZoteroMapping(
                    item_key=paper.key,
                    attachment_key=attachment.key,
                    zotero_version=library_version,
                    item_version=paper.version,
                    attachment_version=attachment.version,
                    rag_document_id=failed_document_id,
                    pdf_path=pdf_path,
                    pdf_hash=pdf_hash,
                    metadata_hash=metadata_hash,
                    index_status=IndexStatus.FAILED,
                    last_sync_time=timestamp,
                    error=str(exc),
                )
            )
            report.events.append(
                SyncEvent(
                    action=SyncAction.FAIL,
                    item_key=paper.key,
                    attachment_key=attachment.key,
                    rag_document_id=failed_document_id,
                    message=str(exc),
                )
            )

    async def _delete_mapping(
        self, mapping: ZoteroMapping, report: SyncReport
    ) -> None:
        try:
            if mapping.rag_document_id:
                await self.gateway.delete_document(mapping.rag_document_id)
            self.mappings.delete(mapping.attachment_key)
            self._remove_staged_pdf(mapping.pdf_path)
            report.events.append(
                SyncEvent(
                    action=SyncAction.DELETE,
                    item_key=mapping.item_key,
                    attachment_key=mapping.attachment_key,
                    rag_document_id=mapping.rag_document_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - persist per-item failure state
            self.mappings.upsert(
                replace(
                    mapping,
                    index_status=IndexStatus.FAILED,
                    last_sync_time=_utc_now(),
                    error=str(exc),
                )
            )
            report.events.append(
                SyncEvent(
                    action=SyncAction.FAIL,
                    item_key=mapping.item_key,
                    attachment_key=mapping.attachment_key,
                    rag_document_id=mapping.rag_document_id,
                    message=str(exc),
                )
            )

    async def exclude_attachment(self, attachment_key: str) -> ZoteroMapping:
        """Delete one derived document and keep an explicit exclusion marker."""
        async with self._lock:
            mapping = self.mappings.get(attachment_key)
            if mapping is None:
                raise KeyError(f"Unknown Zotero attachment mapping: {attachment_key}")
            if mapping.rag_document_id:
                await self.gateway.delete_document(mapping.rag_document_id)
            self._remove_staged_pdf(mapping.pdf_path)
            excluded = replace(
                mapping,
                rag_document_id=None,
                pdf_hash=None,
                index_status=IndexStatus.EXCLUDED,
                last_sync_time=_utc_now(),
                error=None,
            )
            self.mappings.upsert(excluded)
            return excluded

    async def reindex_attachment(self, attachment_key: str) -> SyncReport:
        """Mark one mapping for retry even if its Zotero version is unchanged."""
        async with self._lock:
            mapping = self.mappings.get(attachment_key)
            if mapping is None:
                raise KeyError(f"Unknown Zotero attachment mapping: {attachment_key}")
            self.mappings.upsert(
                replace(
                    mapping,
                    index_status=IndexStatus.FAILED,
                    last_sync_time=_utc_now(),
                    error=None,
                )
            )
        return await self.sync_once()

    def _remove_staged_pdf(self, pdf_path: Path) -> None:
        resolved = pdf_path.resolve()
        try:
            resolved.relative_to(self.staging_dir)
        except ValueError as exc:
            raise RuntimeError(f"Refusing to remove non-staged PDF: {resolved}") from exc
        resolved.unlink(missing_ok=True)


def _safe_key(key: str) -> str:
    normalized = _SAFE_KEY_RE.sub("_", key).strip("_")
    if not normalized:
        raise ValueError("Zotero attachment key cannot form a safe file name")
    return normalized[:128]


def _metadata_hash(paper: ZoteroPaper, attachment: ZoteroAttachment) -> str:
    payload = {
        "item_key": paper.key,
        "attachment_key": attachment.key,
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "doi": paper.doi,
        "collections": paper.collections,
        "tags": paper.tags,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
