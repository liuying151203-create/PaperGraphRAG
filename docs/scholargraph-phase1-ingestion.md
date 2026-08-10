# ScholarGraph Phase 1: scientific PDF ingestion

## Outcome

Phase 1 adds a metadata-preserving scientific-paper ingestion boundary without
reimplementing PDF parsing or creating a parallel RAG pipeline. MinerU remains
responsible for PDF-to-structured-content conversion; LightRAG remains
responsible for sidecar normalization, chunking, embedding, entity/relation
extraction, vector and graph writes, retries, provenance, and deletion.

## Reused LightRAG capabilities

The implementation directly reuses:

- `MinerUParser` and `MinerUIRBuilder` for validated raw-bundle ingestion;
- the universal `*.parsed/` sidecar format for headings, page/bbox positions,
  tables, drawings, equations, and stable block IDs;
- `P` (`paragraph_semantic`) chunking for section-aware paper chunks;
- `apipeline_enqueue_documents()` with `pending_parse` for scheduling and
  recovery;
- existing embedding, vector storage, entity/relation extraction, graph
  storage, query, and document deletion paths.

No PDF parser, vector database, graph database, or background scheduler was
added by ScholarGraph.

## Added capability

### Paper metadata contract

`scholargraph.ingestion.PaperMetadata` validates and normalizes:

| Field | Requirement |
| --- | --- |
| `paper_id` | required stable project identifier |
| `title` | required |
| `authors` | ordered, de-duplicated list |
| `year` | optional four-digit year |
| `doi` | optional; DOI URL/prefix is removed and the value is lower-cased |
| `source_path` | required original/staged source reference |
| `zotero_item_key` | optional, reserved for Zotero integration |
| `zotero_attachment_key` | optional, reserved for Zotero integration |

Unknown fields are rejected so spelling mistakes do not silently become
unusable metadata.

### Generic LightRAG metadata carrier

`apipeline_enqueue_documents()` now accepts optional `document_metadata` as a
single JSON object or a list aligned with the input documents. The payload is:

- required to be a JSON object with non-empty string keys;
- normalized through a JSON round trip;
- limited to 64 KiB after UTF-8 serialization;
- stored under a dedicated nested key, avoiding collisions with internal
  recovery metadata such as `kg_write_state` and `kg_purge`;
- persisted in `full_docs`, `doc_status.metadata`, and every `text_chunks`
  record;
- retained across normal status transitions and FAILED-to-PENDING retries.

The vector backend does not need to duplicate this nested object. Vector search
returns chunk IDs, and LightRAG hydrates authoritative chunk records from
`text_chunks`, where the metadata and sidecar provenance live. This keeps the
same behavior for NanoVectorDB and the planned Milvus backend.

### Scientific PDF adapter

`enqueue_scientific_pdf()` accepts a PDF already staged below the configured
`INPUT_DIR`, validates its `PaperMetadata`, and invokes the existing pipeline
with:

```text
docs_format = pending_parse
parse_engine = mineru
process_options = P
document_metadata = PaperMetadata payload
```

It returns the tracking ID and LightRAG's deterministic document ID. It does
not parse, copy, mutate, or delete the source PDF itself.

### HTTP upload

`POST /documents/upload` accepts an optional multipart `metadata` field whose
value is a JSON object. A safe file-based curl form avoids shell quote loss:

```bash
curl -F "file=@paper.pdf;type=application/pdf" \
  -F "metadata=<paper-metadata.json" \
  http://127.0.0.1:9621/documents/upload
```

Invalid JSON, a non-object value, invalid keys, non-JSON values, or payloads
over 64 KiB return HTTP 400 before the uploaded file is written.

## Citation and evidence provenance

Paper-level metadata is attached directly to each stored text chunk. Structural
provenance uses LightRAG's existing representation:

- `chunk.heading` carries the section heading and parent hierarchy;
- `chunk.sidecar.refs` names one or more source block IDs;
- the referenced `blocks.jsonl` rows carry page anchors and bbox ranges;
- the chunk storage key is the stable chunk ID used by vector and graph
  evidence.

The current `/query/data` response intentionally presents a compact chunk
projection (`chunk_id`, content, file path). Phase 3 Evidence Trace can enrich
that response by resolving the existing chunk and sidecar references; it does
not need to change ingestion again.

## Verification

### Automated checks

- ScholarGraph metadata/adapter and full-pipeline tests: **7 passed**.
- Health and API bridge tests: **10 passed**.
- Existing MinerU parser/cache/IR/sidecar tests: **92 passed**.
- The broader document route test file passed **80 relevant tests**; its three
  remaining failures are pre-existing Windows platform assumptions requiring
  symlink privilege or POSIX `0600` mode reporting.
- Two long-path deletion cases in the broader pipeline suite exceed the
  default Windows path limit; they are unrelated to document metadata.

### Isolated live service check

An isolated server on port `19622` used independent input and storage
directories. A validated, pre-generated MinerU raw bundle exercised the real
cache-hit parser path without depending on an external service during the
test. Results:

| Check | Result |
| --- | --- |
| HTTP upload with complete paper metadata | accepted |
| Parser | `mineru`, raw-bundle cache hit |
| Chunking | `paragraph_semantic`, one chunk |
| Metadata persistence | paper ID, title, authors, year, DOI, source and Zotero keys present in doc status and chunk storage |
| Section provenance | two headings and two block references |
| Page provenance | page anchors 1 and 2 |
| Knowledge graph | 4 nodes and 3 edges for the test method/dataset/metric/task |
| Mixed evidence retrieval | 8 entities, 5 relations, 1 chunk, 1 reference |
| Deletion | document absent, uploaded file absent, graph returned 0 nodes/0 edges |

The isolated service was stopped and all generated test data was removed.

## Operational boundary

A MinerU endpoint is still an external runtime dependency on a raw-cache miss.
The current machine does not have a self-hosted MinerU service or GPU model
installation, and no official API credential was supplied. The adapter and
cache-hit path are operational; production or first-time PDF parsing must set
the existing `MINERU_API_MODE` plus the matching local or official endpoint
credentials documented in `env.example`. This phase does not claim that an
external MinerU deployment was installed.

## Phase 1 exit condition

The scientific PDF ingestion boundary, metadata contract, persistence path,
section/page provenance, HTTP entry point, actual server indexing, retrieval,
and deletion are implemented and verified. Phase 2 can build the academic
entity schema and relation normalizer on these stored paper identities without
changing the PDF parser.
