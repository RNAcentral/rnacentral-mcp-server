import aiohttp
import asyncio
import logging
from typing import Optional
from rnacentral_sequence_search.utils import resolve_taxid, resolve_gene_coordinates

logger = logging.getLogger('rna_search')

async def fetch_overlapping_ncrnas(
    species: str,
    chromosome: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    gene_symbol: Optional[str] = None
) -> str:
    """Core logic for getting non-coding RNAs overlapping a genomic region."""
    async with aiohttp.ClientSession() as session:
        # 1. Resolve taxon ID
        taxon_id = await resolve_taxid(session, species)
        if not taxon_id:
            return f"Error: Could not resolve species '{species}' to a Taxon ID."

        # 2. Resolve coordinates and/or scientific name via Ensembl
        coords, scientific_name, err = await resolve_gene_coordinates(session, taxon_id, gene_symbol)
        
        if gene_symbol:
            if err:
                return f"Coordinate Resolution Error: {err}"
            chromosome, start, end = coords
            
        # 3. Determine RNAcentral species identifier
        if scientific_name:
            rnacentral_species = scientific_name.lower().replace(" ", "_")
        else:
            rnacentral_species = species.lower().replace(" ", "_")
            
        # 4. Query RNAcentral Overlap API
        chr_clean = str(chromosome).replace("chr", "") if str(chromosome).lower().startswith("chr") else str(chromosome)
        url = f"https://rnacentral.org/api/v1/overlap/region/{rnacentral_species}/{chr_clean}:{start}-{end}/"
        
        try:
            all_results = []
            current_url = url
            
            for _ in range(3): 
                async with session.get(current_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            all_results.extend(data)
                            break
                        elif isinstance(data, dict):
                            results = data.get("results", [])
                            all_results.extend(results)
                            current_url = data.get("next")
                            if not current_url:
                                break
                    elif resp.status == 404:
                        break
                    else:
                        error_text = await resp.text()
                        return f"Error querying RNAcentral overlap API: HTTP {resp.status} - {error_text}\nURL: {url}"
            
            transcripts = [r for r in all_results if r.get("feature_type") == "transcript"]
            if not transcripts:
                transcripts = [r for r in all_results if "Parent" not in r]
                        
            if not transcripts:
                return f"No overlapping RNAs found for {rnacentral_species} ({scientific_name or species}) at {chr_clean}:{start}-{end}."
                
            # 5. Format Results
            markdown = [
                f"# Overlapping ncRNAs in {scientific_name or species}",
                f"**Region**: `{chr_clean}:{start}-{end}`",
            ]
            if gene_symbol:
                markdown.append(f"**Gene Symbol**: `{gene_symbol}`")
                
            markdown.append(f"\nFound **{len(transcripts)}** overlapping ncRNAs.\n")
            
            for i, hit in enumerate(transcripts[:15]):
                urs_raw = hit.get("rnacentral_id") or hit.get("ID", "Unknown")
                urs_str = str(urs_raw)
                urs = urs_str.split("@")[0] if "@" in urs_str else urs_str
                
                desc = hit.get("description", "No description")
                rna_type = hit.get("rna_type") or hit.get("biotype", "Unknown")
                
                hit_start = int(hit.get("start", 0))
                hit_end = int(hit.get("end", 0))
                
                overlap_start = max(start, hit_start)
                overlap_end = min(end, hit_end)
                overlap_len = max(0, overlap_end - overlap_start + 1)
                hit_len = max(1, hit_end - hit_start + 1)
                overlap_pct = (overlap_len / hit_len) * 100
                
                markdown.append(f"### {i+1}. [{urs}](https://rnacentral.org/rna/{urs})")
                if "@" in urs_str:
                    markdown.append(f"**Location**: `{urs_str.split('@')[-1]}`")
                
                markdown.append(f"**Description**: {desc}")
                markdown.append(f"**Type**: {rna_type} | **Overlap**: {overlap_pct:.1f}%")
                markdown.append("")
                
            if len(transcripts) > 15:
                markdown.append(f"*Showing first 15 of {len(transcripts)} results.*")
                
            return "\n".join(markdown)
            
        except Exception as e:
            logger.error(f"Error in fetch_overlapping_ncrnas: {e}")
            return f"An error occurred while querying overlap: {str(e)}"
