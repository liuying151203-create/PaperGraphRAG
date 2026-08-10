"""Read-only client for Zotero's localhost Web API implementation."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlparse

import httpx

from scholargraph.zotero.models import (
    ZoteroAttachment,
    ZoteroChanges,
    ZoteroPaper,
    ZoteroServerInfo,
)

_YEAR_RE = re.compile(r"(?<!\d)(1\d{3}|2\d{3})(?!\d)")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ZoteroLocalAPIError(RuntimeError):
    """Raised when the local Zotero API cannot satisfy a read request."""


class ZoteroInstanceChangedError(ZoteroLocalAPIError):
    """Raised when persisted versions belong to another Zotero instance."""


class ZoteroLocalClient:
    """Small API-v3 client restricted to a loopback Zotero endpoint."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:23119/api/",
        *,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("Zotero Local API must use an HTTP loopback address")
        normalized = base_url.rstrip("/") + "/"
        self._client = httpx.AsyncClient(
            base_url=normalized,
            headers={"Zotero-API-Version": "3", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def probe(self) -> ZoteroServerInfo:
        """Check Local API availability and return instance identity."""
        response = await self._request("GET", "")
        raw_version = response.headers.get("Zotero-API-Version", "3")
        try:
            api_version = int(raw_version)
        except ValueError as exc:
            raise ZoteroLocalAPIError(
                f"Invalid Zotero-API-Version header: {raw_version!r}"
            ) from exc
        if api_version != 3:
            raise ZoteroLocalAPIError(
                f"Unsupported Zotero Local API version: {api_version}"
            )
        return ZoteroServerInfo(
            api_version=api_version,
            server_id=response.headers.get("Zotero-Server-ID"),
        )

    async def fetch_changes(self, since: int, *, retries: int = 3) -> ZoteroChanges:
        """Read changed and deleted items from one consistent version window."""
        if since < 0:
            raise ValueError("since must be non-negative")
        for attempt in range(retries):
            items_response = await self._request(
                "GET",
                "users/0/items",
                params={"since": since, "includeTrashed": 1},
            )
            items = items_response.json()
            if not isinstance(items, list):
                raise ZoteroLocalAPIError("Zotero items response must be a JSON array")
            items_version = self._response_version(items_response)

            deleted_response = await self._request(
                "GET", "users/0/deleted", params={"since": since}
            )
            deleted = deleted_response.json()
            if not isinstance(deleted, dict):
                raise ZoteroLocalAPIError("Zotero deleted response must be an object")
            deleted_version = self._response_version(deleted_response)
            if items_version == deleted_version:
                raw_deleted_items = deleted.get("items", [])
                if not isinstance(raw_deleted_items, list):
                    raise ZoteroLocalAPIError("Zotero deleted.items must be an array")
                return ZoteroChanges(
                    library_version=items_version,
                    items=tuple(item for item in items if isinstance(item, dict)),
                    deleted_item_keys=tuple(str(key) for key in raw_deleted_items),
                )
            if attempt + 1 == retries:
                break
        raise ZoteroLocalAPIError(
            "Zotero library changed while reading an incremental sync window"
        )

    async def get_items(self, keys: set[str]) -> dict[str, dict[str, object]]:
        """Fetch item JSON in API-supported batches of at most 50 keys."""
        result: dict[str, dict[str, object]] = {}
        ordered = sorted(keys)
        for offset in range(0, len(ordered), 50):
            batch = ordered[offset : offset + 50]
            response = await self._request(
                "GET",
                "users/0/items",
                params={"itemKey": ",".join(batch), "includeTrashed": 1},
            )
            payload = response.json()
            if not isinstance(payload, list):
                raise ZoteroLocalAPIError("Zotero item batch must be a JSON array")
            for raw in payload:
                if isinstance(raw, dict) and isinstance(raw.get("key"), str):
                    result[str(raw["key"])] = raw
        return result

    async def get_children(self, item_key: str) -> tuple[dict[str, object], ...]:
        response = await self._request(
            "GET", f"users/0/items/{item_key}/children", params={"includeTrashed": 1}
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise ZoteroLocalAPIError("Zotero children response must be a JSON array")
        return tuple(item for item in payload if isinstance(item, dict))

    async def download_attachment(self, attachment_key: str, destination: Path) -> str:
        """Download a PDF into ScholarGraph-managed storage and return SHA-256."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        prefix = bytearray()
        try:
            async with self._client.stream(
                "GET", f"users/0/items/{attachment_key}/file"
            ) as response:
                self._raise_for_status(response)
                with temporary.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        if len(prefix) < 1024:
                            prefix.extend(chunk[: 1024 - len(prefix)])
                        digest.update(chunk)
                        handle.write(chunk)
            if b"%PDF-" not in prefix:
                raise ZoteroLocalAPIError(
                    f"Attachment {attachment_key} did not return PDF content"
                )
            os.replace(temporary, destination)
            return digest.hexdigest()
        finally:
            temporary.unlink(missing_ok=True)

    async def _request(
        self, method: str, path: str, *, params: dict[str, object] | None = None
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, path, params=params)
        except httpx.HTTPError as exc:
            raise ZoteroLocalAPIError(f"Cannot reach Zotero Local API: {exc}") from exc
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 403:
            raise ZoteroLocalAPIError(
                "Zotero Local API is disabled; enable local application communication"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ZoteroLocalAPIError(
                f"Zotero Local API returned HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _response_version(response: httpx.Response) -> int:
        raw = response.headers.get("Last-Modified-Version")
        if raw is None:
            raise ZoteroLocalAPIError("Missing Last-Modified-Version header")
        try:
            return int(raw)
        except ValueError as exc:
            raise ZoteroLocalAPIError(
                f"Invalid Last-Modified-Version header: {raw!r}"
            ) from exc


def parse_paper(raw: dict[str, object]) -> ZoteroPaper | None:
    """Normalize one regular Zotero item into the ScholarGraph paper model."""
    data = raw.get("data")
    if not isinstance(data, dict) or data.get("itemType") in {"attachment", "note"}:
        return None
    key = raw.get("key") or data.get("key")
    title = data.get("title")
    if not isinstance(key, str) or not isinstance(title, str) or not title.strip():
        return None

    creators = data.get("creators", [])
    authors: list[str] = []
    if isinstance(creators, list):
        author_creators = [
            creator
            for creator in creators
            if isinstance(creator, dict) and creator.get("creatorType") == "author"
        ]
        selected = author_creators or [
            creator for creator in creators if isinstance(creator, dict)
        ]
        for creator in selected:
            name = _creator_name(creator)
            if name and name not in authors:
                authors.append(name)

    date = data.get("date")
    year_match = _YEAR_RE.search(str(date)) if date else None
    doi = data.get("DOI")
    collections = data.get("collections", [])
    tags = data.get("tags", [])
    return ZoteroPaper(
        key=key,
        version=_object_version(raw, data),
        title=title.strip(),
        authors=tuple(authors),
        year=int(year_match.group(1)) if year_match else None,
        doi=doi.strip() if isinstance(doi, str) and doi.strip() else None,
        collections=tuple(str(value) for value in collections)
        if isinstance(collections, list)
        else (),
        tags=tuple(
            str(tag["tag"])
            for tag in tags
            if isinstance(tag, dict) and isinstance(tag.get("tag"), str)
        )
        if isinstance(tags, list)
        else (),
    )


def parse_attachment(raw: dict[str, object]) -> ZoteroAttachment | None:
    """Normalize one child attachment returned by the Zotero API."""
    data = raw.get("data")
    if not isinstance(data, dict) or data.get("itemType") != "attachment":
        return None
    key = raw.get("key") or data.get("key")
    parent = data.get("parentItem")
    if not isinstance(key, str) or not isinstance(parent, str):
        return None
    return ZoteroAttachment(
        key=key,
        version=_object_version(raw, data),
        parent_item_key=parent,
        title=str(data.get("title") or "").strip(),
        content_type=str(data.get("contentType") or "").strip(),
        link_mode=str(data.get("linkMode") or "").strip(),
        filename=str(data.get("filename") or f"{key}.pdf").strip(),
        md5=str(data["md5"]) if data.get("md5") else None,
    )


def item_is_deleted(raw: dict[str, object]) -> bool:
    data = raw.get("data")
    return isinstance(data, dict) and bool(data.get("deleted"))


def _creator_name(creator: dict[str, Any]) -> str:
    literal = creator.get("name")
    if isinstance(literal, str) and literal.strip():
        return literal.strip()
    parts = [creator.get("firstName"), creator.get("lastName")]
    return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def _object_version(raw: dict[str, object], data: dict[str, object]) -> int:
    value = raw.get("version", data.get("version", 0))
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
