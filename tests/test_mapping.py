import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import MockResponse
from rnacentral_sequence_search.mapping import fetch_rna_mapping

@pytest.mark.asyncio
async def test_fetch_rna_mapping_happy_path_urs_and_taxon():
    urs = "URS0000759B6D"
    taxon = "9606"
    xrefs_data = {
        "results": [
            {
                "database": "miRBase",
                "accession": {
                    "id": "MIMAT0000062",
                    "optional_id": "hsa-miR-126-3p",
                    "external_id": "MI0000109"
                }
            },
            {
                "database": "Ensembl",
                "accession": {
                    "id": "ENST00000385272",
                    "external_id": "ENSG00000207562"
                }
            }
        ],
        "next": None
    }

    async def mock_fetch_json(session, url):
        if f"/rna/{urs}/xrefs/9606/" in url:
            return 200, xrefs_data, None
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(urs, taxon)

    # Assertions on data structure / markdown format
    assert f"# ID Mapping for {urs}" in result
    assert "**Primary ID**: `URS0000759B6D_9606`" in result
    assert "**NCBI Taxon ID**: `9606`" in result
    assert "**Canonical ID**: `miRBase: hsa-miR-126-3p`" in result
    assert "**Secondary Identifiers**:" in result
    assert "- Ensembl: ENSG00000207562" in result
    assert "- Ensembl: ENST00000385272" in result


@pytest.mark.asyncio
async def test_fetch_rna_mapping_happy_path_external_id_resolves():
    ext_id = "MIMAT0000062"
    urs = "URS0000759B6D"

    external_lookup_data = {
        "results": [{"rnacentral_id": urs}]
    }
    xrefs_summary = {
        "results": [{"taxid": 9606}]
    }
    xrefs_data = {
        "results": [
            {
                "database": "miRBase",
                "accession": {
                    "id": "MIMAT0000062",
                    "optional_id": "hsa-miR-126-3p"
                }
            }
        ],
        "next": None
    }

    async def mock_fetch_json(session, url):
        if "external_id=" in url:
            return 200, external_lookup_data, None
        elif f"/rna/{urs}/xrefs" in url and "9606" not in url:
            return 200, xrefs_summary, None
        elif f"/rna/{urs}/xrefs/9606/" in url:
            return 200, xrefs_data, None
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(ext_id)

    assert f"# ID Mapping for {ext_id}" in result
    assert "**Primary ID**: `URS0000759B6D_9606`" in result
    assert "**Canonical ID**: `miRBase: hsa-miR-126-3p`" in result


@pytest.mark.asyncio
async def test_fetch_rna_mapping_external_id_not_found():
    ext_id = "UNKNOWN_ID"
    lookup_data = {"results": []}

    async def mock_fetch_json(session, url):
        return 200, lookup_data, None

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(ext_id)

    assert result == f"No RNAcentral entry found for external ID: {ext_id}"


@pytest.mark.asyncio
async def test_fetch_rna_mapping_external_id_error():
    ext_id = "FAULTY_ID"

    async def mock_fetch_json(session, url):
        return 500, None, "HTTP 500"

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(ext_id)

    assert f"Error looking up external ID {ext_id}: HTTP 500" in result


@pytest.mark.asyncio
async def test_fetch_rna_mapping_cannot_determine_taxid():
    urs = "URS0000000000"

    async def mock_fetch_json(session, url):
        # xrefs call returns empty list
        return 200, {"results": []}, None

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(urs, taxon=None)

    assert result == f"Could not determine a valid Taxon ID for {urs}"


@pytest.mark.asyncio
async def test_fetch_rna_mapping_no_xrefs_for_taxon():
    urs = "URS0000759B6D"

    async def mock_fetch_json(session, url):
        return 200, {"results": []}, None

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(urs, taxon="9606")

    assert result == f"No cross-references found for {urs} in taxon 9606"


@pytest.mark.asyncio
async def test_fetch_rna_mapping_error_fetching_xrefs():
    urs = "URS0000759B6D"

    async def mock_fetch_json(session, url):
        return 500, None, "Connection reset"

    with patch("rnacentral_sequence_search.mapping.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_rna_mapping(urs, taxon="9606")

    assert f"Error fetching cross-references for {urs} (taxon 9606): Connection reset" in result
