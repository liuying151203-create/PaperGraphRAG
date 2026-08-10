from lightrag.utils import convert_to_user_format


def test_query_formatter_preserves_optional_chunk_provenance() -> None:
    raw = convert_to_user_format(
        [],
        [],
        [
            {
                "reference_id": "1",
                "content": "Evidence",
                "file_path": "paper.pdf",
                "chunk_id": "chunk-1",
                "document_metadata": {"title": "Paper"},
                "content_headings": ["Methods"],
                "page": 3,
                "distance": 0.91,
            }
        ],
        [{"reference_id": "1", "file_path": "paper.pdf"}],
        "naive",
    )

    chunk = raw["data"]["chunks"][0]
    assert chunk["document_metadata"] == {"title": "Paper"}
    assert chunk["content_headings"] == ["Methods"]
    assert chunk["page"] == 3
    assert chunk["distance"] == 0.91
