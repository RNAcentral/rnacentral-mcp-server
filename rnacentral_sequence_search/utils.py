import aiohttp
import asyncio
import logging
from typing import Optional, List, Tuple
from urllib.parse import quote

logger = logging.getLogger('rna_search')

# Base URLs
RNA_CENTRAL_SERVER = "https://sequence-search.rnacentral.org/"
EBI_SEARCH_URL = "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral"
EXPORT_SERVICE_URL = "https://export.rnacentral.org/"
ENSEMBL_REST_URL = "https://rest.ensembl.org"
ENA_TAXONOMY_URL = "https://www.ebi.ac.uk/ena/taxonomy/rest/tax-id"

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5


async def fetch_json_with_retry(session: aiohttp.ClientSession, url: str) -> Tuple[int, Optional[dict | list], Optional[str]]:
    """GET url and parse JSON, retrying on network errors and 5xx responses (both are
    typically transient blips, not permanent failures)."""
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return resp.status, await resp.json(), None
                if resp.status < 500:
                    return resp.status, None, f"HTTP {resp.status}"
                last_error = f"HTTP {resp.status}"
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = str(e)

        if attempt < RETRY_ATTEMPTS - 1:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    return 0, None, last_error


async def resolve_taxid(session: aiohttp.ClientSession, taxon: Optional[str]) -> Optional[int]:
    """Resolves a taxon name or ID to an NCBI Taxon ID using the ENA API."""
    if not taxon:
        return None

    # If it's already an ID, return it
    taxon_str = str(taxon).strip()
    if taxon_str.isdigit():
        return int(taxon_str)

    for kind in ("scientific-name", "common-name"):
        _, data, _ = await fetch_json_with_retry(session, f"https://www.ebi.ac.uk/ena/taxonomy/rest/{kind}/{taxon_str}")
        if data and isinstance(data, list):
            return int(data[0].get("taxId"))

    return None

async def resolve_gene_coordinates(session: aiohttp.ClientSession, taxid: int, gene_symbol: Optional[str]):
    """Uses ENA taxonomy + the Ensembl REST API to get the coordinates of a gene and/or scientific name."""
    # 1. Get scientific name for the taxon (needed to build the RNAcentral species slug)
    _, data, err = await fetch_json_with_retry(session, f"{ENA_TAXONOMY_URL}/{taxid}")
    if err:
        logger.error(f"ENA taxonomy lookup error: {err}")
        return None, None, f"ENA taxonomy lookup failed: {err}"

    scientific_name = data.get("scientificName") if data else None
    if not scientific_name:
        return None, None, f"Could not resolve scientific name for taxon ID: {taxid}."

    if not gene_symbol:
        return None, scientific_name, None

    # 2. Get gene coordinates via the Ensembl REST lookup endpoint
    species_slug = scientific_name.lower().replace(" ", "_")
    url = f"{ENSEMBL_REST_URL}/lookup/symbol/{quote(species_slug)}/{quote(gene_symbol)}?content-type=application/json"

    status, data, err = await fetch_json_with_retry(session, url)
    if status == 404:
        return None, scientific_name, f"Gene {gene_symbol} not found in species {species_slug}."
    if err:
        return None, scientific_name, f"Ensembl REST lookup failed: {err}"

    region_name = data.get("seq_region_name")
    start = data.get("start")
    end = data.get("end")

    if region_name and start is not None and end is not None:
        return (region_name, start, end), scientific_name, None
    return None, scientific_name, "Gene found but missing coordinate information."

def build_ebi_query(
    query: str,
    rna_type: Optional[str] = None,
    taxon_id: Optional[int] = None,
    expert_db: Optional[str] = None,
    has_secondary_structure: Optional[bool] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> str:
    """Helper to construct an EBI Search query string."""
    query_parts = [f"({query})"]
    if rna_type:
        query_parts.append(f'rna_type:"{rna_type}"')
    if taxon_id:
        query_parts.append(str(taxon_id))
    if expert_db:
        query_parts.append(f'expert_db:"{expert_db}"')
    if has_secondary_structure is not None:
        val = "true" if has_secondary_structure else "false"
        query_parts.append(f"has_secondary_structure:{val}")
    
    if min_length is not None or max_length is not None:
        l_min = min_length if min_length is not None else "*"
        l_max = max_length if max_length is not None else "*"
        query_parts.append(f"length:[{l_min} TO {l_max}]")
        
    return " AND ".join(query_parts)

def format_results(results, job_id, sequence):
    """Format search results as markdown"""
    hits = results.get("entries", [])
    num_hits = len(hits)
    
    if num_hits == 0:
        return f"No matches found for the provided sequence."
    
    markdown = [
        f"# RNAcentral Search Results",
        f"Found **{results.get('hit_count', num_hits)}** potential matches.",
        f"",
        f"## Top Hits"
    ]
    
    for i, hit in enumerate(hits[:5]):
        rnacentral_id = hit.get("rnacentral_id", "Unknown")
        description = hit.get("description") or "No description available"
        score = hit.get("score", "N/A")
        
        markdown.append(f"### {i+1}. {description}")
        markdown.append(f"**RNAcentral ID**: [{rnacentral_id}](https://rnacentral.org/rna/{rnacentral_id})")
        markdown.append(f"**Score**: {score} | **E-value**: {hit.get('e_value', 'N/A')} | **Identity**: {hit.get('identity', 'N/A'):.1f}% | **Query coverage**: {hit.get('query_coverage', 'N/A'):.1f}%")
        markdown.append("")
    
    markdown.append(f"## View Complete Results")
    markdown.append(f"View the full results at: [RNAcentral Search Results]({RNA_CENTRAL_SERVER}?jobid={job_id})")
    return "\n".join(markdown)


if __name__ == "__main__":
    # ponytail: live smoke check for resolve_gene_coordinates, run manually with
    # `python -m rnacentral_sequence_search.utils` (hits real ENA/Ensembl services)
    async def _demo():
        async with aiohttp.ClientSession() as session:
            coords, sci_name, err = await resolve_gene_coordinates(session, 9606, "SMAD4")
            assert err is None, f"unexpected error: {err}"
            assert sci_name == "Homo sapiens", f"unexpected scientific name: {sci_name}"
            assert coords == ("18", 51028528, 51085045), f"unexpected coords: {coords}"
            print("OK:", coords, sci_name)

    asyncio.run(_demo())
