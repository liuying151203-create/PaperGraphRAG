from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scholargraph.zotero.client import ZoteroInstanceChangedError
from scholargraph.zotero.mapping import ZoteroMappingStore
from scholargraph.zotero.models import (
    IndexStatus,
    SyncAction,
    ZoteroChanges,
    ZoteroServerInfo,
)
from scholargraph.zotero.sync import ZoteroSyncService


def _paper_raw(*, version: int, title: str) -> dict[str, object]:
    return {
        "key": "PAPERABC",
        "version": version,
        "data": {
            "key": "PAPERABC",
            "version": version,
            "itemType": "journalArticle",
            "title": title,
            "creators": [
                {"creatorType": "author", "firstName": "Grace", "lastName": "Hopper"}
            ],
            "date": "2024",
            "DOI": "10.1000/test",
            "collections": ["COLLECT1"],
            "tags": [{"tag": "graph"}],
        },
    }


def _attachment_raw(*, version: int) -> dict[str, object]:
    return {
        "key": "ATTACHAB",
        "version": version,
        "data": {
            "key": "ATTACHAB",
            "version": version,
            "itemType": "attachment",
            "parentItem": "PAPERABC",
            "title": "PDF",
            "contentType": "application/pdf",
            "linkMode": "imported_file",
            "filename": "paper.pdf",
        },
    }


class FakeClient:
    def __init__(self) -> None:
        self.server_id = "desktop-one"
        self.version = 5
        self.paper = _paper_raw(version=4, title="Initial Paper")
        self.attachment = _attachment_raw(version=5)
        self.deleted: tuple[str, ...] = ()
        self.pdf = b"%PDF-1.7\ninitial"
        self.since_calls: list[int] = []

    async def probe(self) -> ZoteroServerInfo:
        return ZoteroServerInfo(api_version=3, server_id=self.server_id)

    async def fetch_changes(self, since: int) -> ZoteroChanges:
        self.since_calls.append(since)
        items = () if self.deleted else (self.paper, self.attachment)
        return ZoteroChanges(self.version, items, self.deleted)

    async def get_items(self, keys: set[str]) -> dict[str, dict[str, object]]:
        return {"PAPERABC": self.paper} if "PAPERABC" in keys else {}

    async def get_children(self, item_key: str) -> tuple[dict[str, object], ...]:
        assert item_key == "PAPERABC"
        return () if self.deleted else (self.attachment,)

    async def download_attachment(self, attachment_key: str, destination: Path) -> str:
        assert attachment_key == "ATTACHAB"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.pdf)
        return hashlib.sha256(self.pdf).hexdigest()


class FakeGateway:
    def __init__(self) -> None:
        self.indexed: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.fail_index = False

    async def index_pdf(self, pdf_path, paper, attachment) -> str:
        if self.fail_index:
            raise RuntimeError("index unavailable")
        assert pdf_path.read_bytes().startswith(b"%PDF-")
        self.indexed.append((paper.key, attachment.key))
        return f"doc-{attachment.key.lower()}"

    async def delete_document(self, document_id: str) -> None:
        self.deleted.append(document_id)


@pytest.mark.asyncio
async def test_sync_add_update_delete_and_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir = tmp_path / "inputs"
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    client = FakeClient()
    gateway = FakeGateway()
    store = ZoteroMappingStore(tmp_path / "zotero.sqlite3")
    service = ZoteroSyncService(client, store, gateway)

    added = await service.sync_once()
    assert added.count(SyncAction.ADD) == 1
    assert added.committed_version == 5
    mapping = store.get("ATTACHAB")
    assert mapping is not None
    assert mapping.index_status is IndexStatus.INDEXED
    assert mapping.pdf_path == input_dir / "zotero" / "ATTACHAB.pdf"

    client.version = 6
    client.paper = _paper_raw(version=6, title="Updated Paper")
    client.attachment = _attachment_raw(version=6)
    client.pdf = b"%PDF-1.7\nupdated"
    updated = await service.sync_once()
    assert updated.count(SyncAction.UPDATE) == 1
    assert gateway.deleted == ["doc-attachab"]
    assert store.get_sync_state().library_version == 6  # type: ignore[union-attr]

    client.version = 7
    client.deleted = ("ATTACHAB",)
    deleted = await service.sync_once()
    assert deleted.count(SyncAction.DELETE) == 1
    assert store.get("ATTACHAB") is None
    assert not (input_dir / "zotero" / "ATTACHAB.pdf").exists()
    assert gateway.deleted == ["doc-attachab", "doc-attachab"]
    assert client.since_calls == [0, 5, 6]


@pytest.mark.asyncio
async def test_failed_index_does_not_advance_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "inputs"))
    client = FakeClient()
    gateway = FakeGateway()
    gateway.fail_index = True
    store = ZoteroMappingStore(tmp_path / "zotero.sqlite3")
    service = ZoteroSyncService(client, store, gateway)

    failed = await service.sync_once()

    assert failed.count(SyncAction.FAIL) == 1
    assert failed.committed_version == 0
    assert store.get_sync_state() is None
    mapping = store.get("ATTACHAB")
    assert mapping is not None
    assert mapping.index_status is IndexStatus.FAILED


@pytest.mark.asyncio
async def test_sync_refuses_versions_from_another_zotero_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "inputs"))
    client = FakeClient()
    store = ZoteroMappingStore(tmp_path / "zotero.sqlite3")
    service = ZoteroSyncService(client, store, FakeGateway())
    await service.sync_once()
    client.server_id = "desktop-two"

    with pytest.raises(ZoteroInstanceChangedError, match="Server-ID changed"):
        await service.sync_once()


@pytest.mark.asyncio
async def test_exclude_and_explicit_reindex_without_new_zotero_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "inputs"))
    client = FakeClient()
    gateway = FakeGateway()
    store = ZoteroMappingStore(tmp_path / "zotero.sqlite3")
    service = ZoteroSyncService(client, store, gateway)
    await service.sync_once()

    excluded = await service.exclude_attachment("ATTACHAB")
    assert excluded.index_status is IndexStatus.EXCLUDED
    assert excluded.rag_document_id is None
    assert gateway.deleted == ["doc-attachab"]

    skipped = await service.sync_once()
    assert skipped.count(SyncAction.SKIP) == 1
    assert store.get("ATTACHAB").index_status is IndexStatus.EXCLUDED  # type: ignore[union-attr]

    reindexed = await service.reindex_attachment("ATTACHAB")
    assert reindexed.count(SyncAction.ADD) == 1
    assert store.get("ATTACHAB").index_status is IndexStatus.INDEXED  # type: ignore[union-attr]
