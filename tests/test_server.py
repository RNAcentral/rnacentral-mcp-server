import pytest
from unittest.mock import patch, AsyncMock
from rnacentral_sequence_search.server import (
    mcp,
    get_secondary_structure_svg,
    map_rna_id,
    query_rnacentral,
    export_sequences,
    get_overlapping_ncrnas,
    get_rna_description,
    search_sequence,
    get_sequence_search_results,
)

def test_server_tools_registered():
    """Verify that all expected MCP tools are registered on the FastMCP instance."""
    tool_names = set(mcp._tool_manager._tools.keys())
    expected_tools = {
        "get_secondary_structure_svg",
        "map_rna_id",
        "query_rnacentral",
        "export_sequences",
        "get_overlapping_ncrnas",
        "get_rna_description",
        "search_sequence",
        "get_sequence_search_results",
    }
    assert expected_tools.issubset(tool_names)


@pytest.mark.asyncio
async def test_get_overlapping_ncrnas_validation_in_server():
    """Verify input validation returns an informative string to the LLM when arguments are incomplete."""
    res_none = await get_overlapping_ncrnas(species="human")
    assert res_none == "Error: You must provide EITHER gene_symbol OR (chromosome, start, and end)."

    res_missing_end = await get_overlapping_ncrnas(species="human", chromosome="1", start=100)
    assert res_missing_end == "Error: You must provide EITHER gene_symbol OR (chromosome, start, and end)."


@pytest.mark.asyncio
async def test_server_tool_delegation():
    """Verify server functions delegate to their respective module implementations."""
    with patch("rnacentral_sequence_search.server.fetch_rna_mapping", new_callable=AsyncMock) as mock_mapping, \
         patch("rnacentral_sequence_search.server.perform_query_rnacentral", new_callable=AsyncMock) as mock_query, \
         patch("rnacentral_sequence_search.server.perform_export_sequences", new_callable=AsyncMock) as mock_export, \
         patch("rnacentral_sequence_search.server.fetch_overlapping_ncrnas", new_callable=AsyncMock) as mock_overlap, \
         patch("rnacentral_sequence_search.server.fetch_rna_description", new_callable=AsyncMock) as mock_lit, \
         patch("rnacentral_sequence_search.server.perform_search_sequence", new_callable=AsyncMock) as mock_seq_search, \
         patch("rnacentral_sequence_search.server.fetch_sequence_search_results", new_callable=AsyncMock) as mock_seq_results:

        mock_mapping.return_value = "mock_mapping_result"
        mock_query.return_value = "mock_query_result"
        mock_export.return_value = "mock_export_result"
        mock_overlap.return_value = "mock_overlap_result"
        mock_lit.return_value = "mock_lit_result"
        mock_seq_search.return_value = "mock_seq_search_result"
        mock_seq_results.return_value = "mock_seq_results_result"

        assert await map_rna_id("URS123") == "mock_mapping_result"
        assert await query_rnacentral("test") == "mock_query_result"
        assert await export_sequences("test") == "mock_export_result"
        assert await get_overlapping_ncrnas("human", gene_symbol="TP53") == "mock_overlap_result"
        assert await get_rna_description("id123") == "mock_lit_result"
        assert await search_sequence("ACGU") == "mock_seq_search_result"
        assert await get_sequence_search_results("job123") == "mock_seq_results_result"
