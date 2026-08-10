import pytest

from lightrag.operate import _apply_extraction_result_normalizer


@pytest.mark.offline
@pytest.mark.asyncio
async def test_extraction_result_normalizer_supports_sync_callable():
    nodes = {"A": [{"entity_type": "method"}]}
    edges = {}
    seen_chunk = None

    def normalizer(input_nodes, input_edges, chunk_data):
        nonlocal seen_chunk
        seen_chunk = chunk_data
        return {**input_nodes, "B": []}, input_edges

    result_nodes, result_edges = await _apply_extraction_result_normalizer(
        nodes,
        edges,
        {"addon_params": {"extraction_result_normalizer": normalizer}},
        {"content": "paper text"},
    )

    assert set(result_nodes) == {"A", "B"}
    assert result_edges == {}
    assert seen_chunk == {"content": "paper text"}


@pytest.mark.offline
@pytest.mark.asyncio
async def test_extraction_result_normalizer_supports_async_callable():
    async def normalizer(nodes, edges, chunk_data):
        return nodes, {("A", "B"): []}

    _, result_edges = await _apply_extraction_result_normalizer(
        {},
        {},
        {"addon_params": {"extraction_result_normalizer": normalizer}},
    )

    assert ("A", "B") in result_edges


@pytest.mark.offline
@pytest.mark.asyncio
async def test_extraction_result_normalizer_rejects_invalid_contract():
    with pytest.raises(TypeError, match="tuple of two dicts"):
        await _apply_extraction_result_normalizer(
            {},
            {},
            {"addon_params": {"extraction_result_normalizer": lambda *_: {}}},
        )
