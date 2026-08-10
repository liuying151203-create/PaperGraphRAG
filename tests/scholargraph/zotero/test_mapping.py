from __future__ import annotations

from pathlib import Path

from scholargraph.zotero.mapping import ZoteroMappingStore
from scholargraph.zotero.models import (
    IndexStatus,
    ZoteroMapping,
    ZoteroSyncState,
)


def test_mapping_store_round_trip_and_key_lookup(tmp_path: Path) -> None:
    store = ZoteroMappingStore(tmp_path / "state" / "zotero.sqlite3")
    store.initialize()
    mapping = ZoteroMapping(
        item_key="PAPERABC",
        attachment_key="ATTACHAB",
        zotero_version=20,
        item_version=18,
        attachment_version=20,
        rag_document_id="doc-123",
        pdf_path=tmp_path / "inputs" / "ATTACHAB.pdf",
        pdf_hash="pdf-hash",
        metadata_hash="metadata-hash",
        index_status=IndexStatus.INDEXED,
        last_sync_time="2026-08-10T00:00:00+00:00",
    )
    store.upsert(mapping)

    assert store.get("ATTACHAB") == mapping
    assert store.list_for_item("PAPERABC") == [mapping]
    assert store.list_matching_keys({"PAPERABC"}) == [mapping]
    assert store.list_matching_keys({"ATTACHAB"}) == [mapping]

    state = ZoteroSyncState(
        library_key="users/0",
        server_id="desktop-one",
        library_version=20,
        last_sync_time="2026-08-10T00:00:00+00:00",
    )
    store.set_sync_state(state)
    assert store.get_sync_state() == state

    store.delete("ATTACHAB")
    assert store.get("ATTACHAB") is None

