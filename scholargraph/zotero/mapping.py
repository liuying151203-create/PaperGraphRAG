"""ScholarGraph-owned SQLite mapping storage for Zotero-derived documents."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from scholargraph.zotero.models import IndexStatus, ZoteroMapping, ZoteroSyncState


class ZoteroMappingStore:
    """Persist derived-index mappings without touching Zotero's own database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS zotero_mappings (
                    zotero_attachment_key TEXT PRIMARY KEY,
                    zotero_item_key TEXT NOT NULL,
                    zotero_version INTEGER NOT NULL,
                    item_version INTEGER NOT NULL,
                    attachment_version INTEGER NOT NULL,
                    rag_document_id TEXT,
                    pdf_path TEXT NOT NULL,
                    pdf_hash TEXT,
                    metadata_hash TEXT,
                    index_status TEXT NOT NULL,
                    last_sync_time TEXT NOT NULL,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_zotero_mappings_item
                    ON zotero_mappings(zotero_item_key);
                CREATE TABLE IF NOT EXISTS zotero_sync_state (
                    library_key TEXT PRIMARY KEY,
                    server_id TEXT,
                    library_version INTEGER NOT NULL,
                    last_sync_time TEXT NOT NULL
                );
                """
            )

    def get(self, attachment_key: str) -> ZoteroMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM zotero_mappings WHERE zotero_attachment_key = ?",
                (attachment_key,),
            ).fetchone()
        return self._mapping_from_row(row) if row else None

    def list(self) -> list[ZoteroMapping]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM zotero_mappings ORDER BY zotero_item_key, "
                "zotero_attachment_key"
            ).fetchall()
        return [self._mapping_from_row(row) for row in rows]

    def list_for_item(self, item_key: str) -> list[ZoteroMapping]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM zotero_mappings WHERE zotero_item_key = ? "
                "ORDER BY zotero_attachment_key",
                (item_key,),
            ).fetchall()
        return [self._mapping_from_row(row) for row in rows]

    def list_matching_keys(self, keys: set[str]) -> list[ZoteroMapping]:
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        values = tuple(sorted(keys))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM zotero_mappings WHERE zotero_item_key IN "
                f"({placeholders}) OR zotero_attachment_key IN ({placeholders})",
                values + values,
            ).fetchall()
        return [self._mapping_from_row(row) for row in rows]

    def upsert(self, mapping: ZoteroMapping) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO zotero_mappings (
                    zotero_attachment_key, zotero_item_key, zotero_version,
                    item_version, attachment_version, rag_document_id, pdf_path,
                    pdf_hash, metadata_hash, index_status, last_sync_time, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(zotero_attachment_key) DO UPDATE SET
                    zotero_item_key = excluded.zotero_item_key,
                    zotero_version = excluded.zotero_version,
                    item_version = excluded.item_version,
                    attachment_version = excluded.attachment_version,
                    rag_document_id = excluded.rag_document_id,
                    pdf_path = excluded.pdf_path,
                    pdf_hash = excluded.pdf_hash,
                    metadata_hash = excluded.metadata_hash,
                    index_status = excluded.index_status,
                    last_sync_time = excluded.last_sync_time,
                    error = excluded.error
                """,
                (
                    mapping.attachment_key,
                    mapping.item_key,
                    mapping.zotero_version,
                    mapping.item_version,
                    mapping.attachment_version,
                    mapping.rag_document_id,
                    str(mapping.pdf_path),
                    mapping.pdf_hash,
                    mapping.metadata_hash,
                    mapping.index_status.value,
                    mapping.last_sync_time,
                    mapping.error,
                ),
            )

    def delete(self, attachment_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM zotero_mappings WHERE zotero_attachment_key = ?",
                (attachment_key,),
            )

    def get_sync_state(self, library_key: str = "users/0") -> ZoteroSyncState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM zotero_sync_state WHERE library_key = ?",
                (library_key,),
            ).fetchone()
        if row is None:
            return None
        return ZoteroSyncState(
            library_key=str(row["library_key"]),
            server_id=row["server_id"],
            library_version=int(row["library_version"]),
            last_sync_time=str(row["last_sync_time"]),
        )

    def set_sync_state(self, state: ZoteroSyncState) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO zotero_sync_state (
                    library_key, server_id, library_version, last_sync_time
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(library_key) DO UPDATE SET
                    server_id = excluded.server_id,
                    library_version = excluded.library_version,
                    last_sync_time = excluded.last_sync_time
                """,
                (
                    state.library_key,
                    state.server_id,
                    state.library_version,
                    state.last_sync_time,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _mapping_from_row(row: sqlite3.Row) -> ZoteroMapping:
        return ZoteroMapping(
            item_key=str(row["zotero_item_key"]),
            attachment_key=str(row["zotero_attachment_key"]),
            zotero_version=int(row["zotero_version"]),
            item_version=int(row["item_version"]),
            attachment_version=int(row["attachment_version"]),
            rag_document_id=row["rag_document_id"],
            pdf_path=Path(row["pdf_path"]),
            pdf_hash=row["pdf_hash"],
            metadata_hash=row["metadata_hash"],
            index_status=IndexStatus(row["index_status"]),
            last_sync_time=str(row["last_sync_time"]),
            error=row["error"],
        )
