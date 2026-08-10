# LightRAG Phase 0 baseline analysis

## Scope and evidence

This document records the upstream LightRAG baseline before ScholarGraph
features are added. No `lightrag/` source code was changed during this phase.

The repository contains an existing locally indexed paper:

- Input: a parsed `HANHeterogeneous Graph Attention Network` PDF under
  `inputs/__parsed__/`
- Document record: `rag_storage/kv_store_doc_status.json` reports the document as
  `PROCESSED`.
- Vector index artifacts: `vdb_chunks.json`, `vdb_entities.json`, and
  `vdb_relationships.json`.
- Knowledge graph artifact: `graph_chunk_entity_relation.graphml`, whose nodes
  include the paper `Heterogeneous Graph Attention Network` and source chunk
  identifiers.
- Recovery and provenance artifacts: `kv_store_full_docs.json`,
  `kv_store_full_entities.json`, `kv_store_full_relations.json`, and the
  entity/relation-to-chunk stores.

These artifacts prove that the baseline previously indexed at least one real
PDF into text chunks, vectors, and a knowledge graph. They are not a substitute
for a new end-to-end run; the current runtime status is recorded below.

## Repository map

| Area | Verified location | Responsibility |
| --- | --- | --- |
| Core orchestration | `lightrag/lightrag.py` | `LightRAG`, public insert/query/delete APIs and storage lifecycle |
| Ingestion pipeline | `lightrag/pipeline.py` | enqueueing, parser dispatch, chunk processing, scheduling and recovery |
| RAG operations | `lightrag/operate.py` | chunking, extraction, graph merge, KG and naive retrieval |
| Storage contracts | `lightrag/base.py` | base KV, vector, graph and document-status abstractions |
| Storage registry | `lightrag/kg/__init__.py`, `lightrag/kg/factory.py` | validates and resolves concrete storage implementations |
| API entry point | `lightrag/api/lightrag_server.py` | creates the FastAPI application and mounts routers |
| API routers | `lightrag/api/routers/{document,query,graph}_routes.py` | document, query and graph HTTP endpoints |
| WebUI | `lightrag_webui/src/` | React/Vite client |
| Packaged WebUI | `lightrag/api/webui/` | production bundle served by the API server |

## Official local development and startup paths

The documented source-development path is `uv sync` (or `make dev`), then:

```bash
# Build the production WebUI bundle.
cd lightrag_webui
bun install --frozen-lockfile
bun run build
cd ..

# Configure .env from env.example, then start the API and packaged WebUI.
lightrag-server
```

For isolated WebUI development, run `bun run dev` in `lightrag_webui`; its
Vite configuration can proxy API paths to `http://localhost:9621`. Production
WebUI builds to `lightrag/api/webui/` and is served by the same FastAPI server,
so no separate frontend process is required for a production-style baseline.

## Document indexing call chain

1. HTTP ingress is implemented by `create_document_routes()` in
   `lightrag/api/routers/document_routes.py`. Relevant endpoints include
   `POST /documents/upload`, `POST /documents/text`, and
   `POST /documents/texts`.
2. Programmatic ingestion enters `LightRAG.ainsert()` in
   `lightrag/lightrag.py`.
3. It delegates to `_PipelineMixin.apipeline_enqueue_documents()` and
   `apipeline_process_enqueue_documents()` in `lightrag/pipeline.py`.
4. The pipeline resolves parser routing. Native, MinerU and Docling flows are
   dispatched through the pipeline/parser layer; it then records document
   status, chunks content, writes full-document and chunk stores, and computes
   embeddings through the configured `EmbeddingFunc`.
5. `LightRAG._process_extract_entities()` runs entity/relation extraction.
   `operate.merge_nodes_and_edges()` writes durable recovery anchors before
   graph mutations, then merges graph nodes and edges and updates vector
   indexes.
6. `LightRAG._insert_done()` flushes the storage backends.

The legacy PDF artifact currently in `rag_storage` is marked `parse_engine:
legacy`; the next phase should use the existing MinerU integration, rather
than adding another PDF parser.

## Query call chain and retrieval modes

