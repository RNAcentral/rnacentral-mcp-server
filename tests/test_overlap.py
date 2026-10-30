import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import MockResponse
from rnacentral_sequence_search.overlap import fetch_overlapping_ncrnas
from rnacentral_sequence_search.server import get_overlapping_ncrnas

@pytest.mark.asyncio
async def test_get_overlapping_ncrnas_validation_error():
    # Neither gene_symbol nor complete chromosome coords provided
    res1 = await get_overlapping_ncrnas(species="human")
    assert "Error: You must provide EITHER gene_symbol OR (chromosome, start, and end)." in res1

    res2 = await get_overlapping_ncrnas(species="human", chromosome="1", start=100)  # missing end
    assert "Error: You must provide EITHER gene_symbol OR (chromosome, start, and end)." in res2


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_species_not_found():
    async def mock_fetch_json(session, url):
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.utils.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_overlapping_ncrnas(species="unknown_alien", chromosome="1", start=100, end=200)

    assert result == "Error: Could not resolve species 'unknown_alien' to a Taxon ID."


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_gene_symbol_error():
    async def mock_resolve_taxid(session, species):
        return 9606

    async def mock_resolve_coords(session, taxid, gene_symbol):
        return None, "Homo sapiens", "Gene NOTFOUND not found in species homo_sapiens."

    with patch("rnacentral_sequence_search.overlap.resolve_taxid", side_effect=mock_resolve_taxid), \
         patch("rnacentral_sequence_search.overlap.resolve_gene_coordinates", side_effect=mock_resolve_coords):
        result = await fetch_overlapping_ncrnas(species="human", gene_symbol="NOTFOUND")

    assert result == "Coordinate Resolution Error: Gene NOTFOUND not found in species homo_sapiens."


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_happy_path_by_gene():
    async def mock_resolve_taxid(session, species):
        return 9606

    async def mock_resolve_coords(session, taxid, gene_symbol):
        return ("18", 51028528, 51085045), "Homo sapiens", None

    overlap_data = {
        "results": [
            {
                "feature_type": "transcript",
                "rnacentral_id": "URS000080E2F4@18/51028528-51030000",
                "description": "Homo sapiens lncRNA overlapping SMAD4",
                "rna_type": "lncRNA",
                "start": 51028528,
                "end": 51030000
            }
        ],
        "next": None
    }

    async def mock_fetch_json(session, url):
        if "overlap/region/homo_sapiens/18:51028528-51085045" in url:
            return 200, overlap_data, None
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.overlap.resolve_taxid", side_effect=mock_resolve_taxid), \
         patch("rnacentral_sequence_search.overlap.resolve_gene_coordinates", side_effect=mock_resolve_coords), \
         patch("rnacentral_sequence_search.overlap.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_overlapping_ncrnas(species="human", gene_symbol="SMAD4")

    assert "# Overlapping ncRNAs in Homo sapiens" in result
    assert "**Region**: `18:51028528-51085045`" in result
    assert "**Gene Symbol**: `SMAD4`" in result
    assert "Found **1** overlapping ncRNAs." in result
    assert "[URS000080E2F4](https://rnacentral.org/rna/URS000080E2F4)" in result
    assert "Description**: Homo sapiens lncRNA overlapping SMAD4" in result
    assert "Type**: lncRNA" in result


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_happy_path_by_coordinates():
    async def mock_resolve_taxid(session, species):
        return 9606

    async def mock_resolve_coords(session, taxid, gene_symbol):
        return None, "Homo sapiens", None

    overlap_data = [
        {
            "feature_type": "transcript",
            "ID": "URS0000123456",
            "description": "Homo sapiens miRNA",
            "biotype": "miRNA",
            "start": 1000,
            "end": 2000
        }
    ]

    async def mock_fetch_json(session, url):
        return 200, overlap_data, None

    with patch("rnacentral_sequence_search.overlap.resolve_taxid", side_effect=mock_resolve_taxid), \
         patch("rnacentral_sequence_search.overlap.resolve_gene_coordinates", side_effect=mock_resolve_coords), \
         patch("rnacentral_sequence_search.overlap.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_overlapping_ncrnas(species="human", chromosome="chr1", start=1000, end=2000)

    assert "# Overlapping ncRNAs in Homo sapiens" in result
    assert "**Region**: `1:1000-2000`" in result
    assert "[URS0000123456](https://rnacentral.org/rna/URS0000123456)" in result


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_no_results():
    async def mock_resolve_taxid(session, species):
        return 9606

    async def mock_resolve_coords(session, taxid, gene_symbol):
        return None, "Homo sapiens", None

    async def mock_fetch_json(session, url):
        # 404 or empty results
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.overlap.resolve_taxid", side_effect=mock_resolve_taxid), \
         patch("rnacentral_sequence_search.overlap.resolve_gene_coordinates", side_effect=mock_resolve_coords), \
         patch("rnacentral_sequence_search.overlap.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_overlapping_ncrnas(species="human", chromosome="1", start=1, end=100)

    assert result == "No overlapping RNAs found for homo_sapiens (Homo sapiens) at 1:1-100."


@pytest.mark.asyncio
async def test_fetch_overlapping_ncrnas_api_error():
    async def mock_resolve_taxid(session, species):
        return 9606

    async def mock_resolve_coords(session, taxid, gene_symbol):
        return None, "Homo sapiens", None

    async def mock_fetch_json(session, url):
        return 500, None, "Server error"

    with patch("rnacentral_sequence_search.overlap.resolve_taxid", side_effect=mock_resolve_taxid), \
         patch("rnacentral_sequence_search.overlap.resolve_gene_coordinates", side_effect=mock_resolve_coords), \
         patch("rnacentral_sequence_search.overlap.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_overlapping_ncrnas(species="human", chromosome="1", start=1, end=100)

    assert "Error querying RNAcentral overlap API: Server error" in result
