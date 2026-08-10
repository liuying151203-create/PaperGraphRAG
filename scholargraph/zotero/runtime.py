"""Server-facing Zotero runtime built from the sync core."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from scholargraph.zotero.client import (
    ZoteroLocalAPIError,
    ZoteroLocalClient,
    parse_paper,
)
from scholargraph.zotero.gateway import LightRAGZoteroGateway
from scholargraph.zotero.mapping import ZoteroMappingStore
from scholargraph.zotero.models import SyncReport
from scholargraph.zotero.sync import ZoteroSyncService

if TYPE_CHECKING:
    from lightrag import LightRAG


class ScholarGraphZoteroRuntime:
    """Create short-lived Local API clients around one persistent mapping DB."""

    def __init__(
        self,
        rag: LightRAG,
        *,
        database_path: str | Path,
        staging_dir: str | Path | None = None,
        base_url: str = "http://127.0.0.1:23119/api/",
        client_factory: Callable[[], ZoteroLocalClient] | None = None,
    ) -> None:
        self.gateway = LightRAGZoteroGateway(rag)
        self.mappings = ZoteroMappingStore(database_path)
        self.mappings.initialize()
        self.staging_dir = staging_dir
        self.base_url = base_url
        self._client_factory = client_factory

    def _new_client(self) -> ZoteroLocalClient:
        if self._client_factory is not None:
            return self._client_factory()
        return ZoteroLocalClient(self.base_url)

    async def status(self) -> dict[str, object]:
        mappings = self.mappings.list()
        counts = Counter(mapping.index_status.value for mapping in mappings)
        state = self.mappings.get_sync_state()
        try:
            async with self._new_client() as client:
                info = await client.probe()
            return {
                "connected": True,
                "api_version": info.api_version,
                "server_id": info.server_id,
                "library_version": state.library_version if state else 0,
                "last_sync_time": state.last_sync_time if state else None,
                "papers": len({mapping.item_key for mapping in mappings}),
                "attachments": len(mappings),
                "status_counts": dict(counts),
                "error": None,
            }
        except ZoteroLocalAPIError as exc:
            return {
                "connected": False,
                "api_version": None,
                "server_id": None,
                "library_version": state.library_version if state else 0,
                "last_sync_time": state.last_sync_time if state else None,
                "papers": len({mapping.item_key for mapping in mappings}),
                "attachments": len(mappings),
                "status_counts": dict(counts),
                "error": str(exc),
            }

    async def library(self) -> list[dict[str, object]]:
        mappings = self.mappings.list()
        raw_items: dict[str, dict[str, object]] = {}
        if mappings:
            try:
                async with self._new_client() as client:
                    await client.probe()
                    raw_items = await client.get_items(
                        {mapping.item_key for mapping in mappings}
                    )
            except ZoteroLocalAPIError:
                raw_items = {}

        rows: list[dict[str, object]] = []
        for mapping in mappings:
            paper = (
                parse_paper(raw_items[mapping.item_key])
                if mapping.item_key in raw_items
                else None
            )
            rows.append(
                {
                    "item_key": mapping.item_key,
                    "attachment_key": mapping.attachment_key,
                    "title": paper.title if paper else None,
                    "authors": list(paper.authors) if paper else [],
                    "year": paper.year if paper else None,
                    "doi": paper.doi if paper else None,
                    "collections": list(paper.collections) if paper else [],
                    "tags": list(paper.tags) if paper else [],
                    "zotero_version": mapping.zotero_version,
                    "rag_document_id": mapping.rag_document_id,
                    "pdf_path": str(mapping.pdf_path),
                    "pdf_hash": mapping.pdf_hash,
                    "index_status": mapping.index_status.value,
                    "last_sync_time": mapping.last_sync_time,
                    "error": mapping.error,
                }
            )
        return rows

    async def sync_once(self) -> SyncReport:
        async with self._new_client() as client:
            return await self._service(client).sync_once()

    async def exclude_attachment(self, attachment_key: str) -> dict[str, object]:
        async with self._new_client() as client:
            mapping = await self._service(client).exclude_attachment(attachment_key)
        return {
            "attachment_key": mapping.attachment_key,
            "index_status": mapping.index_status.value,
            "rag_document_id": mapping.rag_document_id,
        }

    async def reindex_attachment(self, attachment_key: str) -> SyncReport:
        async with self._new_client() as client:
            return await self._service(client).reindex_attachment(attachment_key)

    def _service(self, client: ZoteroLocalClient) -> ZoteroSyncService:
        return ZoteroSyncService(
            client,
            self.mappings,
            self.gateway,
            staging_dir=self.staging_dir,
        )


def sync_report_dict(report: SyncReport) -> dict[str, object]:
    return {
        "succeeded": report.succeeded,
        "previous_version": report.previous_version,
        "observed_version": report.observed_version,
        "committed_version": report.committed_version,
        "events": [
            {
                "action": event.action.value,
                "item_key": event.item_key,
                "attachment_key": event.attachment_key,
                "rag_document_id": event.rag_document_id,
                "message": event.message,
            }
            for event in report.events
        ],
    }
