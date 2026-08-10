from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_original_argv = sys.argv[:]
sys.argv = [sys.argv[0]]
create_scholargraph_routes = importlib.import_module(
    "scholargraph.api"
).create_scholargraph_routes
sys.argv = _original_argv


class FakeRag:
    async def aquery_llm(self, query, param):
        return {
            "status": "success",
            "message": "ok",
            "data": {
                "references": [{"reference_id": "1", "file_path": "paper.pdf"}],
                "chunks": [
                    {
                        "reference_id": "1",
                        "chunk_id": "chunk-1",
                        "file_path": "paper.pdf",
                        "content": "Evidence text",
                    }
                ],
                "entities": [],
                "relationships": [],
            },
            "metadata": {"query_mode": param.mode},
            "llm_response": {"content": "Answer [1]."},
        }


class FakeZoteroRuntime:
    async def status(self):
        return {"connected": False, "papers": 1, "attachments": 1}

    async def library(self):
        return [{"item_key": "PAPERABC", "attachment_key": "ATTACHAB"}]

    async def sync_once(self):
        raise AssertionError("not called in this route test")

    async def reindex_attachment(self, attachment_key):
        raise AssertionError("not called in this route test")

    async def exclude_attachment(self, attachment_key):
        assert attachment_key == "ATTACHAB"
        return {
            "attachment_key": attachment_key,
            "index_status": "excluded",
            "rag_document_id": None,
        }


def _client(working_dir: Path) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_scholargraph_routes(
            FakeRag(),  # type: ignore[arg-type]
            working_dir=working_dir,
            zotero_runtime=FakeZoteroRuntime(),  # type: ignore[arg-type]
        )
    )
    return TestClient(app)


def test_scholar_query_exposes_stable_strategy_and_evidence(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/scholar/query",
        json={"query": "What evidence exists?", "strategy": "VECTOR"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "VECTOR"
    assert payload["lightrag_mode"] == "naive"
    assert payload["answer"] == "Answer [1]."
    assert payload["evidence"]["vector"][0]["chunk_id"] == "chunk-1"


def test_zotero_status_library_and_delete_index_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.get("/scholar/zotero/status").json()["connected"] is False
    assert client.get("/scholar/zotero/library").json()[0]["item_key"] == "PAPERABC"
    deleted = client.delete("/scholar/zotero/attachments/ATTACHAB/index")
    assert deleted.status_code == 200
    assert deleted.json()["index_status"] == "excluded"


def test_evaluation_dataset_run_and_records_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)

    datasets = client.get("/scholar/evaluation/datasets")
    assert datasets.status_code == 200
    assert datasets.json()[0]["paper_count"] == 6
    assert datasets.json()[0]["question_count"] == 6

    run = client.post("/scholar/evaluation/runs", json={})
    assert run.status_code == 200
    summary = run.json()
    assert summary["record_count"] == 18
    assert [mode["retrieval_mode"] for mode in summary["modes"]] == [
        "VECTOR",
        "GRAPH",
        "HYBRID",
    ]

    listed = client.get("/scholar/evaluation/runs").json()
    assert listed[0]["run_id"] == summary["run_id"]
    detail = client.get(f"/scholar/evaluation/runs/{summary['run_id']}").json()
    assert len(detail["records"]) == 18
