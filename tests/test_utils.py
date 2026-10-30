import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from tests.conftest import MockResponse
from rnacentral_sequence_search.utils import (
    build_ebi_query,
    format_results,
    fetch_json_with_retry,
    resolve_taxid,
    resolve_gene_coordinates,
)

def test_build_ebi_query():
    # Basic query
    assert build_ebi_query("HOTAIR") == "(HOTAIR)"
    
    # Query with all filters
    q = build_ebi_query(
        query="HOTAIR",
        rna_type="lncRNA",
        taxon_id=9606,
        expert_db="GENCODE",
        has_secondary_structure=True,
        min_length=100,
        max_length=500
    )
    assert '(HOTAIR)' in q
    assert 'rna_type:"lncRNA"' in q
    assert '9606' in q
    assert 'expert_db:"GENCODE"' in q
    assert 'has_secondary_structure:true' in q
    assert 'length:[100 TO 500]' in q

    # Only min_length
    q_min = build_ebi_query("test", min_length=50)
    assert "length:[50 TO *]" in q_min

    # Only max_length
    q_max = build_ebi_query("test", max_length=200)
    assert "length:[* TO 200]" in q_max

    # has_secondary_structure=False
    q_no_2d = build_ebi_query("test", has_secondary_structure=False)
    assert "has_secondary_structure:false" in q_no_2d


def test_format_results_empty():
    res = format_results({"entries": []}, "job-123", "ACGU")
    assert res == "No matches found for the provided sequence."


def test_format_results_with_hits():
    data = {
        "hit_count": 1,
        "entries": [
            {
                "rnacentral_id": "URS0000000001",
                "description": "Homo sapiens miRNA",
                "score": 100.5,
                "e_value": "1e-20",
                "identity": 98.5,
                "query_coverage": 100.0,
            }
        ]
    }
    output = format_results(data, "job-456", "ACGU")
    assert "# RNAcentral Search Results" in output
    assert "Found **1** potential matches" in output
    assert "[URS0000000001](https://rnacentral.org/rna/URS0000000001)" in output
    assert "Homo sapiens miRNA" in output
    assert "Score**: 100.5" in output
    assert "E-value**: 1e-20" in output
    assert "Identity**: 98.5%" in output
    assert "jobid=job-456" in output


@pytest.mark.asyncio
async def test_fetch_json_with_retry_success():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=200, json_data={"key": "val"})

    status, data, err = await fetch_json_with_retry(session, "http://fake.url")
    assert status == 200
    assert data == {"key": "val"}
    assert err is None


@pytest.mark.asyncio
async def test_fetch_json_with_retry_404():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=404)

    status, data, err = await fetch_json_with_retry(session, "http://fake.url")
    assert status == 404
    assert data is None
    assert err == "HTTP 404"
    # Should not retry for 4xx
    assert session.get.call_count == 1


@pytest.mark.asyncio
async def test_fetch_json_with_retry_500_retried():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=500)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        status, data, err = await fetch_json_with_retry(session, "http://fake.url")
        assert status == 0
        assert data is None
        assert err == "HTTP 500"
        assert session.get.call_count == 3


@pytest.mark.asyncio
async def test_fetch_json_with_retry_network_error():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.side_effect = aiohttp.ClientError("Connection refused")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        status, data, err = await fetch_json_with_retry(session, "http://fake.url")
        assert status == 0
        assert data is None
        assert "Connection refused" in err
        assert session.get.call_count == 3


@pytest.mark.asyncio
async def test_resolve_taxid_direct_numeric():
    session = MagicMock(spec=aiohttp.ClientSession)
    assert await resolve_taxid(session, "9606") == 9606
    assert await resolve_taxid(session, 10090) == 10090
    assert await resolve_taxid(session, None) is None
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_taxid_by_name():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=200, json_data=[{"taxId": "9606"}])

    taxid = await resolve_taxid(session, "Homo sapiens")
    assert taxid == 9606


@pytest.mark.asyncio
async def test_resolve_taxid_not_found():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=404, json_data=None)

    taxid = await resolve_taxid(session, "NonexistentOrganism")
    assert taxid is None


@pytest.mark.asyncio
async def test_resolve_gene_coordinates_success():
    session = MagicMock(spec=aiohttp.ClientSession)

    def mock_get(url, **kwargs):
        if "taxonomy/rest/tax-id/9606" in url:
            return MockResponse(status=200, json_data={"scientificName": "Homo sapiens"})
        elif "/lookup/symbol/homo_sapiens/SMAD4" in url:
            return MockResponse(status=200, json_data={
                "seq_region_name": "18",
                "start": 51028528,
                "end": 51085045
            })
        return MockResponse(status=404)

    session.get.side_effect = mock_get

    coords, sci_name, err = await resolve_gene_coordinates(session, 9606, "SMAD4")
    assert err is None
    assert sci_name == "Homo sapiens"
    assert coords == ("18", 51028528, 51085045)


@pytest.mark.asyncio
async def test_resolve_gene_coordinates_no_gene_symbol():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=200, json_data={"scientificName": "Homo sapiens"})

    coords, sci_name, err = await resolve_gene_coordinates(session, 9606, None)
    assert err is None
    assert sci_name == "Homo sapiens"
    assert coords is None


@pytest.mark.asyncio
async def test_resolve_gene_coordinates_taxid_failed():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value = MockResponse(status=404)

    coords, sci_name, err = await resolve_gene_coordinates(session, 999999, "BRCA1")
    assert coords is None
    assert sci_name is None
    assert "ENA taxonomy lookup failed" in err


@pytest.mark.asyncio
async def test_resolve_gene_coordinates_gene_not_found_404():
    session = MagicMock(spec=aiohttp.ClientSession)

    def mock_get(url, **kwargs):
        if "taxonomy/rest/tax-id/9606" in url:
            return MockResponse(status=200, json_data={"scientificName": "Homo sapiens"})
        return MockResponse(status=404)

    session.get.side_effect = mock_get

    coords, sci_name, err = await resolve_gene_coordinates(session, 9606, "NONEXISTENT")
    assert coords is None
    assert sci_name == "Homo sapiens"
    assert err == "Gene NONEXISTENT not found in species homo_sapiens."


@pytest.mark.asyncio
async def test_resolve_gene_coordinates_missing_coords():
    session = MagicMock(spec=aiohttp.ClientSession)

    def mock_get(url, **kwargs):
        if "taxonomy/rest/tax-id/9606" in url:
            return MockResponse(status=200, json_data={"scientificName": "Homo sapiens"})
        return MockResponse(status=200, json_data={"id": "ENSG123"})

    session.get.side_effect = mock_get

    coords, sci_name, err = await resolve_gene_coordinates(session, 9606, "NOCOORDS")
    assert coords is None
    assert sci_name == "Homo sapiens"
    assert err == "Gene found but missing coordinate information."
