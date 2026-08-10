# ScholarGraph Phase 2: Academic Ontology Adapter

## Outcome

Phase 2 adds an academic entity schema and deterministic relation normalizer to
LightRAG's existing extraction and graph pipeline. It does not introduce a
second graph model or change the storage schema.

The supported entity types are:

- `Paper`
- `Method`
- `Task`
- `Dataset`
- `Metric`
- `Model`
- `Concept`
- `Attack`
- `Defense`

The v1 canonical relations are:

- `PROPOSES`
- `ADDRESSES`
- `EVALUATED_ON`
- `USES_METRIC`
- `BASED_ON`
- `COMPARES_WITH`
- `OUTPERFORMS`
- `ATTACKS`
- `DEFENDS_AGAINST`
- `CITES`

## Reused LightRAG capabilities

LightRAG already provides all of the expensive and storage-sensitive parts:

1. `addon_params['entity_types_guidance']` is injected into both text and JSON
   extraction prompts.
2. Text and JSON extraction parsers emit the same open records:
   `entity_name/entity_type/description` and
   `src_id/tgt_id/keywords/description`.
3. `merge_nodes_and_edges` persists those records through the configured graph
   and vector storage abstractions.
4. Recovery anchors and cache-backed graph rebuild use the same parsed records.

ScholarGraph therefore keeps LightRAG's graph records and stores the canonical
relation in the existing `keywords` field.

## Added capability

### Domain module

`scholargraph/academic/` owns the project-specific ontology:

- `schema.py`: entity enum, aliases, storage labels, prompt guidance.
- `relations.py`: relation enum, phrase aliases, endpoint signatures.
- `normalizer.py`: LightRAG result adapter and addon configuration helper.

Example normalizations:

| Extracted value | Canonical value |
|---|---|
| `algorithm` | entity type `method` |
| `benchmark` | entity type `dataset` |
| `problem` | entity type `task` |
| `experimented on` | relation `EVALUATED_ON` |
| `measured by` | relation `USES_METRIC` |

Known relation phrases are canonicalized only when the source and target entity
types satisfy the ontology signature. Unknown or invalid relations retain their
original `keywords`, preserving source-grounded information instead of silently
dropping it. LightRAG-injected `drawing`, `table`, and `equation` entities are
also preserved.

### Minimal LightRAG extension point

`lightrag/operate.py` now recognizes the optional callable:

```python
addon_params["extraction_result_normalizer"]
```

It accepts `(nodes, edges, chunk_data)` and returns `(nodes, edges)`. Sync and
async callables are supported and the return contract is validated.

The hook is applied in both places that must agree:

```text
Initial extraction -> parse -> glean/MM merge -> normalize -> graph merge
Cached extraction  -> parse -> normalize          -> graph rebuild
```

Applying it to cache-backed rebuilds is required for correct shared-graph
deletion and recovery. Otherwise a normalized object could be written under one
identity and later rebuilt from its raw cached identity.

## Configuration

### Python

```python
from lightrag import LightRAG
from scholargraph.academic import academic_addon_params

rag = LightRAG(
    ...,
    addon_params=academic_addon_params({"language": "English"}),
)
```

### API server

Set this environment variable before starting the existing server:

```dotenv
SCHOLARGRAPH_ACADEMIC_ONTOLOGY=true
```

Then start LightRAG normally. The health response makes the effective state
observable:

```powershell
Invoke-RestMethod http://127.0.0.1:9621/health |
  Select-Object -ExpandProperty configuration |
  Select-Object academic_ontology
```

No environment variable means the upstream extraction behavior remains
unchanged.

## Storage and direction caveat

The current LightRAG graph merge treats relationships as undirected and sorts
the endpoint key. Phase 2 consequently validates both endpoint orientations.
The canonical keyword describes the scientific relation, but applications must
not yet infer a guaranteed directed edge from the physical graph orientation.
A directed relation-storage migration is intentionally outside this phase.

## Verification

### Automated tests

- Academic schema, aliases, signatures, non-mutating adapter, and addon builder.
- Sync/async LightRAG hook contract validation.
- A real `LightRAG.ainsert` flow using JSON/NetworkX/NanoVector storage with a
  deterministic LLM and embedding function.
- Existing extraction prompt and API health regressions.

Observed results:

- Focused offline suite: `24 passed`.
- Academic pipeline plus API health suite: `18 passed`.
- Full related extraction suite: `93 passed`, with one unrelated Windows-only
  path-message assertion failure. The test expects `file name only`, while an
  absolute Windows path first triggers the existing `directory separators`
  validation.

The real pipeline test persisted:

```text
MetaGraph             type=method
ACM                   type=dataset
Node Classification   type=task
Macro-F1              type=metric

MetaGraph -- ACM                  keywords=EVALUATED_ON
MetaGraph -- Node Classification  keywords=ADDRESSES
MetaGraph -- Macro-F1             keywords=USES_METRIC
```

### Isolated API service

An isolated server was started on `127.0.0.1:19623` with the academic flag. Its
health response reported:

```json
{
  "academic_ontology": true,
  "graph_storage": "NetworkXStorage",
  "vector_storage": "NanoVectorDBStorage",
  "summary_language": "English"
}
```

The isolated process was stopped after verification. The existing service on
port 19621 remained healthy and untouched.

## Phase boundary

Phase 2 deliberately does not implement Milvus or Neo4j itself. The academic
adapter operates above LightRAG's storage interfaces, so Phase 3 can switch to
the existing Milvus and Neo4j implementations without changing this ontology
module.
