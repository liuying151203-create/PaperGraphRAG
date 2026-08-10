"""Run a real academic extraction -> Neo4j -> delete smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import numpy as np

from lightrag import LightRAG
from lightrag.kg.shared_storage import finalize_share_data
from lightrag.utils import EmbeddingFunc, Tokenizer, compute_mdhash_id
from scholargraph.academic import academic_addon_params

PAPER_TEXT = (
    "MetaGraph addresses node classification. The method is evaluated on the "
    "ACM citation dataset using Macro-F1."
)

EXTRACTION_RESULT = (
    "entity<|#|>MetaGraph<|#|>Algorithm<|#|>MetaGraph is a graph method.\n"
    "entity<|#|>ACM<|#|>Benchmark<|#|>ACM is a citation dataset.\n"
    "entity<|#|>Node Classification<|#|>Problem<|#|>Node Classification is a task.\n"
    "entity<|#|>Macro-F1<|#|>Measure<|#|>Macro-F1 is an evaluation metric.\n"
    "relation<|#|>MetaGraph<|#|>ACM<|#|>experimented on<|#|>MetaGraph was evaluated on ACM.\n"
    "relation<|#|>MetaGraph<|#|>Node Classification<|#|>addresses<|#|>MetaGraph addresses node classification.\n"
    "relation<|#|>MetaGraph<|#|>Macro-F1<|#|>measured by<|#|>MetaGraph uses Macro-F1.\n"
    "<|COMPLETE|>"
)


class _TokenizerImpl:
    def encode(self, content: str) -> list[int]:
        return [ord(character) for character in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


async def _embedding(texts: list[str]) -> np.ndarray:
    return np.ones((len(texts), 8), dtype=float)


async def _extract(*args, **kwargs) -> str:
    return EXTRACTION_RESULT


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neo4j-uri", default="bolt://127.0.0.1:7688")
    parser.add_argument("--neo4j-username", default="neo4j")
    parser.add_argument("--neo4j-password", default="scholargraph-local")
    parser.add_argument("--neo4j-database", default="neo4j")
    parser.add_argument(
        "--working-dir", default=".cache/lightrag/neo4j-graph-verify"
    )
    parser.add_argument("--workspace", default="scholargraph_graph_verify")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict:
    os.environ["NEO4J_URI"] = args.neo4j_uri
    os.environ["NEO4J_USERNAME"] = args.neo4j_username
    os.environ["NEO4J_PASSWORD"] = args.neo4j_password
    os.environ["NEO4J_DATABASE"] = args.neo4j_database

    rag = LightRAG(
        working_dir=str(Path(args.working_dir).resolve()),
        workspace=args.workspace,
        llm_model_func=_extract,
        embedding_func=EmbeddingFunc(
            embedding_dim=8,
            max_token_size=8192,
            model_name="neo4j-smoke-embedding",
            func=_embedding,
        ),
        tokenizer=Tokenizer("neo4j-smoke", _TokenizerImpl()),
        graph_storage="Neo4JStorage",
        addon_params=academic_addon_params({"language": "English"}),
        entity_extraction_use_json=False,
        entity_extract_max_gleaning=0,
        max_parallel_insert=1,
    )
    await rag.initialize_storages()
    source = "scholargraph-neo4j-smoke.txt"
    doc_id = compute_mdhash_id(source, prefix="doc-")
    try:
        await rag.apipeline_enqueue_documents(PAPER_TEXT, file_paths=source)
        await rag.apipeline_process_enqueue_documents()

        node_names = ["MetaGraph", "ACM", "Node Classification", "Macro-F1"]
        nodes = {
            name: await rag.chunk_entity_relation_graph.get_node(name)
            for name in node_names
        }
        relation_pairs = [
            ("MetaGraph", "ACM"),
            ("MetaGraph", "Node Classification"),
            ("MetaGraph", "Macro-F1"),
        ]
        edges = {
            f"{source_name}->{target_name}": (
                await rag.chunk_entity_relation_graph.get_edge(
                    source_name, target_name
                )
            )
            for source_name, target_name in relation_pairs
        }
        subgraph = await rag.chunk_entity_relation_graph.get_knowledge_graph(
            "MetaGraph", max_depth=2, max_nodes=50
        )
        before_delete = {
            "nodes": nodes,
            "edges": edges,
            "subgraph_node_count": len(subgraph.nodes),
            "subgraph_edge_count": len(subgraph.edges),
            "is_truncated": subgraph.is_truncated,
        }

        await rag.adelete_by_doc_id(doc_id)
        remaining_labels = await rag.chunk_entity_relation_graph.get_all_labels()
        return {
            "neo4j_uri": args.neo4j_uri,
            "neo4j_database": args.neo4j_database,
            "workspace": args.workspace,
            "before_delete": before_delete,
            "remaining_labels_after_delete": remaining_labels,
        }
    finally:
        await rag.finalize_storages()
        finalize_share_data()


def main() -> None:
    result = asyncio.run(_run(_parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
