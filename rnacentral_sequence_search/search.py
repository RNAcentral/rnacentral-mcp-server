import aiohttp
import asyncio
import logging
from typing import Optional, List
from rnacentral_sequence_search.utils import (
    resolve_taxid, build_ebi_query, format_results, fetch_json_with_retry,
    EBI_SEARCH_URL, EXPORT_SERVICE_URL, RNA_CENTRAL_SERVER
)

logger = logging.getLogger('rna_search')

async def perform_query_rnacentral(
    query: str,
    rna_type: Optional[str] = None,
    taxon: Optional[str] = None,
    expert_db: Optional[str] = None,
    has_secondary_structure: Optional[bool] = None,
    limit: int = 10
) -> str:
    """Core logic for querying RNAcentral using EBI Search."""
    limit = min(max(1, limit), 20)
    
    async with aiohttp.ClientSession() as session:
        taxon_id = await resolve_taxid(session, taxon)
        
        full_query = build_ebi_query(
            query=query,
            rna_type=rna_type,
            taxon_id=taxon_id,
            expert_db=expert_db,
            has_secondary_structure=has_secondary_structure
        )
        
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
            async with session.get(EBI_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return f"Error querying EBI Search: {response.status} - {error_text}"
                ebi_data = await response.json()
            
            entries = ebi_data.get('entries', [])
            if not entries:
                return f"No results found for query: {full_query}"
            
            async def fetch_rnacentral_metadata(entry):
                urs_full = entry['id']
                urs = urs_full.split('_')[0]
                url = f"https://rnacentral.org/api/v1/rna/{urs}"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json()
                except Exception:
                    pass
                return None

            tasks = [fetch_rnacentral_metadata(entry) for entry in entries]
            rnacentral_metadata_list = await asyncio.gather(*tasks)
            
            markdown = [f"# RNAcentral Search Results: {query}", ""]
            if taxon_id:
                markdown.append(f"**Taxon Filter**: {taxon} (NCBI:{taxon_id})\n")
            
            for i, (entry, meta) in enumerate(zip(entries, rnacentral_metadata_list)):
                urs_full = entry['id']
                urs = urs_full.split('_')[0]
                fields_data = entry.get('fields', {})
                
                def get_field(fname, default="N/A"):
                    f_list = fields_data.get(fname, [])
                    return f_list[0] if f_list else default

                desc = get_field('description', 'No description')
                r_type = get_field('rna_type')
                tax_str = get_field('tax_string')
                if tax_str == "N/A":
                    tax_str = get_field('common_name', 'Unknown')
                elif ";" in tax_str:
                    parts = [p.strip() for p in tax_str.split(';') if p.strip()]
                    if len(parts) > 3:
                        tax_str = "... " + "; ".join(parts[-3:])
                
                expert_dbs = ", ".join(fields_data.get('expert_db', []))
                length = get_field('length')
                has_2d = get_field('has_secondary_structure', 'false').lower() == 'true'
                
                markdown.append(f"### {i+1}. [{urs_full}](https://rnacentral.org/rna/{urs})")
                markdown.append(f"**Description**: {desc}")
                markdown.append(f"**Type**: {r_type} | **Organism**: {tax_str} | **Length**: {length} nt")
                if expert_dbs:
                    markdown.append(f"**Databases**: {expert_dbs}")
                
                if meta:
                    go_annots = meta.get('go_annotations', [])
                    if go_annots:
                        go_terms = [x.get('ontology_term', {}).get('name') for x in go_annots[:3] if x.get('ontology_term', {}).get('name')]
                        if go_terms:
                            markdown.append(f"**GO Annotations**: {', '.join(go_terms)}")
                    
                    rfam_hits_data = meta.get('rfam_hits', [])
                    if rfam_hits_data:
                        rfam_links = [f"[{x.get('rfam_family_id')}](https://rfam.org/family/{x.get('rfam_family_id')})" for x in rfam_hits_data[:2] if x.get('rfam_family_id')]
                        if rfam_links:
                            markdown.append(f"**Rfam Hits**: {', '.join(rfam_links)}")
                
                if has_2d:
                    markdown.append("**2D Structure**: Available")
                
                markdown.append("")
                
            return "\n".join(markdown)
        except Exception as e:
            logger.error(f"Error in perform_query_rnacentral: {e}")
            return f"An error occurred while querying RNAcentral: {str(e)}"

async def perform_export_sequences(
    query: str,
    rna_type: Optional[str] = None,
    taxon: Optional[str] = None,
    expert_db: Optional[str] = None,
    has_secondary_structure: Optional[bool] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    format: str = "fasta"
) -> str:
    """Core logic for bulk sequence export."""
    format = format.lower()
    if format not in ["fasta", "parquet"]:
        return "Error: Unsupported format. Please choose 'fasta' or 'parquet'."
        
    async with aiohttp.ClientSession() as session:
        taxon_id = await resolve_taxid(session, taxon)
        full_query = build_ebi_query(query, rna_type, taxon_id, expert_db, has_secondary_structure, min_length, max_length)
        api_url = f"{EBI_SEARCH_URL}?query={full_query}&format=json"
        payload = {
            "api_url": api_url, 
            "format": format,
            "data_type": format
        }
        
        try:
            async with session.post(f"{EXPORT_SERVICE_URL}submit", json=payload) as resp:
                if resp.status not in [200, 201, 202]:
                    return f"Error submitting export job: {resp.status} - {await resp.text()}"
                data = await resp.json()
                task_id = data.get("task_id")
            
            if not task_id:
                return "Error: No task_id returned from export service."

            status_url = f"{EXPORT_SERVICE_URL}status/{task_id}"
            download_url = f"{EXPORT_SERVICE_URL}download/{task_id}/{format}"
            
            is_ready = False
            for _ in range(30):
                await asyncio.sleep(5)
                async with session.get(status_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = str(data.get("state", data.get("status", ""))).lower()
                        if status in ["success", "finished", "completed"]:
                            is_ready = True
                            break
                        elif status in ["failed", "error", "failure"]:
                            error_msg = data.get("error", "Unknown error")
                            return f"Export job failed: {error_msg}"
                
            if not is_ready:
                return f"Export job `{task_id}` is still processing: {download_url}"

            return f"# Bulk Sequence Export\nJob `{task_id}` completed.\n\n### [Download Results]({download_url})"
        except Exception as e:
            return f"An error occurred: {str(e)}"

async def perform_search_sequence(
    sequence: str,
    databases: Optional[List[str]] = None,
) -> str:
    """Submit a sequence search job and return immediately with its job ID (searches can take hours under load)."""
    data = {"databases": databases or [], "sequence": str(sequence)}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{RNA_CENTRAL_SERVER}api/submit-job", json=data) as resp:
                if resp.status != 200:
                    return f"Error submitting search job: HTTP {resp.status}"
                job_id = (await resp.json()).get("job_id")
        if not job_id:
            return "Error: No job_id returned from search service."
        return (f"Search job submitted. Job ID: `{job_id}`\n\n"
                f"The search runs in the background and may take minutes to hours. "
                f"Poll `get_sequence_search_results` with this job ID until it reports the job is finished.")
    except Exception as e:
        logger.error(f"Error in perform_search_sequence: {e}")
        return f"An error occurred while searching: {str(e)}"


async def fetch_sequence_search_results(job_id: str, sequence: str = "") -> str:
    """Single status check for a job; returns progress, or formatted results once finished."""
    try:
        async with aiohttp.ClientSession() as session:
            _, status_data, err = await fetch_json_with_retry(session, f"{RNA_CENTRAL_SERVER}api/job-status/{job_id}")
            if err:
                return f"Error checking job status: {err}"
            status = status_data.get("status", "")
            if status in ("error", "not_found"):
                return f"Search job `{job_id}` failed (status: {status})."
            if status != "finished":
                return (f"Search job `{job_id}` is {status}: {status_data.get('progress', 0):.0f}% complete "
                        f"({status_data.get('databases_finished', 0)}/{status_data.get('databases_total', '?')} databases). "
                        f"Still running; check again later.")
            _, result_data, err = await fetch_json_with_retry(session, f"{RNA_CENTRAL_SERVER}api/job-results/{job_id}")
            if err:
                return f"Error retrieving results: {err}"
            if not result_data.get("entries"):
                # The service reports "finished" ~20s before hits are queryable, so empty is ambiguous.
                return (f"Search job `{job_id}` has finished but returned no hits yet. Results can take about "
                        f"30 seconds to appear after completion; check again once. If it is still empty, there are no matches.")
            return format_results(result_data, job_id, sequence)
    except Exception as e:
        logger.error(f"Error in fetch_sequence_search_results: {e}")
        return f"An error occurred while fetching results: {str(e)}"
