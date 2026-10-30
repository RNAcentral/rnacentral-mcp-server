import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tests.conftest import MockResponse
from rnacentral_sequence_search.search import (
    perform_query_rnacentral,
    perform_export_sequences,
    perform_search_sequence,
    fetch_sequence_search_results,
)

# -----------------------------------------------------------------------------
# Tests for perform_query_rnacentral
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_perform_query_rnacentral_happy_path():
    ebi_response_data = {
        "entries": [
            {
                "id": "URS0000759B6D_9606",
                "fields": {
                    "description": ["Homo sapiens microRNA-126"],
                    "rna_type": ["miRNA"],
                    "tax_string": ["Eukaryota; Metazoa; Chordata; Mammalia; Primates; Hominidae; Homo sapiens"],
                    "expert_db": ["miRBase", "Ensembl"],
                    "length": ["85"],
                    "has_secondary_structure": ["true"]
                }
            }
        ]
    }
    metadata_response_data = {
        "go_annotations": [
            {"ontology_term": {"name": "gene silencing by miRNA"}}
        ],
        "rfam_hits": [
            {"rfam_family_id": "RF00074"}
        ]
    }

    def mock_get(url, **kwargs):
        if "ebisearch" in url:
            return MockResponse(status=200, json_data=ebi_response_data)
        elif "/api/v1/rna/URS0000759B6D" in url:
            return MockResponse(status=200, json_data=metadata_response_data)
        return MockResponse(status=404)

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await perform_query_rnacentral(
            query="hsa-mir-126",
            rna_type="miRNA",
            taxon="9606",
            has_secondary_structure=True
        )

    assert "# RNAcentral Search Results: hsa-mir-126" in result
    assert "**Taxon Filter**: 9606 (NCBI:9606)" in result
    assert "[URS0000759B6D_9606](https://rnacentral.org/rna/URS0000759B6D)" in result
    assert "Description**: Homo sapiens microRNA-126" in result
    assert "Type**: miRNA" in result
    assert "Length**: 85 nt" in result
    assert "Databases**: miRBase, Ensembl" in result
    assert "GO Annotations**: gene silencing by miRNA" in result
    assert "Rfam Hits**: [RF00074](https://rfam.org/family/RF00074)" in result
    assert "**2D Structure**: Available" in result


@pytest.mark.asyncio
async def test_perform_query_rnacentral_no_results():
    ebi_response_data = {"entries": []}

    def mock_get(url, **kwargs):
        return MockResponse(status=200, json_data=ebi_response_data)

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await perform_query_rnacentral(query="nonexistent_seq_term")

    assert "No results found for query:" in result
    assert "(nonexistent_seq_term)" in result


@pytest.mark.asyncio
async def test_perform_query_rnacentral_ebi_error():
    def mock_get(url, **kwargs):
        return MockResponse(status=500, text_data="Internal Server Error")

    with patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await perform_query_rnacentral(query="fail_query")

    assert result == "Error querying EBI Search: 500 - Internal Server Error"


@pytest.mark.asyncio
async def test_perform_query_rnacentral_exception():
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Network down")):
        result = await perform_query_rnacentral(query="fail_query")

    assert result == "An error occurred while querying RNAcentral: Network down"


# -----------------------------------------------------------------------------
# Tests for perform_export_sequences
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_perform_export_sequences_invalid_format():
    result = await perform_export_sequences(query="HOTAIR", format="invalid_format")
    assert result == "Error: Unsupported format. Please choose 'fasta' or 'parquet'."


@pytest.mark.asyncio
async def test_perform_export_sequences_happy_path():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"task_id": "test-task-123"})

    def mock_get(url, **kwargs):
        return MockResponse(status=200, json_data={"status": "finished"})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await perform_export_sequences(query="HOTAIR", format="fasta")

    assert "# Bulk Sequence Export" in result
    assert "Job `test-task-123` completed." in result
    assert "[Download Results](https://export.rnacentral.org/download/test-task-123/fasta)" in result


@pytest.mark.asyncio
async def test_perform_export_sequences_submit_failure():
    def mock_post(url, **kwargs):
        return MockResponse(status=503, text_data="Service Unavailable")

    with patch("aiohttp.ClientSession.post", side_effect=mock_post):
        result = await perform_export_sequences(query="HOTAIR", format="fasta")

    assert "Error submitting export job: 503 - Service Unavailable" in result


@pytest.mark.asyncio
async def test_perform_export_sequences_no_task_id():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post):
        result = await perform_export_sequences(query="HOTAIR", format="fasta")

    assert result == "Error: No task_id returned from export service."


