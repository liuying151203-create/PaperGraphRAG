# ScholarGraph Phase 6: Retrieval, Evidence, and WebUI

Phase 6 provides a stable research-facing query contract over LightRAG and a
WebUI workflow for managing papers, asking questions, inspecting evidence, and
filtering the academic knowledge graph.

## Retrieval strategies

The public strategy names are deliberately independent from LightRAG's
internal mode names:

| ScholarGraph strategy | LightRAG mode | Evidence used |
| --- | --- | --- |
| `VECTOR` | `naive` | semantic text chunks |
| `GRAPH` | `hybrid` | entities, relations, and their source chunks |
| `HYBRID` | `mix` | graph evidence plus semantic chunks |

`POST /scholar/query` accepts one strategy and performs one LightRAG query. The
response returns the answer and the exact structured evidence produced by that
same query, avoiding a second retrieval pass that could disagree with the
answer context.

Example request:

```json
{
  "query": "Which datasets are used to evaluate graph RAG methods?",
  "strategy": "HYBRID",
  "collection_key": "ABCD1234"
}
```

`collection_key` is optional. When present, an exact metadata filter is applied
before token truncation and answer generation to vector chunks and to every
graph entity/relation source id. The collection key is also part of the answer
cache key, so answers cannot be reused across collection scopes.

## Evidence contract

The query response contains:

- `evidence.vector`: chunk id, score when available, section/page, text, and
  paper metadata.
- `evidence.entities`: academic entity type, description, graph source ids,
  and file paths.
- `evidence.relations`: source, target, canonical relation keyword, weight,
  graph source ids, and file paths.
- `evidence.sources`: a deduplicated paper/source list used by citations.

Document metadata is read from the persisted text chunk record only when a
caller requests it. It remains structured evidence and is not injected into
the LLM prompt. This keeps bibliographic fields available to the UI without
increasing the answer token budget.

## ScholarGraph routes

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/scholar/query` | Answer with vector/graph evidence |
| `GET` | `/scholar/zotero/status` | Connection and index counts |
| `GET` | `/scholar/zotero/library` | Synced attachment rows |
| `POST` | `/scholar/zotero/sync` | Run incremental sync |
| `POST` | `/scholar/zotero/attachments/{key}/reindex` | Retry or refresh one PDF |
| `DELETE` | `/scholar/zotero/attachments/{key}/index` | Remove only derived RAG data |

All routes reuse the server's existing API-key/JWT authentication dependency.
Deleting an index never writes to Zotero and never deletes the Zotero PDF.

## WebUI workflow

- **Library** shows Zotero connectivity and Papers, Indexed, Processing, and
  Failed counts; it offers Sync Now, Reindex, and Delete Index actions.
- **Ask Papers** selects Vector, Graph, or Hybrid retrieval, optionally scopes
  a query to a Zotero collection, and splits evidence into Vector, Graph, and
  Sources sections.
- **Knowledge Graph** retains label search and adds a multi-select academic type
  filter for Paper, Method, Task, Dataset, Metric, Model, Concept, Attack, and
  Defense. Edges connected to hidden nodes are hidden as well.
- Existing Documents, Knowledge Graph, Retrieval/API infrastructure remains
  available; the former Retrieval navigation item is presented as Ask Papers.

Zotero's Local API exposes collection keys rather than guaranteed collection
names in item records, so the first UI version labels a scope as
`Collection <key>`. A future optional collection lookup can replace the label
without changing the query contract.

## Validation

```powershell
.\.venv\Scripts\python.exe -B -m pytest `
  tests/scholargraph/retrieval `
  tests/scholargraph/ingestion `
  tests/scholargraph/zotero `
  tests/scholargraph/api -q

cd lightrag_webui
node.exe node_modules\eslint\bin\eslint.js src
node.exe node_modules\typescript\bin\tsc --noEmit
node.exe node_modules\vite\bin\vite.js build
```

The isolated server smoke check uses file-based storages and verifies the built
`/webui/`, `/openapi.json`, and Zotero status endpoint without sending an LLM
query or changing a production workspace.

