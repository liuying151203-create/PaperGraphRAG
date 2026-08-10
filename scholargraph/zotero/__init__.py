"""Zotero Local API integration for ScholarGraph."""

from scholargraph.zotero.client import (
    ZoteroInstanceChangedError,
    ZoteroLocalAPIError,
    ZoteroLocalClient,
    item_is_deleted,
    parse_attachment,
    parse_paper,
)
from scholargraph.zotero.gateway import LightRAGZoteroGateway, ZoteroRAGGateway
from scholargraph.zotero.mapping import ZoteroMappingStore
from scholargraph.zotero.models import (
    IndexStatus,
    SyncAction,
    SyncEvent,
    SyncReport,
    ZoteroAttachment,
    ZoteroChanges,
    ZoteroMapping,
    ZoteroPaper,
    ZoteroServerInfo,
    ZoteroSyncState,
)
from scholargraph.zotero.runtime import ScholarGraphZoteroRuntime, sync_report_dict
from scholargraph.zotero.sync import ZoteroReadClient, ZoteroSyncService

__all__ = [
    "IndexStatus",
    "LightRAGZoteroGateway",
    "ScholarGraphZoteroRuntime",
    "SyncAction",
    "SyncEvent",
    "SyncReport",
    "ZoteroAttachment",
    "ZoteroChanges",
    "ZoteroInstanceChangedError",
    "ZoteroLocalAPIError",
    "ZoteroLocalClient",
    "ZoteroMapping",
    "ZoteroMappingStore",
    "ZoteroPaper",
    "ZoteroRAGGateway",
    "ZoteroReadClient",
    "ZoteroServerInfo",
    "ZoteroSyncService",
    "ZoteroSyncState",
    "item_is_deleted",
    "parse_attachment",
    "parse_paper",
    "sync_report_dict",
]
