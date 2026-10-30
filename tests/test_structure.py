import base64
import pytest
from unittest.mock import patch
from tests.conftest import MockResponse
from rnacentral_sequence_search.structure import fetch_secondary_structure_svg
from mcp.types import CallToolResult, TextContent, ImageContent

@pytest.mark.asyncio
async def test_fetch_secondary_structure_svg_happy_path():
    urs_id = "URS0000049E57_9606"
    svg_content = '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>'

    def mock_get(url, **kwargs):
        assert "URS0000049E57" in url
        return MockResponse(status=200, text_data=svg_content)

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_secondary_structure_svg(urs_id)

    assert isinstance(result, CallToolResult)
    assert not result.isError
    assert len(result.content) == 2

    text_part = result.content[0]
    image_part = result.content[1]

    assert isinstance(text_part, TextContent)
    assert f"Secondary structure diagram for {urs_id}:" in text_part.text
    assert svg_content in text_part.text

    assert isinstance(image_part, ImageContent)
    assert image_part.mimeType == "image/svg+xml"
    expected_b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
    assert image_part.data == expected_b64


@pytest.mark.asyncio
async def test_fetch_secondary_structure_svg_404_error():
    urs_id = "URS0000000000"

    def mock_get(url, **kwargs):
        return MockResponse(status=404)

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_secondary_structure_svg(urs_id)

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    assert f"Error: Could not find secondary structure for {urs_id}. (Status 404)" in result.content[0].text


@pytest.mark.asyncio
async def test_fetch_secondary_structure_svg_no_diagram_available():
    # Service returns 200 but content has no <svg tag
    urs_id = "URS0000049E57"

    def mock_get(url, **kwargs):
        return MockResponse(status=200, text_data="No data found")

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await fetch_secondary_structure_svg(urs_id)

    assert isinstance(result, CallToolResult)
    # Not flagged as error since it's just absent data
    assert result.isError is False
    assert len(result.content) == 1
    assert result.content[0].text == f"No secondary structure diagram available for {urs_id}."


@pytest.mark.asyncio
async def test_fetch_secondary_structure_svg_exception():
    urs_id = "URS0000049E57"

    with patch("aiohttp.ClientSession.get", side_effect=Exception("Connection reset by peer")):
        result = await fetch_secondary_structure_svg(urs_id)

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    assert "An error occurred while fetching the structure: Connection reset by peer" in result.content[0].text
