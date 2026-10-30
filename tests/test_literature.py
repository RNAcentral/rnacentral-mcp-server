import pytest
from unittest.mock import patch
from tests.conftest import MockResponse
from rnacentral_sequence_search.literature import fetch_rna_description

@pytest.mark.asyncio
async def test_fetch_rna_description_happy_path():
    summary_text = "mmu-mir-191 is a microRNA involved in cellular regulation."

    def mock_get(url, **kwargs):
        assert "litsumm/mmu-mir-191" in url
        return MockResponse(status=200, json_data={"summary": summary_text})

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_rna_description("mmu-mir-191")

    assert result == summary_text


@pytest.mark.asyncio
async def test_fetch_rna_description_no_summary_field():
    def mock_get(url, **kwargs):
        return MockResponse(status=200, json_data={})

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_rna_description("mmu-mir-191")

    assert result == "No description available"


@pytest.mark.asyncio
async def test_fetch_rna_description_http_error():
    def mock_get(url, **kwargs):
        return MockResponse(status=404)

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_rna_description("unknown_id")

    assert "Error querying RNAcentral API:" in result
    assert "404" in result


@pytest.mark.asyncio
async def test_fetch_rna_description_network_exception():
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Connection timed out")):
        result = await fetch_rna_description("mmu-mir-191")

    assert result == "Error querying RNAcentral API: Connection timed out"