1. `POST /query` is defined in `lightrag/api/routers/query_routes.py` and
   calls `LightRAG.aquery()`.
2. `aquery()` validates `QueryParam` and dispatches to retrieval operations in
   `lightrag/operate.py`.
3. `kg_query()` supplies graph-aware local/global/hybrid retrieval; `naive_query()`
   supplies chunk-vector retrieval. The `mix` mode combines graph and vector
   context and is the current default.

Current internal mode names are `local`, `global`, `hybrid`, `naive`, `mix`,
and `bypass` (see `QueryParam` in `lightrag/base.py`). For ScholarGraph, the
future UI adapter should map **VECTOR** to `naive`, **GRAPH** to a documented
graph-only choice (`local` or `global`, based on the question), and **HYBRID**
to `mix`/`hybrid`. That adapter belongs outside the upstream mode API.

## Knowledge graph and storage abstractions

`BaseGraphStorage` exposes graph primitives such as `upsert_node`,
`upsert_edge`, graph retrieval and deletion. The current graph records carry
an open relation representation (`source/target` plus `keywords`,
`description`, provenance and weight), which is appropriate for a project-side
academic relation normalizer before storage writes.

The registry supports the following relevant backends without replacing the
abstraction:

| Need | Existing implementation | Required configuration |
| --- | --- | --- |
| Local Phase 0 vector baseline | `NanoVectorDBStorage` | none |
| Planned paper vector index | `MilvusVectorDBStorage` | `MILVUS_URI`, `MILVUS_DB_NAME` |
| Local Phase 0 graph baseline | `NetworkXStorage` | none |
| Planned paper knowledge graph | `Neo4JStorage` | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` |
| Document lifecycle | `JsonDocStatusStorage` | none |

`lightrag/kg/factory.py::get_storage_class()` resolves these implementations,
so the project should configure existing classes rather than introduce another
vector database or Neo4j abstraction.

## Important existing HTTP interfaces

- Documents: upload/text insertion, listing/status, scan/reprocess and
  `DELETE /documents/delete_document` are in `document_routes.py`. The delete
  endpoint accepts a JSON body containing `doc_ids` plus the optional
  `delete_file` and `delete_llm_cache` flags.
- Queries: `POST /query`, streaming query, and data/context query are in
  `query_routes.py`.
- Graph: `GET /graphs`, graph-label discovery, entity/relation editing and
  graph deletion are in `graph_routes.py`.
- The React client already wraps these APIs in
  `lightrag_webui/src/api/lightrag.ts`, while its existing screens are
  `DocumentManager`, `RetrievalView`, and `GraphViewer`.

## Current environment verification status

| Check | Result | Evidence / blocker |
| --- | --- | --- |
| Windows Python environment | Available for server and retrieval | Python 3.12, `.venv\\Scripts`, the Python `ollama` client, and the `o200k_base` tokenizer cache are present |
| Windows frontend dependencies | Present, but Bun absent | `node_modules` exists; `bun` is not on PATH |
| Windows LightRAG startup | Verified | UTF-8 environment variables plus a local `tiktoken` cache allow the server to start and return `200` from `/health` |
| Packaged WebUI | Verified | `GET /webui/` returns `200` with the React root; `/health` reports `webui_available: true` |
| WSL Ubuntu | Available | Ubuntu 2 mounts this repo at `/mnt/d/dev/LightRAG` |
| WSL Ollama embedding service | Verified | Started the existing `bge-m3:latest` model; Windows can call it at `127.0.0.1:11434` and receives real 1024-dimensional embeddings |
| Vector retrieval | Verified | Exact-title `naive` retrieval returned 17 indexed chunks; the context is 65,156 characters |
| Graph retrieval | Verified | `GET /graphs` returned a 20-node, 32-edge subgraph; keyword-guided `local`, `global`, `hybrid`, and `mix` retrieval all returned graph context |
| Structured mixed retrieval | Verified | `POST /query/data` with `mix` returned 29 entities, 141 relations, 10 chunks, and one source reference |
| Generated answer | Verified | With a valid credential in the ignored local `.env` and outbound network access for the server process, a `mix` query returned a 794-character cited answer with one source reference |
| Existing real indexing | Verified as prior artifact | `PROCESSED` document status plus chunk, vector and GraphML artifacts |
| Fresh isolated upload/index | Verified | A new plain-text paper reached `processed`, produced one chunk, and created a 7-node, 6-edge graph in an isolated workspace |
| Three generated retrieval modes | Verified | `naive`, `local`, and `mix` each answered the GraphTrace evaluation question correctly and returned one reference to the uploaded paper |
| Document and graph deletion | Verified | The official delete endpoint reduced processed documents to zero, removed the uploaded input file, and left zero GraphTrace nodes and edges |

The startup command used for this verification was:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:TIKTOKEN_CACHE_DIR = "$PWD/.cache/lightrag/tiktoken"
lightrag-server --host 127.0.0.1 --port 19621 `
  --working-dir .\rag_storage --input-dir .\inputs