@pytest.mark.asyncio
async def test_perform_export_sequences_job_failed():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"task_id": "task-fail"})

    def mock_get(url, **kwargs):
        return MockResponse(status=200, json_data={"status": "failed", "error": "Query execution timeout"})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await perform_export_sequences(query="HOTAIR", format="fasta")

    assert result == "Export job failed: Query execution timeout"


@pytest.mark.asyncio
async def test_perform_export_sequences_still_processing():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"task_id": "task-slow"})

    def mock_get(url, **kwargs):
        return MockResponse(status=200, json_data={"status": "pending"})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post), \
         patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await perform_export_sequences(query="HOTAIR", format="parquet")

    assert "Export job `task-slow` is still processing: https://export.rnacentral.org/download/task-slow/parquet" in result


# -----------------------------------------------------------------------------
# Tests for perform_search_sequence
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_perform_search_sequence_happy_path():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={"job_id": "seq-job-999"})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post):
        result = await perform_search_sequence(sequence="UGAGGUAGUAGGUUGUAUAGUU")

    assert "Search job submitted. Job ID: `seq-job-999`" in result
    assert "Poll `get_sequence_search_results` with this job ID" in result


@pytest.mark.asyncio
async def test_perform_search_sequence_submission_error():
    def mock_post(url, **kwargs):
        return MockResponse(status=400, text_data="Invalid sequence")

    with patch("aiohttp.ClientSession.post", side_effect=mock_post):
        result = await perform_search_sequence(sequence="XYZ")

    assert result == "Error submitting search job: HTTP 400"


@pytest.mark.asyncio
async def test_perform_search_sequence_missing_job_id():
    def mock_post(url, **kwargs):
        return MockResponse(status=200, json_data={})

    with patch("aiohttp.ClientSession.post", side_effect=mock_post):
        result = await perform_search_sequence(sequence="UGAGGUAGUAGGUUGUAUAGUU")

    assert result == "Error: No job_id returned from search service."


@pytest.mark.asyncio
async def test_perform_search_sequence_exception():
    with patch("aiohttp.ClientSession.post", side_effect=Exception("Connection dropped")):
        result = await perform_search_sequence(sequence="UGAGGUAGUAGGUUGUAUAGUU")

    assert result == "An error occurred while searching: Connection dropped"


# -----------------------------------------------------------------------------
# Tests for fetch_sequence_search_results
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_sequence_search_results_happy_path():
    async def mock_fetch_json(session, url):
        if "job-status" in url:
            return 200, {"status": "finished"}, None
        elif "job-results" in url:
            return 200, {
                "hit_count": 1,
                "entries": [{
                    "rnacentral_id": "URS0000000001",
                    "description": "Test RNA",
                    "score": 95.0,
                    "e_value": "1e-15",
                    "identity": 100.0,
                    "query_coverage": 100.0
                }]
            }, None
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.search.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_sequence_search_results("job-123", sequence="ACGU")

    assert "# RNAcentral Search Results" in result
    assert "[URS0000000001](https://rnacentral.org/rna/URS0000000001)" in result


@pytest.mark.asyncio
async def test_fetch_sequence_search_results_status_error():
    async def mock_fetch_json(session, url):
        return 500, None, "HTTP 500"

    with patch("rnacentral_sequence_search.search.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_sequence_search_results("job-error")

    assert result == "Error checking job status: HTTP 500"


@pytest.mark.asyncio
async def test_fetch_sequence_search_results_job_failed():
    async def mock_fetch_json(session, url):
        return 200, {"status": "error"}, None

    with patch("rnacentral_sequence_search.search.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_sequence_search_results("job-failed")

    assert result == "Search job `job-failed` failed (status: error)."


@pytest.mark.asyncio
async def test_fetch_sequence_search_results_still_running():
    async def mock_fetch_json(session, url):
        return 200, {
            "status": "running",
            "progress": 60.0,
            "databases_finished": 3,
            "databases_total": 5
        }, None

    with patch("rnacentral_sequence_search.search.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_sequence_search_results("job-running")

    assert "Search job `job-running` is running: 60% complete (3/5 databases). Still running; check again later." in result


@pytest.mark.asyncio
async def test_fetch_sequence_search_results_finished_no_hits_yet():
    async def mock_fetch_json(session, url):
        if "job-status" in url:
            return 200, {"status": "finished"}, None
        elif "job-results" in url:
            return 200, {"entries": []}, None
        return 404, None, "Not found"

    with patch("rnacentral_sequence_search.search.fetch_json_with_retry", side_effect=mock_fetch_json):
        result = await fetch_sequence_search_results("job-empty-yet")

    assert "Search job `job-empty-yet` has finished but returned no hits yet." in result
    assert "Results can take about 30 seconds to appear after completion" in result
