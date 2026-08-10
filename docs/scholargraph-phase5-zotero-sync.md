# ScholarGraph Phase 5: Zotero Incremental Sync

## Outcome

ScholarGraph now has a read-only Zotero integration that maintains a derived
LightRAG index through version-based polling:

```text
Zotero Local API v3
  -> changed items since committed version
  -> parent item + current PDF children
  -> ScholarGraph-owned PDF staging copy
  -> MinerU / LightRAG ingestion
  -> independent SQLite item/attachment/document mapping

Zotero deletion log
  -> mapped RAG document
  -> LightRAG attribution-safe deletion
```

Zotero remains the source of truth. The integration never opens Zotero's
SQLite database and never writes, moves, or removes Zotero-managed files.

## Source analysis and reuse

The implementation follows Zotero's current official API contracts:

- The desktop client exposes Web API v3 below
  `http://localhost:23119/api/`.
- Local read requests need no authentication and are intended only for local
  applications.
- `since=<version>` returns objects changed after a saved library version.
- `Last-Modified-Version` is a monotonic checkpoint, not a sequential counter.
- `/users/0/deleted?since=<version>` returns deleted item keys.
- `/users/0/items/<itemKey>/children` returns an item's attachments.
- `/users/0/items/<attachmentKey>/file` returns attachment content.
- Zotero 10's `Zotero-Server-ID` identifies the desktop instance because local
  versions are meaningful only within that instance.

Primary references:

- [Zotero Local API](https://www.zotero.org/support/dev/web_api/v3/local_api)
- [Zotero Web API basics](https://www.zotero.org/support/dev/web_api/v3/basics)
- [Zotero version syncing](https://www.zotero.org/support/dev/web_api/v3/syncing)
- [Zotero attachment file endpoint](https://www.zotero.org/support/dev/web_api/v3/file_upload)

On the LightRAG side, the integration reuses:

- `enqueue_scientific_pdf` from Phase 1 for MinerU parsing, metadata
  propagation, chunking, embeddings, graph extraction, and retries.
- `LightRAG.adelete_by_doc_id` for vector, graph, chunk, status, and recovery
  anchor cleanup.
- Stable document IDs derived by the existing ingestion pipeline from the
  staged attachment filename.

No Zotero-specific mapping fields were added to a LightRAG storage backend.

## Added modules

| Module | Responsibility |
|---|---|
| `scholargraph/zotero/client.py` | Loopback-only Local API v3 client, normalization, consistent version-window reads, and PDF download |
| `scholargraph/zotero/models.py` | Paper, attachment, mapping, checkpoint, action, and report contracts |
| `scholargraph/zotero/mapping.py` | ScholarGraph-owned SQLite mapping and sync checkpoint |
| `scholargraph/zotero/gateway.py` | Minimal adapter to Phase 1 ingestion and LightRAG deletion |
| `scholargraph/zotero/sync.py` | ADD/UPDATE/DELETE orchestration and checkpoint semantics |

The HTTP client is provided by the project's `api` extra, which is already
required by the LightRAG server:

```powershell
uv sync --extra api
```

## Metadata and attachment mapping

Regular Zotero items are normalized into:

- item key
- title
- authors
- year
- DOI
- collection keys
- tags
- item version

Child items are accepted for indexing when their content type is
`application/pdf` and their link mode is `imported_file`, `imported_url`, or
`linked_file`. Multiple PDF children under one paper produce separate mappings
and RAG documents.

The SQLite `zotero_mappings` table contains the required business mapping plus
individual object versions used for correct change detection:

```text
zotero_item_key
zotero_attachment_key
zotero_version
item_version
attachment_version
rag_document_id
pdf_path
pdf_hash
metadata_hash
index_status
last_sync_time
error
```

`zotero_sync_state` separately records `library_key`, `server_id`, the last
fully committed library version, and sync time.

## Incremental behavior

Each `sync_once()` call is one polling cycle:

1. Probe the Local API and validate API v3 and the Zotero server identity.
2. Read changed items and deleted keys after the committed library version.
3. Refetch missing parents and each affected parent's current child list.
4. Compare item version, attachment version, PDF SHA-256, and normalized
   metadata SHA-256 against SQLite.
5. Perform ADD, UPDATE, DELETE, or SKIP through the LightRAG gateway.
6. Advance the library checkpoint only when every attachment operation
   succeeds.

UPDATE downloads the replacement PDF before removing the old derived index.
If deletion or indexing then fails, the mapping is retained as `failed`, the
library checkpoint is not advanced, and the same Zotero version window is
retried on the next poll. Replaying a completed deletion is safe because a
missing LightRAG document is treated as already deleted.

When `Zotero-Server-ID` changes, synchronization fails closed instead of
applying versions or deletion keys from a different Zotero profile to the
existing derived index.

## Staging and file safety

PDFs are downloaded through the Local API into:

```text
<INPUT_DIR>/zotero/<attachment_key>.pdf
```

The client writes a temporary `.part` file, verifies a PDF header, computes
SHA-256 while streaming, and atomically replaces the ScholarGraph copy. Only a
path proven to be inside this staging directory can be removed during DELETE.
The source attachment in Zotero is untouched.

The staging directory is intentionally under `INPUT_DIR`, which lets the
existing MinerU ingestion adapter accept it without weakening its path safety
checks.

## Programmatic use

The `LightRAG` instance must have initialized storages, and `INPUT_DIR` must be
configured before constructing the sync service:

```python
from scholargraph.zotero import (
    LightRAGZoteroGateway,
    ZoteroLocalClient,
    ZoteroMappingStore,
    ZoteroSyncService,
)

async with ZoteroLocalClient() as zotero:
    service = ZoteroSyncService(
        zotero,
        ZoteroMappingStore("./data/scholargraph-zotero.sqlite3"),
        LightRAGZoteroGateway(rag),
    )
    report = await service.sync_once()
    print(report.observed_version, report.committed_version, report.events)
```

Call `sync_once()` on the application's polling interval. A server-owned
background scheduler and Library UI will be wired in the WebUI integration
phase so that application lifecycle and concurrent pipeline reservations are
handled in one place.

## Verification

The local probe performed during development reported that nothing was
listening on port 23119. Therefore, no claim is made that a live user library
was synchronized in this environment.

The protocol and orchestration were instead verified with a deterministic
mock Local API and fake derived-index gateway. Coverage includes:

- API v3 and server identity probing
- incremental item and deletion endpoints
- parent/child and PDF file endpoints
- author, year, DOI, collection, and tag normalization
- loopback-only endpoint enforcement
- disabled Local API diagnostics
- SQLite CRUD and checkpoint persistence
- ADD -> UPDATE -> DELETE lifecycle
- staged PDF cleanup
- failed indexing without checkpoint advancement
- Zotero instance-change refusal
- Phase 1 metadata handoff
- idempotent LightRAG deletion

Focused Zotero tests plus the related ingestion and document-metadata tests:

```text
18 passed
```

Ruff and Python compilation checks passed.

## Current boundary

This phase implements the client, mapping, and incremental synchronization
core. The machine used for verification did not have Zotero running, and the
backend lifecycle/API endpoints and WebUI Library surface are intentionally
left for the next integration phase. Collection membership is currently
stored as Zotero collection keys; collection title lookup will be added with
the Library API/UI rather than duplicating data in the ingestion metadata.
