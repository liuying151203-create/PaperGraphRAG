# ScholarGraph Phase 4: Neo4j Academic Graph

## Outcome

ScholarGraph now has a reproducible academic graph baseline using LightRAG's
existing graph-storage contract:

```text
Academic extraction
  -> ontology normalization
  -> Neo4JStorage
  -> node/edge and bounded subgraph queries
  -> attribution-safe document deletion
```

No second graph abstraction or parallel schema was introduced.

## Source analysis and reuse

LightRAG already provides the required Neo4j behavior:

- `Neo4JStorage` is selected with `LIGHTRAG_GRAPH_STORAGE=Neo4JStorage`.
- A workspace-specific Neo4j label isolates each LightRAG workspace.
- Nodes are merged by `entity_id` and retain `entity_type`, `description`, and
  source attribution.
- Relations retain their academic ontology name in the `keywords` property.
- Batched node and edge upserts, B-Tree indexes, CJK full-text indexes, degree
  queries, label queries, and document-aware deletion already exist.
- Bounded subgraph traversal uses APOC when available and automatically falls
  back to basic Cypher breadth-first traversal when APOC is absent.
- `LightRAG.adelete_by_doc_id` uses recovery anchors and source attribution to
  remove only the selected document's graph contributions.

ScholarGraph adds deployment and end-to-end verification assets only:

- `docker/scholargraph-neo4j.yml`
- `scripts/verify_scholargraph_neo4j.py`

## Relationship representation

LightRAG stores graph edges using the physical Neo4j relationship type
`DIRECTED`. The normalized academic relation is stored in `keywords`, such as
`EVALUATED_ON`, `ADDRESSES`, or `USES_METRIC`.

The storage merge orders the two endpoint identifiers for deterministic
deduplication. Consequently, consumers must use the academic `keywords`
property and the domain schema to interpret semantics; they must not infer
academic direction solely from the physical Neo4j arrow.

## Local Neo4j deployment

The compose service binds only to localhost and uses ports that avoid Neo4j's
usual defaults:

| Endpoint | Host binding |
|---|---|
| Neo4j Browser/HTTP | `127.0.0.1:7475` |
| Bolt | `127.0.0.1:7688` |

Start the isolated service with:

```powershell
docker compose -f docker/scholargraph-neo4j.yml -p scholargraph-neo4j up -d --wait
```

The verified default is Neo4j `5.26-community`. Override the image tag or local
password without editing the compose file:

```powershell
$env:SCHOLARGRAPH_NEO4J_VERSION = '5.26-community'
$env:SCHOLARGRAPH_NEO4J_PASSWORD = '<local-password>'
docker compose -f docker/scholargraph-neo4j.yml -p scholargraph-neo4j up -d --wait
```

The default password is intended only for an isolated loopback development
service.

## LightRAG server configuration

```dotenv
LIGHTRAG_GRAPH_STORAGE=Neo4JStorage
NEO4J_URI=bolt://127.0.0.1:7688
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=scholargraph-local
NEO4J_DATABASE=neo4j
SCHOLARGRAPH_ACADEMIC_ONTOLOGY=true
```

The server health response should report:

```json
{
  "graph_storage": "Neo4JStorage",
  "academic_ontology": true
}
```

## Reproducible graph smoke test

Run the verifier as a module so the repository root remains on Python's import
path:

```powershell
python -m scripts.verify_scholargraph_neo4j `
  --neo4j-uri bolt://127.0.0.1:7688 `
  --neo4j-password scholargraph-local `
  --working-dir .cache/lightrag/phase4-neo4j-smoke `
  --workspace phase4_smoke
```

The script uses a deterministic extraction response and exercises the real
LightRAG pipeline. It then reads individual nodes and edges, requests a
two-hop subgraph, and deletes the source through the public document deletion
API.

## Verification results

The real Neo4j run persisted four normalized academic nodes:

- `MetaGraph` (`method`)
- `ACM` (`dataset`)
- `Node Classification` (`task`)
- `Macro-F1` (`metric`)

It persisted three normalized relations:

- `MetaGraph` to `ACM`: `EVALUATED_ON`
- `MetaGraph` to `Node Classification`: `ADDRESSES`
- `MetaGraph` to `Macro-F1`: `USES_METRIC`

The bounded query returned four nodes and three edges with
`is_truncated=false`. The verified community image did not include APOC, so the
automatic basic-Cypher traversal path was exercised successfully.

Document deletion then removed three relations, four entities, and one chunk.
A final label query returned an empty list, demonstrating that the graph did
not retain unattributed objects from the test document.

An isolated API server on port 19625 also initialized successfully against the
same Neo4j service. `/health` reported `Neo4JStorage`, workspace `phase4_api`,
and `academic_ontology=true`.

Neo4j storage tests:

```text
42 passed, 6 skipped
```

Compose validation, Ruff, and Python compilation checks also passed.

## Teardown

```powershell
docker compose -f docker/scholargraph-neo4j.yml -p scholargraph-neo4j down -v
```

The `-v` option removes only volumes owned by that exact compose project.

## Phase boundary

This phase establishes Neo4j persistence and graph traversal. Zotero remains
the bibliographic source of truth; the next phase adds a separate mapping
database and version-based Zotero Local API synchronization into LightRAG.
