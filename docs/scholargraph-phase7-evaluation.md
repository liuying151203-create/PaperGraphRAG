# ScholarGraph Phase 7: Evaluation and Ablation

Phase 7 adds a reproducible comparison harness for Vector-only, Graph-only,
and Hybrid retrieval. It calls the same `ScholarRetrievalService` used by Ask
Papers, so evaluation does not maintain a separate retrieval implementation.

No benchmark scores are checked into the repository. Results are created only
by a real run against the user's configured index, embedding model, and LLM.

## Development dataset

`data/scholargraph/evaluation/graph_rag_dev_v1.json` declares six public arXiv
papers:

1. Semi-Supervised Classification with Graph Convolutional Networks
2. Graph Attention Networks
3. Inductive Representation Learning on Large Graphs (GraphSAGE)
4. Adversarial Attacks on Graph Neural Networks via Meta Learning
5. Graph Structure Learning for Robust Graph Neural Networks (Pro-GNN)
6. GNNGuard: Defending Graph Neural Networks against Adversarial Attacks

The six questions cover fact retrieval, method retrieval, dataset retrieval,
cross-document comparison, method-to-threat relations, and multi-hop
attack-to-defense reasoning. Each question includes a human-written reference
answer plus explicit expected answer/evidence term groups. These expectations
are inputs to transparent metrics; they are not generated model results.

Download the PDFs from the manifest:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_scholargraph_eval.py `
  --output inputs\scholargraph-eval
```

The downloader skips existing files, validates the PDF signature, writes a
temporary `.part` file, and then renames it into place. Use `--force` only when
the local copies should be replaced. Index the downloaded PDFs through the
normal ScholarGraph/MinerU ingestion flow before running the benchmark.

## Fair-run controls

One `AblationConfig` is reused for every cell in a run:

- dataset and question text;
- query-role LLM and embedding configuration labels;
- `top_k` and `chunk_top_k`;
- entity, relation, and total context budgets;
- generation prompt;
- rerank setting (off by default for the three-mode baseline);
- optional Zotero collection scope.

The runner is deliberately sequential. This avoids making one strategy suffer
from provider throttling caused by concurrent evaluation cells and makes logs
and timing easier to audit.

## Recorded fields

Every query/strategy cell is appended to `<run_id>.jsonl` under
`WORKING_DIR/scholargraph-evaluations/` with:

- run, dataset, query, category, and retrieval-mode identifiers;
- answer and the complete structured evidence trace;
- end-to-end latency;
- token usage when the provider exposes it;
- correctness, evidence recall, faithfulness, and citation validity;
- status and error text for failed cells.

A compact `<run_id>.summary.json` stores per-mode averages and failure counts.
Failed cells remain visible and do not receive invented answers or scores.

## Metric interpretation

- **Answer correctness** is expected-term-group coverage. It is deterministic,
  inspectable, and intentionally weaker than expert semantic grading.
- **Evidence recall** applies the same group-recall rule to retrieved sources,
  chunks, entities, and relations.
- **Citation validity** is the fraction of numeric citations in the answer that
  resolve to returned source reference ids.
- **Faithfulness** is `null` unless a `FaithfulnessJudge` implementation is
  explicitly configured. The default does not pretend lexical overlap proves
  factual grounding.
- **Latency** is measured around the complete retrieval and answer call.

This design makes a real judge easy to add later while keeping the initial
benchmark auditable and free of fabricated semantic scores.

## API and WebUI

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/scholar/evaluation/datasets` | List checked-in dataset metadata |
| `POST` | `/scholar/evaluation/runs` | Execute the controlled three-mode run |
| `GET` | `/scholar/evaluation/runs` | List summaries, newest first |
| `GET` | `/scholar/evaluation/runs/{run_id}` | Read summary and all JSONL records |

The Evaluation page displays dataset coverage and a comparison table for
answer correctness, evidence recall, faithfulness, citation validity, latency,
and failures. Starting a run requires an explicit browser confirmation because
the six-question dataset performs 18 generated-answer calls.

## Validation

```powershell
.\.venv\Scripts\python.exe -B -m pytest `
  tests\scholargraph\evaluation `
  tests\scholargraph\api -q

.\.venv\Scripts\python.exe -m ruff check `
  scholargraph tests\scholargraph scripts\prepare_scholargraph_eval.py

cd lightrag_webui
node.exe node_modules\eslint\bin\eslint.js src
node.exe node_modules\typescript\bin\tsc --noEmit
node.exe node_modules\vite\bin\vite.js build
```

