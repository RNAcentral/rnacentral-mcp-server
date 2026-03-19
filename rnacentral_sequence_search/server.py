#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import os
from typing import List, Optional
import aiohttp.web
import click
from mcp.server.fastmcp import FastMCP, Context

import logging

logger = logging.getLogger('rna_search')

# Initialize the MCP server
mcp = FastMCP("RNAcentral Sequence Search", dependencies=["aiohttp", "mcp"])

# Base URL for the RNAcentral API
RNA_CENTRAL_SERVER = "https://search.rnacentral.org/"
EBI_SEARCH_URL = "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral"

async def resolve_taxid(session: aiohttp.ClientSession, taxon: Optional[str]) -> Optional[int]:
    """Resolves a taxon name or ID to an NCBI Taxon ID using the ENA API."""
    if not taxon:
        return None
    
    # If it's already an ID, return it
    taxon_str = str(taxon).strip()
    if taxon_str.isdigit():
        return int(taxon_str)
        
    # Try scientific name
    try:
        url = f"https://www.ebi.ac.uk/ena/taxonomy/rest/scientific-name/{taxon_str}"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data and isinstance(data, list):
                    return int(data[0].get("taxId"))
    except Exception:
        pass
        
    # Try common name
    try:
        url = f"https://www.ebi.ac.uk/ena/taxonomy/rest/common-name/{taxon_str}"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data and isinstance(data, list):
                    return int(data[0].get("taxId"))
    except Exception:
        pass
        
    return None

