from __future__ import annotations

import pytest
from pydantic import ValidationError

from scholargraph.ingestion import PaperMetadata


def test_paper_metadata_normalizes_citation_fields() -> None:
    metadata = PaperMetadata(
        paper_id=" paper-1 ",
        title=" A Graph Paper ",
        authors=["Alice", " Alice ", "Bob"],
        year=2025,
        doi="https://doi.org/10.1000/ABC",
        source_path=" /library/paper.pdf ",
        zotero_item_key=" ITEM1 ",
        collection_keys=["COLL1", " COLL1 ", "COLL2"],
        tags=["graph", " graph "],
    )

    assert metadata.paper_id == "paper-1"
    assert metadata.title == "A Graph Paper"
    assert metadata.authors == ["Alice", "Bob"]
    assert metadata.doi == "10.1000/abc"
    assert metadata.source_path == "/library/paper.pdf"
    assert metadata.to_document_metadata()["zotero_item_key"] == "ITEM1"
    assert metadata.collection_keys == ["COLL1", "COLL2"]
    assert metadata.tags == ["graph"]


def test_paper_metadata_rejects_unknown_or_invalid_fields() -> None:
    with pytest.raises(ValidationError):
        PaperMetadata(
            paper_id="paper-1",
            title="Title",
            authors="Alice",
            source_path="paper.pdf",
            invented=True,
        )
