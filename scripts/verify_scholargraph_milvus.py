"""Run a real BGE-m3 -> Milvus write and TopK retrieval smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from functools import partial
from pathlib import Path

from lightrag import LightRAG
from lightrag.kg.shared_storage import finalize_share_data
from lightrag.llm.ollama import ollama_embed
from lightrag.utils import EmbeddingFunc

DEFAULT_CONTENT = (
    "MetaGraph is a graph retrieval method for scientific papers. "
    "It is evaluated on the ACM citation network for node classification. "
    "Macro-F1 measures its classification quality. ScholarGraph combines "
    "semantic vector retrieval with academic graph evidence."
)


async def _unexpected_llm_call(*args, **kwargs) -> str:
    raise RuntimeError("The vector-only smoke test must not call an LLM")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milvus-uri", default="http://127.0.0.1:19531")
    parser.add_argument("--milvus-db", default="scholargraph_vector_verify")
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--embedding-model", default="bge-m3:latest")
    parser.add_argument("--embedding-dim", type=int, default=1024)
    parser.add_argument(
        "--working-dir", default=".cache/lightrag/milvus-vector-verify"
    )
    parser.add_argument("--workspace", default="scholargraph_vector_verify")
    parser.add_argument("--query", default="Which method uses graph retrieval?")
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict:
    os.environ["MILVUS_URI"] = args.milvus_uri
    os.environ["MILVUS_DB_NAME"] = args.milvus_db

    embedding_func = EmbeddingFunc(
        embedding_dim=args.embedding_dim,
        max_token_size=8192,
        model_name=args.embedding_model,
        supports_asymmetric=True,
        func=partial(
            ollama_embed.func,
            embed_model=args.embedding_model,
            host=args.ollama_host,
        ),
    )
    rag = LightRAG(
        working_dir=str(Path(args.working_dir).resolve()),
        workspace=args.workspace,
        llm_model_func=_unexpected_llm_call,
        embedding_func=embedding_func,
        vector_storage="MilvusVectorDBStorage",
        max_parallel_insert=1,
    )
    await rag.initialize_storages()
    try:
        await rag.apipeline_enqueue_documents(
            DEFAULT_CONTENT,
            file_paths="scholargraph-vector-smoke.txt",
            process_options="!",
        )
        await rag.apipeline_process_enqueue_documents()
        results = await rag.chunks_vdb.query(args.query, top_k=args.top_k)
        statuses = await rag.doc_status.get_all_status_counts()
        return {
            "milvus_uri": args.milvus_uri,
            "milvus_db": args.milvus_db,
            "embedding_model": args.embedding_model,
            "embedding_dim": args.embedding_dim,
            "workspace": args.workspace,
            "document_status_counts": statuses,
            "top_k": args.top_k,
            "result_count": len(results),
            "results": results,
        }
    finally:
        await rag.finalize_storages()
        finalize_share_data()


def main() -> None:
    result = asyncio.run(_run(_parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