```

The existing WSL model was started with `ollama serve`; it exposes
`bge-m3:latest` at the standard loopback endpoint and is reachable by the
Windows API server through WSL localhost forwarding.

The configured DeepSeek OpenAI-compatible generation endpoint was also
verified directly and through LightRAG. The server process must have outbound
network permission; a sandboxed process can appear healthy while generation
requests fail at the network boundary. Credentials remain only in the ignored
local `.env` and must not be committed.

`tests/api/test_health_auth.py` initially failed before this restoration because
the Python `ollama` package was absent. After installing that missing runtime
dependency, the live server verification above succeeded. No source code was
changed to make this pass. A rerun completed with **9 passed** (two unrelated
third-party deprecation warnings).
The Windows UTF-8 workaround is operational only:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
lightrag-server --host 127.0.0.1 --port 9621
```

For non-default isolated workspaces, set absolute `INPUT_DIR` and `WORKING_DIR`
environment variables in addition to passing `--input-dir` and
`--working-dir`. Parser source-path resolution reads the environment-backed
configuration; setting only the CLI input directory caused the first isolated
upload attempt to report that its legacy source file was missing.

### Isolated end-to-end verification record

The isolated verification server used port `19622` and separate temporary
input/storage directories, leaving the existing real index untouched. The test
paper introduced `GraphTrace`, literature question answering, the ACM dataset,
and Macro-F1. Its upload reached `processed` after extraction, with one chunk
and a graph containing seven nodes and six edges. The graph included the method,
paper, dataset, metric, and vector-index entities.

Generated `naive`, `local`, and `mix` queries all identified literature
question answering as the task and ACM/Macro-F1 as the evaluation dataset and
metric. Each response included one reference to the uploaded source. Calling
`DELETE /documents/delete_document` with `delete_file: true` then removed the
document record, uploaded file, and its graph contribution. A final graph query
returned zero nodes and zero edges. The isolated server was stopped and its
temporary workspace removed after verification.

## Extension boundary for later phases

Keep ScholarGraph-specific code under a new top-level `scholargraph/` package:

- `scholargraph/ingestion/`: passes MinerU structured output and paper metadata
  into the existing LightRAG ingestion APIs.
- `scholargraph/academic/`: entity-profile assets and an academic relation
  normalizer; do not alter the core relation storage schema in the first pass.
- `scholargraph/zotero/`: read-only Local API client, version-based sync, and
  a separate SQLite mapping database linking Zotero items/attachments to RAG
  document IDs.
- `scholargraph/retrieval/`: stable VECTOR/GRAPH/HYBRID adapter and evidence
  shaping over existing query operations.
- `scholargraph/evaluation/`: persisted run records for consistent ablations.

The LightRAG integration points should remain narrow: parser configuration and
ingestion metadata, extraction prompt profiles, configured storage classes,
and the existing REST/WebUI client layers.

## Phase 0 exit condition

Phase 0 is complete. The source architecture, API server, packaged WebUI,
existing real index, fresh document ingestion, vector and graph construction,
structured retrieval, generated answers across three retrieval modes, source
references, and document/graph deletion are verified and documented. No
ScholarGraph feature implementation or Phase 1 work has started; wait for
explicit user confirmation before proceeding.
