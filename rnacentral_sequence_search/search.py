import aiohttp
import asyncio
import logging
from typing import Optional, List
from rnacentral_sequence_search.utils import (
    resolve_taxid, build_ebi_query, format_results, 
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
        source_api_url = f"{EBI_SEARCH_URL}?query={full_query}"
        payload = {"source_api_url": source_api_url, "format": format}
        
        try:
            async with session.post(f"{EXPORT_SERVICE_URL}submit", json=payload) as resp:
                if resp.status not in [200, 201, 202]:
                    return f"Error submitting export job: {resp.status} - {await resp.text()}"
                data = await resp.json()
                job_id = data.get("job_id")
            
            status_url = f"{EXPORT_SERVICE_URL}status?job_id={job_id}"
            download_url = f"{EXPORT_SERVICE_URL}download/{job_id}/{format}"
            
            is_ready = False
            for _ in range(30):
                async with session.get(status_url) as resp:
                    if resp.status == 200:
                        status = (await resp.json()).get("status", "").lower()
                        if status in ["finished", "success"]:
                            is_ready = True
                            break
                        elif status == "failed":
                            return "Export job failed."
                await asyncio.sleep(10)

            if not is_ready:
                return f"Export job `{job_id}` is still processing: {download_url}"

            return f"# Bulk Sequence Export\nJob `{job_id}` completed.\n\n### [Download Results]({download_url})"
        except Exception as e:
            return f"An error occurred: {str(e)}"

async def perform_search_sequence(
    sequence: str,
    databases: Optional[List[str]] = None,
) -> str:
    """Core logic for sequence-based RNA search."""
    if databases is None: databases = []
    data = {"databases": databases, "query": str(sequence)}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{RNA_CENTRAL_SERVER}api/submit-job", json=data) as resp:
            if resp.status != 201: return f"Error: {resp.status}"
            job_id = (await resp.json()).get("job_id")
        
        status = ""
        for _ in range(30):
            async with session.get(f"{RNA_CENTRAL_SERVER}api/job-status/{job_id}") as resp:
                if resp.status == 200:
                    status = (await resp.json()).get("status", "")
                    if status in ["success", "partial_success"]: break
                    elif status == "failed": return "Search job failed."
            await asyncio.sleep(2)
        
        if status not in ["success", "partial_success"]: return "Search timed out."
        
        async with session.get(f"{RNA_CENTRAL_SERVER}api/job-result/{job_id}") as resp:
            if resp.status == 200:
                return format_results(await resp.json(), job_id, sequence)
            return f"Error retrieving results: {resp.status}"
