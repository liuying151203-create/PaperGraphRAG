"""FastAPI routes for ScholarGraph retrieval and Zotero integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from lightrag.api.utils_api import get_combined_auth_dependency, internal_server_error
from scholargraph.evaluation import (
    AblationConfig,
    EvaluationRunner,
    EvaluationStore,
    load_evaluation_dataset,
)
from scholargraph.retrieval import (
    ScholarQueryRequest,
    ScholarQueryResponse,
    ScholarRetrievalService,
)
from scholargraph.zotero import (
    ScholarGraphZoteroRuntime,
    ZoteroLocalAPIError,
    sync_report_dict,
)

if TYPE_CHECKING:
    from lightrag import LightRAG


def create_scholargraph_routes(
    rag: LightRAG,
    *,
    api_key: str | None = None,
    working_dir: str | Path = ".",
    zotero_runtime: ScholarGraphZoteroRuntime | None = None,
) -> APIRouter:
    """Create isolated ScholarGraph routes over one initialized LightRAG."""
    router = APIRouter(prefix="/scholar", tags=["scholargraph"])
    auth = get_combined_auth_dependency(api_key)
    retrieval = ScholarRetrievalService(rag)
    evaluation_store = EvaluationStore(
        Path(working_dir) / "scholargraph-evaluations"
    )
    evaluation_runner = EvaluationRunner(retrieval, evaluation_store)
    runtime = zotero_runtime or ScholarGraphZoteroRuntime(
        rag,
        database_path=Path(working_dir) / "scholargraph-zotero.sqlite3",
    )

    @router.post(
        "/query",
        response_model=ScholarQueryResponse,
        dependencies=[Depends(auth)],
    )
    async def scholar_query(request: ScholarQueryRequest) -> ScholarQueryResponse:
        try:
            return await retrieval.query(request)
        except Exception as exc:  # noqa: BLE001 - API exception boundary
            raise internal_server_error(exc)

    @router.get("/zotero/status", dependencies=[Depends(auth)])
    async def zotero_status() -> dict[str, object]:
        return await runtime.status()

    @router.get("/zotero/library", dependencies=[Depends(auth)])
    async def zotero_library() -> list[dict[str, object]]:
        return await runtime.library()

    @router.post("/zotero/sync", dependencies=[Depends(auth)])
    async def zotero_sync() -> dict[str, object]:
        try:
            return sync_report_dict(await runtime.sync_once())
        except ZoteroLocalAPIError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post(
        "/zotero/attachments/{attachment_key}/reindex",
        dependencies=[Depends(auth)],
    )
    async def zotero_reindex(attachment_key: str) -> dict[str, object]:
        try:
            return sync_report_dict(await runtime.reindex_attachment(attachment_key))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ZoteroLocalAPIError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.delete(
        "/zotero/attachments/{attachment_key}/index",
        dependencies=[Depends(auth)],
    )
    async def zotero_delete_index(attachment_key: str) -> dict[str, object]:
        try:
            return await runtime.exclude_attachment(attachment_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/evaluation/datasets", dependencies=[Depends(auth)])
    async def evaluation_datasets() -> list[dict[str, object]]:
        dataset = load_evaluation_dataset()
        return [
            {
                "dataset_id": dataset.dataset_id,
                "version": dataset.version,
                "description": dataset.description,
                "paper_count": len(dataset.papers),
                "question_count": len(dataset.questions),
                "categories": sorted(
                    {question.category.value for question in dataset.questions}
                ),
            }
        ]

    @router.get("/evaluation/runs", dependencies=[Depends(auth)])
    async def evaluation_runs() -> list[dict[str, object]]:
        return [
            summary.model_dump(mode="json")
            for summary in evaluation_store.list_summaries()
        ]

    @router.get("/evaluation/runs/{run_id}", dependencies=[Depends(auth)])
    async def evaluation_run(run_id: str) -> dict[str, object]:
        try:
            summary = evaluation_store.get_summary(run_id)
            if summary is None:
                raise HTTPException(status_code=404, detail="evaluation run not found")
            return {
                "summary": summary.model_dump(mode="json"),
                "records": [
                    record.model_dump(mode="json")
                    for record in evaluation_store.get_records(run_id)
                ],
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/evaluation/runs", dependencies=[Depends(auth)])
    async def start_evaluation_run(
        config: AblationConfig,
    ) -> dict[str, object]:
        try:
            dataset = load_evaluation_dataset()
            summary = await evaluation_runner.run(dataset, config)
            return summary.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - API exception boundary
            raise internal_server_error(exc)

    return router
