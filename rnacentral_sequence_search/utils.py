import aiohttp
import logging
from typing import Optional, List

logger = logging.getLogger('rna_search')

# Base URLs
RNA_CENTRAL_SERVER = "https://search.rnacentral.org/"
EBI_SEARCH_URL = "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral"
EXPORT_SERVICE_URL = "https://export.rnacentral.org/"
ENSEMBL_GRAPHQL_URL = "https://beta.ensembl.org/data/graphql"

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

async def resolve_gene_coordinates(session: aiohttp.ClientSession, taxid: int, gene_symbol: Optional[str]):
    """Uses Ensembl GraphQL to get the coordinates of a gene and/or scientific name."""
    # 1. Get genome ID and scientific name
    query = {
        "query": f"""
        query GetGenome {{
          genomes(by_keyword: {{ species_taxonomy_id: "{taxid}" }}) {{
            genome_id
            scientific_name
            assembly_accession
            genome_tag
          }}
        }}
        """
    }
    
    genome_id = None
    scientific_name = None
    try:
        async with session.post(ENSEMBL_GRAPHQL_URL, json=query) as resp:
            if resp.status == 200:
                data = await resp.json()
                genomes = data.get("data", {}).get("genomes", [])
                if genomes:
                    # Heuristic: Prefer GRCh38 for human, or generally the one with highest accession
                    sorted_genomes = sorted(
                        genomes, 
                        key=lambda x: x.get("assembly_accession", ""), 
                        reverse=True
                    )
                    
                    # Also prefer grch38 tag if available (common for many species in beta Ensembl)
                    grch38_genomes = [g for g in sorted_genomes if g.get("genome_tag") == "grch38"]
                    best_genome = grch38_genomes[0] if grch38_genomes else sorted_genomes[0]
                    
                    genome_id = best_genome.get("genome_id")
                    scientific_name = best_genome.get("scientific_name")
            else:
                return None, None, f"GraphQL genome query failed: {resp.status}"
    except Exception as e:
        logger.error(f"GraphQL genome error: {e}")
        return None, None, f"GraphQL genome error: {e}"
            
    if not genome_id:
        return None, None, f"Could not resolve genome_id for taxon ID: {taxid} via Ensembl GraphQL."

    if not gene_symbol:
        return None, scientific_name, None

    # 2. Get gene coordinates
    gene_query = {
        "query": f"""
        query GenesBySymbol {{
          genes(by_symbol: {{ 
            genome_id: "{genome_id}", 
            symbol: "{gene_symbol}" 
          }}) {{
            stable_id
            slice {{
              region {{
                name
              }}
              location {{
                start
                end
              }}
            }}
          }}
        }}
        """
    }
    
    try:
        async with session.post(ENSEMBL_GRAPHQL_URL, json=gene_query) as resp:
            if resp.status == 200:
                data = await resp.json()
                genes = data.get("data", {}).get("genes", [])
                if not genes:
                    return None, scientific_name, f"Gene {gene_symbol} not found in genome {genome_id}."
                
                gene = genes[0]
                slice_info = gene.get("slice", {})
                region_name = slice_info.get("region", {}).get("name")
                location = slice_info.get("location", {})
                start = location.get("start")
                end = location.get("end")
                
                if region_name and start is not None and end is not None:
                    return (region_name, start, end), scientific_name, None
                else:
                    return None, scientific_name, "Gene found but missing coordinate information."
            else:
                return None, scientific_name, f"GraphQL gene query failed: {resp.status}"
    except Exception as e:
        return None, scientific_name, f"GraphQL gene error: {e}"

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
    hits = results
    num_hits = len(hits)
    
    if num_hits == 0:
        return f"No matches found for the provided sequence."
    
    markdown = [
        f"# RNAcentral Search Results",
        f"Found **{num_hits}** potential matches.",
        f"",
        f"## Top Hits"
    ]
    
    for i, hit in enumerate(hits[:5]):
        rnacentral_id = hit.get("rnacentral_id", "Unknown")
        description = hit.get("description", "No description available")
        score = hit.get("score", "N/A")
        
        markdown.append(f"### {i+1}. {description}")
        markdown.append(f"**RNAcentral ID**: [{rnacentral_id}](https://rnacentral.org/rna/{rnacentral_id})")
        markdown.append(f"**Score**: {score}")
        markdown.append("")
    
    markdown.append(f"## View Complete Results")
    markdown.append(f"View the full results at: [RNAcentral Search Results]({RNA_CENTRAL_SERVER}?jobid={job_id})")
    return "\n".join(markdown)