@mcp.tool()
async def map_rna_id(identifier: str, taxon: Optional[str] = None) -> str:
    """
    Bidirectional ID mapping for RNA sequences.
    Maps between RNAcentral URS IDs and external database identifiers.
    
    Args:
        identifier: RNAcentral URS ID (e.g., "URS0000759B6D") or External ID (e.g., "MIMAT0000062")
        taxon: Optional taxon name or NCBI Taxonomy ID. Prefer scientific names (e.g. "Homo sapiens", "Mus musculus") if available.
    """
    async with aiohttp.ClientSession() as session:
        # Normalize identifier
        identifier = identifier.strip()
        urs = identifier.split('_')[0] if identifier.upper().startswith("URS") else None
        
        # 1. If not a URS, try to find the URS from external ID
        if not urs:
            url = f"https://rnacentral.org/api/v1/rna/?external_id={identifier}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        urs = results[0].get("rnacentral_id")
                    else:
                        return f"No RNAcentral entry found for external ID: {identifier}"
                else:
                    return f"Error looking up external ID {identifier}: HTTP {resp.status}"

        # 2. Determine Taxon ID
        taxon_id = await resolve_taxid(session, taxon)
        
        if not taxon_id:
            # If no taxon specified or resolved, try to find one from available xrefs
            xrefs_url = f"https://rnacentral.org/api/v1/rna/{urs}/xrefs"
            async with session.get(xrefs_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        # Prefer human (9606) or the first taxid found
                        human_xref = next((x for x in results if x.get("taxid") == 9606), None)
                        taxon_id = 9606 if human_xref else results[0].get("taxid")
        
        if not taxon_id:
            return f"Could not determine a valid Taxon ID for {urs}"

        # 3. Fetch all cross-references for this taxon using the taxon-specific endpoint
        current_url = f"https://rnacentral.org/api/v1/rna/{urs}/xrefs/{taxon_id}/"
        all_xrefs = []
        for _ in range(5): # Paginate through taxon-specific xrefs
            async with session.get(current_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    all_xrefs.extend(data.get("results", []))
                    current_url = data.get("next")
                    if not current_url: break
                else:
                    break
        
        if not all_xrefs:
            return f"No cross-references found for {urs} in taxon {taxon_id}"

        # 4. Filter and Group IDs
        primary_id = f"{urs}_{taxon_id}"
        db_priority = ["HGNC", "miRBase", "Ensembl", "Rfam", "NCBI Gene", "GtRNAdb", "NONCODE"]
        
        canonical_id = None
        secondary_ids = set()
        
        # Find canonical ID
        for db in db_priority:
            for xref in all_xrefs:
                if xref.get("database", "").lower() == db.lower():
                    acc = xref.get("accession", {})
                    cid = acc.get("optional_id") or acc.get("id")
                    if cid:
                        canonical_id = f"{db}: {cid}"
                        break
            if canonical_id:
                break
        
        # Collect all other unique IDs
        for xref in all_xrefs:
            db = xref.get("database")
            acc = xref.get("accession", {})
            
            for field in ["id", "external_id", "optional_id"]:
                val = acc.get(field)
                if val:
                    # Clean up DB prefix if present
                    clean_val = val
                    if ":" in val and val.lower().startswith(db.lower()):
                        parts = val.split(":", 1)
                        if len(parts) > 1:
                            clean_val = parts[1].strip()
                    secondary_ids.add(f"{db}: {clean_val}")

        # Remove canonical from secondary
        if canonical_id:
            secondary_ids.discard(canonical_id)
            cid_val = canonical_id.split(": ")[-1]
            secondary_ids = {sid for sid in secondary_ids if not sid.endswith(f": {cid_val}")}

        # 5. Format Output
        markdown = [f"# ID Mapping for {identifier}", ""]
        markdown.append(f"**Primary ID**: `{primary_id}`")
        if taxon_id:
            markdown.append(f"**NCBI Taxon ID**: `{taxon_id}`")
        if canonical_id:
            markdown.append(f"**Canonical ID**: `{canonical_id}`")
        
        if secondary_ids:
            markdown.append("\n**Secondary Identifiers**:")
            for sid in sorted(list(secondary_ids)):
                markdown.append(f"- {sid}")
        
        return "\n".join(markdown)

@mcp.tool()
async def query_rnacentral(
    query: str,
    rna_type: Optional[str] = None,
    taxon_id: Optional[int] = None,
    expert_db: Optional[str] = None,
    has_secondary_structure: Optional[bool] = None,
    limit: int = 10
) -> str:
    """
    Comprehensive search for RNA sequences using EBI Search and RNAcentral APIs.
    Combines text search filters with detailed metadata (Rfam, GO, 2D structure).
    
    Args:
        query: Search term (e.g., "telomerase", "hsa-mir-126", "HOTAIR")
        rna_type: Filter by RNA type (e.g., "miRNA", "lncRNA", "tRNA")
        taxon_id: NCBI Taxonomy ID (e.g., 9606 for human, 10090 for mouse)
        expert_db: Source database (e.g., "miRBase", "GENCODE", "Ensembl")
        has_secondary_structure: Filter for RNAs with known 2D structure
        limit: Number of results to return (default 10, max 20)
    """
    # Ensure limit is within reasonable bounds
    limit = min(max(1, limit), 20)
    
    # Construct EBI Search query
    query_parts = [f"({query})"]
    if rna_type:
        query_parts.append(f'rna_type:"{rna_type}"')
    if taxon_id:
        # Some EBI indices use tax_string or similar for numeric IDs in query
        query_parts.append(str(taxon_id))
    if expert_db:
        query_parts.append(f'expert_db:"{expert_db}"')
    if has_secondary_structure is not None:
        val = "true" if has_secondary_structure else "false"
        query_parts.append(f"has_secondary_structure:{val}")
    
    full_query = " AND ".join(query_parts)
    
    fields = [
        'description', 'rna_type', 'expert_db', 'common_name', 
        'tax_string', 'has_secondary_structure', 'length'
    ]
    
    params = {
        'query': full_query,
        'fields': ','.join(fields),
        'format': 'json',
        'size': limit
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Query EBI Search
            # We use the EBI REST API to get basic metadata and hits
            ebi_url = "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral"
            async with session.get(ebi_url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return f"Error querying EBI Search: {response.status} - {error_text}"
                ebi_data = await response.json()
            
            entries = ebi_data.get('entries', [])
            if not entries:
                return f"No results found for query: {full_query}"
            
            # 2. Concurrently fetch metadata from RNAcentral for each hit
            async def fetch_rnacentral_metadata(entry):
                urs_full = entry['id']
                urs = urs_full.split('_')[0]
                url = f"https://rnacentral.org/api/v1/rna/{urs}"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        else:
                            logger.error(f"Error fetching metadata for {urs}: HTTP {resp.status}")
                except Exception as e:
                    logger.error(f"Exception fetching metadata for {urs}: {e}")
                return None

            tasks = [fetch_rnacentral_metadata(entry) for entry in entries]
            rnacentral_metadata_list = await asyncio.gather(*tasks)
            
            # 3. Format results
            markdown = [f"# RNAcentral Search Results: {query}", ""]
            
            for i, (entry, meta) in enumerate(zip(entries, rnacentral_metadata_list)):
                urs_full = entry['id']
                urs = urs_full.split('_')[0]
                fields_data = entry.get('fields', {})
                
                # EBI Fields are lists; use .get() with a safe default
                def get_field(fname, default="N/A"):
                    f_list = fields_data.get(fname, [])
                    return f_list[0] if f_list else default

                desc = get_field('description', 'No description')
                r_type = get_field('rna_type')
                # Try tax_string first; truncate it if it's too long
                tax = get_field('tax_string')
                if tax == "N/A":
                    tax = get_field('common_name', 'Unknown')
                elif ";" in tax:
                    # Show only the last 3 parts for brevity
                    parts = [p.strip() for p in tax.split(';') if p.strip()]
                    if len(parts) > 3:
                        tax = "... " + "; ".join(parts[-3:])
                
                expert_dbs = ", ".join(fields_data.get('expert_db', []))
                length = get_field('length')
                has_2d = get_field('has_secondary_structure', 'false').lower() == 'true'
                
                markdown.append(f"### {i+1}. [{urs_full}](https://rnacentral.org/rna/{urs})")
                markdown.append(f"**Description**: {desc}")
                markdown.append(f"**Type**: {r_type} | **Organism**: {tax} | **Length**: {length} nt")
                if expert_dbs:
                    markdown.append(f"**Databases**: {expert_dbs}")
                
                if meta:
                    # Extract high-signal info from RNAcentral API response
                    # GO terms
                    go_annots = meta.get('go_annotations', [])
                    if go_annots:
                        go_terms = []
                        for x in go_annots[:3]:
                            term = x.get('ontology_term', {})
                            if term and term.get('name'):
                                go_terms.append(term.get('name'))
                        if go_terms:
                            markdown.append(f"**GO Annotations**: {', '.join(go_terms)}")
                    
                    # Rfam hits
                    rfam_hits_data = meta.get('rfam_hits', [])
                    if rfam_hits_data:
                        rfam_links = []
                        for x in rfam_hits_data[:2]:
                            rfam_id = x.get('rfam_family_id')
                            if rfam_id:
                                rfam_links.append(f"[{rfam_id}](https://rfam.org/family/{rfam_id})")
                        if rfam_links:
                            markdown.append(f"**Rfam Hits**: {', '.join(rfam_links)}")
                
                if has_2d:
                    markdown.append("**2D Structure**: Available")
                
                markdown.append("")
                
            return "\n".join(markdown)

    except Exception as e:
        logger.error(f"Error in query_rnacentral: {e}")
        return f"An error occurred while querying RNAcentral: {str(e)}"


@mcp.tool()
async def get_rna_description(rna_id: str) -> str:
    """
    Get a literature summary description of an RNA sequence from RNAcentral.
    
    Args:
        rna_id: The ID of the RNA (e.g., "mmu-mir-191")
    
    Returns:
        A textual description of the RNA sequence based on literature analysis.
    """
    try:
        # Format the API URL
        url = f"https://rnacentral.org/api/v1/litsumm/{rna_id}"
        
        # Make the API request
        async with aiohttp.ClientSession() as session:
            response = await session.get(url)
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Response status: {response.status}")
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Parse the response
            data = await response.json()
            # Check if description is available
            return data.get("summary", "No description available")
            
    
    except aiohttp.web.HTTPException as e:
        logger.error(f"HTTP error: {e}")
        if e.response.status_code == 404:
            return f"RNA ID '{rna_id}' not found in RNAcentral database."
        else:
            return f"Error querying RNAcentral API: HTTP {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error querying RNAcentral API: {str(e)}"

@mcp.tool()
async def search_sequence(
    sequence: str,
    databases: Optional[List[str]] = None,
) -> str:
    """
    Search the RNAcentral database for a given RNA sequence.
    
    Args:
        sequence: The RNA sequence to search for
        databases: Optional list of specific databases to search within (default: all databases)

    Returns:
        A markdown formatted summary of search results
    """
    logging.error("starting?")
    
    # Default to empty list for searching all databases
    if databases is None:
        databases = []
    
    # Format data for API call
    data = {"databases": databases, "query": str(sequence)}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{RNA_CENTRAL_SERVER}api/submit-job", json=data) as response:
            if response.status != 201:
                error_text = await response.text()
                return f"Error submitting search job: {response.status} - {error_text}"
            
            job_data = await response.json()
            job_id = job_data.get("job_id")
            
            if not job_id:
                return "Error: No job ID returned from RNAcentral"
        
        # Poll for job status      
        status = ""
        attempts = 0
        max_attempts = 30  # Maximum number of polling attempts
        
        while attempts < max_attempts:
            attempts += 1
            
            async with session.get(f"{RNA_CENTRAL_SERVER}api/job-status/{job_id}") as response:
                if response.status != 200:
                    return f"Error checking job status: {response.status}"
                
                status_data = await response.json()
                status = status_data.get("status", "")
                
                if status in ["success", "partial_success"]:
                    break
                elif status == "failed":
                    return "Search job failed. Please try again with a different sequence."
                
                # Wait before polling again
                await asyncio.sleep(100)
        
        if status not in ["success", "partial_success"]:
            return "Search timed out. Please try a shorter sequence or try again later."
        
        async with session.get(f"{RNA_CENTRAL_SERVER}api/job-result/{job_id}") as response:
            if response.status != 200:
                return f"Error retrieving results: {response.status}"
            
            results = await response.json()
            
        # Process and format results
        report = format_results(results, job_id, sequence)
        return report 


def format_results(results, job_id, sequence):
    """Format search results as markdown"""
    hits = results#.get("hits", [])
    num_hits = len(hits)
    
    if num_hits == 0:
        return f"No matches found for the provided sequence: '{sequence[:30]}...'"
    
    # Prepare markdown output
    markdown = [
        f"# RNAcentral Search Results",
        f"Found **{num_hits}** potential matches for your sequence.",
        f"",
        f"## Top Hits"
    ]
    
    # Process top 5 hits (or fewer if less than 5 results)
    for i, hit in enumerate(hits[:5]):
        rnacentral_id = hit.get("rnacentral_id", "Unknown")
        description = hit.get("description", "No description available")
        score = hit.get("score", "N/A")
        
        markdown.append(f"### {i+1}. {description}")
        markdown.append(f"**RNAcentral ID**: [{rnacentral_id}](https://rnacentral.org/rna/{rnacentral_id})")
        markdown.append(f"**Score**: {score}")
        markdown.append("")
    
    # Add link to full results
    markdown.append(f"## View Complete Results")
    markdown.append(f"View the full results at: [RNAcentral Search Results]({RNA_CENTRAL_SERVER}?jobid={job_id})")
    print("\n".join(markdown))
    return "\n".join(markdown)

@click.command()
@click.option('--log-dir', type=click.Path(file_okay=False, dir_okay=True, writable=True), help="Directory to store log files.")
def main(log_dir: Optional[str]):
    """
    Main function to run the MCP server.
    """
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "rnacentral_mcp.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True
        )
    else:
        logging.basicConfig(level=logging.INFO, force=True)
    
    mcp.run()

# Run the server if executed directly
if __name__ == "__main__":
    main()
