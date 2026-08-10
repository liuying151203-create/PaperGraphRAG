from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from scholargraph.zotero.client import (
    ZoteroLocalAPIError,
    ZoteroLocalClient,
    parse_attachment,
    parse_paper,
)


def _paper_raw() -> dict[str, object]:
    return {
        "key": "PAPERABC",
        "version": 12,
        "data": {
            "key": "PAPERABC",
            "version": 12,
            "itemType": "journalArticle",
            "title": "Graph Retrieval for Papers",
            "creators": [
                {
                    "creatorType": "author",
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                },
                {"creatorType": "editor", "name": "Ignored Editor"},
            ],
            "date": "2025-03-14",
            "DOI": "10.1000/Graph.1",
            "collections": ["COLLECT1"],
            "tags": [{"tag": "GraphRAG"}, {"tag": "retrieval"}],
        },
    }


def _attachment_raw() -> dict[str, object]:
    return {
        "key": "ATTACHAB",
        "version": 13,
        "data": {
            "key": "ATTACHAB",
            "version": 13,
            "itemType": "attachment",
            "parentItem": "PAPERABC",
            "title": "Full Text PDF",
            "contentType": "application/pdf",
            "linkMode": "imported_file",
            "filename": "paper.pdf",
            "md5": "abc123",
        },
    }


@pytest.mark.asyncio
async def test_client_uses_local_v3_incremental_and_file_endpoints(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []
    pdf = b"%PDF-1.7\nmock scientific paper"

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        headers = {
            "Zotero-API-Version": "3",
            "Zotero-Server-ID": "desktop-one",
            "Last-Modified-Version": "13",
        }
        path = request.url.path
        if path == "/api/":
            return httpx.Response(200, headers=headers, json={})
        if path == "/api/users/0/items":
            return httpx.Response(
                200, headers=headers, json=[_paper_raw(), _attachment_raw()]
            )
        if path == "/api/users/0/deleted":
            return httpx.Response(200, headers=headers, json={"items": ["OLDKEY12"]})
        if path == "/api/users/0/items/PAPERABC/children":
            return httpx.Response(200, headers=headers, json=[_attachment_raw()])
        if path == "/api/users/0/items/ATTACHAB/file":
            return httpx.Response(
                200, headers={"Content-Type": "application/pdf"}, content=pdf
            )
        return httpx.Response(404)

    client = ZoteroLocalClient(transport=httpx.MockTransport(handler))
    try:
        info = await client.probe()
        changes = await client.fetch_changes(10)
        children = await client.get_children("PAPERABC")
        destination = tmp_path / "ATTACHAB.pdf"
        digest = await client.download_attachment("ATTACHAB", destination)
    finally:
        await client.aclose()

    assert info.api_version == 3
    assert info.server_id == "desktop-one"
    assert changes.library_version == 13
    assert changes.deleted_item_keys == ("OLDKEY12",)
    assert len(changes.items) == 2
    assert children == (_attachment_raw(),)
    assert destination.read_bytes() == pdf
    assert digest == hashlib.sha256(pdf).hexdigest()
    assert ("GET", "/api/users/0/items/ATTACHAB/file") in calls


def test_parse_paper_and_pdf_attachment_metadata() -> None:
    paper = parse_paper(_paper_raw())
    attachment = parse_attachment(_attachment_raw())

    assert paper is not None
    assert paper.title == "Graph Retrieval for Papers"
    assert paper.authors == ("Ada Lovelace",)
    assert paper.year == 2025
    assert paper.doi == "10.1000/Graph.1"
    assert paper.collections == ("COLLECT1",)
    assert paper.tags == ("GraphRAG", "retrieval")
    assert attachment is not None
    assert attachment.is_pdf
    assert attachment.parent_item_key == paper.key


@pytest.mark.asyncio
async def test_client_reports_disabled_local_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    client = ZoteroLocalClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ZoteroLocalAPIError, match="disabled"):
            await client.probe()
    finally:
        await client.aclose()


def test_client_rejects_non_loopback_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        ZoteroLocalClient("https://api.zotero.org/")

