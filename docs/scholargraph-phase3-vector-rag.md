# ScholarGraph Phase 3: BGE-m3 + Milvus Vector RAG

## Outcome

ScholarGraph now has a reproducible Vector-only baseline using the existing
LightRAG embedding and vector-storage abstractions:

```text
Paper content
  -> LightRAG chunking
  -> Ollama bge-m3:latest (1024 dimensions)
  -> MilvusVectorDBStorage
  -> COSINE TopK retrieval
```

No vector database implementation was added to ScholarGraph.

## Source analysis and reuse

LightRAG already implements the required runtime:

- `EmbeddingFunc` validates dimensions and distinguishes document/query
  embedding contexts.
- `lightrag.llm.ollama.ollama_embed` defines BGE-m3 as a 1024-dimensional,
  8192-token embedding model.
- `MilvusVectorDBStorage` is registered under `VECTOR_STORAGE` and selected by
  `LIGHTRAG_VECTOR_STORAGE=MilvusVectorDBStorage`.
- Separate Milvus collections store chunk, entity, and relationship vectors.
- Embeddings are buffered and written in bounded batches during
  `index_done_callback`; queries only see flushed data.
- Collection schemas include the embedding model and dimension in their names,
  preventing incompatible vector spaces from sharing one collection.
- Milvus database creation, workspace prefixes, AUTOINDEX/HNSW/IVF settings,
  COSINE/L2/IP metrics, migration retry, and payload limits are already handled
  in `lightrag/kg/milvus_impl.py`.

The ScholarGraph additions are deployment and verification assets only:

- `docker/scholargraph-milvus.yml`
- `scripts/verify_scholargraph_milvus.py`

## Local Milvus deployment

The compose file runs isolated Milvus standalone, etcd, and MinIO services. It
binds only to localhost and uses ports chosen not to collide with LightRAG's
sample stack:

| Service | Host binding |
|---|---|
| Milvus gRPC/HTTP | `127.0.0.1:19531` |
| Milvus health/metrics | `127.0.0.1:9092` |

Start it with:

```powershell
docker compose -f docker/scholargraph-milvus.yml -p scholargraph-milvus up -d --wait
```

The default versions (`Milvus v2.5.4`, compatible MinIO, etcd v3.5.25) match
the verified offline environment. They can be overridden without editing the
file:

```powershell
$env:SCHOLARGRAPH_MILVUS_VERSION = 'v2.6.11'
$env:SCHOLARGRAPH_MINIO_VERSION = 'RELEASE.2025-09-07T16-13-09Z'
docker compose -f docker/scholargraph-milvus.yml -p scholargraph-milvus up -d --wait
```

`HNSW_SQ` must not be selected on Milvus 2.5.4. LightRAG validates that index
as requiring Milvus 2.6.8 or newer. The verified configuration uses the default
`AUTOINDEX` with `COSINE`.

## LightRAG server configuration

```dotenv
LIGHTRAG_VECTOR_STORAGE=MilvusVectorDBStorage
MILVUS_URI=http://127.0.0.1:19531
MILVUS_DB_NAME=scholargraph

EMBEDDING_BINDING=ollama
EMBEDDING_BINDING_HOST=http://127.0.0.1:11434
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=1024
EMBEDDING_MAX_TOKEN_SIZE=8192
```

The server health response should report:

```json
{
  "embedding_model": "bge-m3:latest",
  "vector_storage": "MilvusVectorDBStorage"
}
```

## Reproducible Vector-only smoke test

The verification script deliberately configures an LLM function that raises if
called, then enqueues a document with LightRAG's `process_options="!"`. This
proves indexing and retrieval do not depend on entity extraction or generation.

```powershell
$env:TIKTOKEN_CACHE_DIR = '.cache/lightrag/tiktoken'
python scripts/verify_scholargraph_milvus.py `
  --milvus-uri http://127.0.0.1:19531 `
  --milvus-db scholargraph_vector_verify `
  --ollama-host http://127.0.0.1:11434
```

The script performs:

1. LightRAG storage initialization.
2. Raw document enqueue and fixed-token chunking.
3. BGE-m3 document embedding.
4. Milvus flush.
5. BGE-m3 query embedding.
6. Direct `chunks_vdb.query(..., top_k=3)` retrieval.
7. JSON output with document status and returned evidence.

## Verification results

### Runtime

Verified components:

- Ollama model: `bge-m3:latest`
- embedding dimension: `1024`
- Milvus server: `v2.5.4`
- index: `AUTOINDEX`
- metric: `COSINE`
- LightRAG workspace: `phase3_smoke`
- document status: `processed=1`, `failed=0`
- retrieved chunks: `1`
- observed similarity distance: `0.609340250492096`

The returned evidence contained the indexed MetaGraph/ACM/Macro-F1 paragraph
and its LightRAG `full_doc_id`, `chunk_id`, and source file.

An isolated API server was also started on port 19624 and successfully created
all three Milvus collections while reporting the correct BGE-m3 and storage
configuration in `/health`.

### Tests

Milvus index configuration, constructor kwargs, deferred embedding, batching,
collection creation, schema, and version behavior:

```text
125 passed
```

Static checks for the verification script also passed.

## Observed ingestion boundary

During HTTP-only testing, filename-hint uploads using the legacy/native parser
reported that the hint-stripped pending filename was missing even though the
uploaded source file existed under `INPUT_DIR`. This is an existing parser
pending-file boundary, not a Milvus failure. A normal `/documents/text` request
reached chunking but then correctly failed when the isolated process could not
connect to the external extraction LLM.

The final Vector-only acceptance therefore used LightRAG's public Python
pipeline with `process_options="!"`, while the actual API service was separately
validated for startup and Milvus collection creation. No failed status was
reported as success.

## Teardown

```powershell
docker compose -f docker/scholargraph-milvus.yml -p scholargraph-milvus down -v
```

The `-v` option removes only volumes belonging to that exact compose project.

## Phase boundary

This phase establishes the Vector-only baseline. Neo4j graph persistence and
graph-path validation are handled in the next phase using LightRAG's existing
`Neo4JStorage` implementation.
