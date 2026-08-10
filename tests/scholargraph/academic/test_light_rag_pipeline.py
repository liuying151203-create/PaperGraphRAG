from __future__ import annotations

import asyncio
from uuid import uuid4

import numpy as np

from lightrag import LightRAG
from lightrag.kg.shared_storage import finalize_share_data, initialize_share_data
from lightrag.utils import EmbeddingFunc, Tokenizer
from scholargraph.academic import academic_addon_params


class _TokenizerImpl:
    def encode(self, content: str) -> list[int]:
        return [ord(character) for character in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


async def _embedding(texts: list[str]) -> np.ndarray:
    return np.ones((len(texts), 8), dtype=float)


async def _llm(*args, **kwargs) -> str:
    return (
        "entity<|#|>MetaGraph<|#|>Algorithm<|#|>MetaGraph is a graph method.\n"
        "entity<|#|>ACM<|#|>Benchmark<|#|>ACM is a citation dataset.\n"
        "entity<|#|>Node Classification<|#|>Problem<|#|>Node Classification is a task.\n"
        "entity<|#|>Macro-F1<|#|>Measure<|#|>Macro-F1 is an evaluation metric.\n"
        "relation<|#|>MetaGraph<|#|>ACM<|#|>experimented on<|#|>MetaGraph was evaluated on ACM.\n"
        "relation<|#|>MetaGraph<|#|>Node Classification<|#|>addresses<|#|>MetaGraph addresses node classification.\n"
        "relation<|#|>MetaGraph<|#|>Macro-F1<|#|>measured by<|#|>MetaGraph uses Macro-F1.\n"
        "<|COMPLETE|>"
    )


def _chunking(*args) -> list[dict]:
    content = args[1]
    return [{"tokens": len(content), "content": content, "chunk_order_index": 0}]


def test_real_light_rag_pipeline_persists_academic_ontology(tmp_path) -> None:
    async def _run() -> None:
        initialize_share_data()
        rag = LightRAG(
            working_dir=str(tmp_path / "academic-rag"),
            workspace=f"academic-{uuid4().hex[:8]}",
            llm_model_func=_llm,
            embedding_func=EmbeddingFunc(
                embedding_dim=8,
                max_token_size=8192,
                func=_embedding,
            ),
            tokenizer=Tokenizer("academic-test", _TokenizerImpl()),
            chunking_func=_chunking,
            addon_params=academic_addon_params({"language": "English"}),
            entity_extraction_use_json=False,
            entity_extract_max_gleaning=0,
            max_parallel_insert=1,
        )
        await rag.initialize_storages()
        try:
            await rag.ainsert(
                "MetaGraph addresses node classification and is evaluated on ACM "
                "using Macro-F1."
            )

            method = await rag.chunk_entity_relation_graph.get_node("MetaGraph")
            dataset = await rag.chunk_entity_relation_graph.get_node("ACM")
            task = await rag.chunk_entity_relation_graph.get_node(
                "Node Classification"
            )
            metric = await rag.chunk_entity_relation_graph.get_node("Macro-F1")
            evaluated_on = await rag.chunk_entity_relation_graph.get_edge(
                "MetaGraph", "ACM"
            )
            addresses = await rag.chunk_entity_relation_graph.get_edge(
                "MetaGraph", "Node Classification"
            )
            uses_metric = await rag.chunk_entity_relation_graph.get_edge(
                "MetaGraph", "Macro-F1"
            )

            assert method["entity_type"] == "method"
            assert dataset["entity_type"] == "dataset"
            assert task["entity_type"] == "task"
            assert metric["entity_type"] == "metric"
            assert evaluated_on["keywords"] == "EVALUATED_ON"
            assert addresses["keywords"] == "ADDRESSES"
            assert uses_metric["keywords"] == "USES_METRIC"
        finally:
            await rag.finalize_storages()
            finalize_share_data()

    asyncio.run(_run())
