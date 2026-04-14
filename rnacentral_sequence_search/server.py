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
    taxon: Optional[str] = None,
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
        taxon: Taxon name or NCBI Taxonomy ID. Prefer scientific names (e.g. "Homo sapiens", "Mus musculus") over common names if available.
        expert_db: Source database (e.g., "miRBase", "GENCODE", "Ensembl")
        has_secondary_structure: Filter for RNAs with known 2D structure
        limit: Number of results to return (default 10, max 20)
    """
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
            # 1. Query EBI Search
            async with session.get(EBI_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return f"Error querying EBI Search: {response.status} - {error_text}"
                ebi_data = await response.json()
            
            entries = ebi_data.get('entries', [])
            if not entries:
                return f"No results found for query: {full_query}"
            
            # 2. Concurrently fetch metadata from RNAcentral
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
            
            # 3. Format results
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
                    # GO terms
                    go_annots = meta.get('go_annotations', [])
                    if go_annots:
                        go_terms = [x.get('ontology_term', {}).get('name') for x in go_annots[:3] if x.get('ontology_term', {}).get('name')]
                        if go_terms:
                            markdown.append(f"**GO Annotations**: {', '.join(go_terms)}")
                    
                    # Rfam hits
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
            logger.error(f"Error in query_rnacentral: {e}")
            return f"An error occurred while querying RNAcentral: {str(e)}"

@mcp.tool()
async def export_sequences(
    query: str,
    rna_type: Optional[str] = None,
    taxon: Optional[str] = None,
    expert_db: Optional[str] = None,
    has_secondary_structure: Optional[bool] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    format: str = "fasta"
) -> str:
    """
    Export bulk RNA sequences matching a query in FASTA or Parquet format.
    Use this for large-scale data retrieval (e.g., ML dataset generation).
    
    Args:
        query: Search term (e.g., "telomerase", "hsa-mir-126", "HOTAIR")
        rna_type: Filter by RNA type (e.g., "miRNA", "lncRNA", "tRNA")
        taxon: Taxon name or NCBI Taxonomy ID.
        expert_db: Source database (e.g., "miRBase", "GENCODE", "Ensembl")
        has_secondary_structure: Filter for RNAs with known 2D structure
        min_length: Minimum sequence length (nt)
        max_length: Maximum sequence length (nt)
        format: Output format ("fasta" or "parquet", default "fasta")
    """
    format = format.lower()
    if format not in ["fasta", "parquet"]:
        return "Error: Unsupported format. Please choose 'fasta' or 'parquet'."
        
    async with aiohttp.ClientSession() as session:
        taxon_id = await resolve_taxid(session, taxon)
        
        full_query = build_ebi_query(
            query=query,
            rna_type=rna_type,
            taxon_id=taxon_id,
            expert_db=expert_db,
            has_secondary_structure=has_secondary_structure,
            min_length=min_length,
            max_length=max_length
        )
        
        # Build source API URL for EBI Search
        # The export service needs the full URL that the export would be based on
        source_api_url = f"{EBI_SEARCH_URL}?query={full_query}"
        
        payload = {
            "source_api_url": source_api_url,
            "format": format
        }
        
        try:
            # 1. Submit export job
            async with session.post(f"{EXPORT_SERVICE_URL}submit", json=payload) as resp:
                if resp.status not in [200, 201, 202]:
                    error_text = await resp.text()
                    return f"Error submitting export job: {resp.status} - {error_text}"
                data = await resp.json()
                job_id = data.get("job_id")
                if not job_id:
                    return "Error: No job ID returned from export service"

            # 2. Poll for completion
            download_url = f"{EXPORT_SERVICE_URL}download/{job_id}/{format}"
            status_url = f"{EXPORT_SERVICE_URL}status?job_id={job_id}"
            
            attempts = 0
            max_attempts = 30 # 5 minutes with 10s sleep
            
            is_ready = False
            while attempts < max_attempts:
                attempts += 1
                async with session.get(status_url) as resp:
                    if resp.status == 200:
                        status_data = await resp.json()
                        status = status_data.get("status", "").lower()
                        if status == "finished" or status == "success":
                            is_ready = True
                            break
                        elif status == "failed":
                            return f"Export job failed: {status_data.get('message', 'Unknown error')}"
                await asyncio.sleep(10)

            if not is_ready:
                return f"Export job `{job_id}` is still processing. You can download the results once ready at: {download_url}"

            # 3. Format result
            markdown = [
                "# Bulk Sequence Export",
                f"Your export job (`{job_id}`) has completed successfully.",
                "",
                f"**Query**: `{full_query}`",
                f"**Format**: {format.upper()}",
                "",
                f"### [Download Results]({download_url})",
                "",
                "Note: The download link will trigger the file download directly. The file might be compressed (e.g., .gz) for FASTA."
            ]
            return "\n".join(markdown)

        except Exception as e:
            logger.error(f"Error in export_sequences: {e}")
            return f"An error occurred while exporting sequences: {str(e)}"

@mcp.tool()
async def get_overlapping_ncrnas(
    species: str,
    chromosome: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    gene_symbol: Optional[str] = None
) -> str:
    """
    Get non-coding RNAs overlapping a genomic region or a specific gene.
    
    You must provide EITHER:
    - chromosome, start, and end (e.g., chromosome="1", start=100000, end=200000)
    - OR gene_symbol (e.g., "BRCA2"), which will be automatically resolved to coordinates via Ensembl.
    
    Args:
        species: Common name (e.g. "human", "mouse") or scientific name (e.g. "homo_sapiens").
        chromosome: Chromosome name (e.g., "1", "X", "chr1").
        start: Start coordinate.
        end: End coordinate.
        gene_symbol: Gene symbol to lookup coordinates for.
    """
    if not gene_symbol and not (chromosome and start is not None and end is not None):
        return "Error: You must provide EITHER gene_symbol OR (chromosome, start, and end)."
        
    async with aiohttp.ClientSession() as session:
        # 1. Resolve taxon ID
        taxon_id = await resolve_taxid(session, species)
        if not taxon_id:
            return f"Error: Could not resolve species '{species}' to a Taxon ID."

        # 2. Resolve coordinates and/or scientific name via Ensembl
        # We call this even if gene_symbol is not provided to get the canonical scientific_name
        coords, scientific_name, err = await resolve_gene_coordinates(session, taxon_id, gene_symbol)
        
        if gene_symbol:
            if err:
                return f"Coordinate Resolution Error: {err}"
            chromosome, start, end = coords
            
        # 3. Determine RNAcentral species identifier (lowercase_with_underscores)
        if scientific_name:
            rnacentral_species = scientific_name.lower().replace(" ", "_")
        else:
            # Fallback to input if Ensembl failed to give a name but we have coordinates
            rnacentral_species = species.lower().replace(" ", "_")
            
        # 4. Query RNAcentral Overlap API
        # Remove 'chr' prefix if present for RNAcentral
        chr_clean = str(chromosome).replace("chr", "") if str(chromosome).lower().startswith("chr") else str(chromosome)
        
        # Build API URL: https://rnacentral.org/api/v1/overlap/region/{species}/{chr}:{start}-{end}/
        url = f"https://rnacentral.org/api/v1/overlap/region/{rnacentral_species}/{chr_clean}:{start}-{end}/"
        
        try:
            all_results = []
            current_url = url
            
            # Limit pagination to prevent excessive context usage
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
            
            # Filter results to transcripts and ensure they are ncRNAs
            transcripts = [r for r in all_results if r.get("feature_type") == "transcript"]
            if not transcripts:
                # Fallback if no explicit transcripts but we have results (some endpoints differ)
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
            
            # Show top 15 results
            for i, hit in enumerate(transcripts[:15]):
                urs_raw = hit.get("rnacentral_id") or hit.get("ID", "Unknown")
                # Ensure urs_raw is a string to avoid "int is not iterable" error
                urs_str = str(urs_raw)
                urs = urs_str.split("@")[0] if "@" in urs_str else urs_str
                
                desc = hit.get("description", "No description")
                rna_type = hit.get("rna_type") or hit.get("biotype", "Unknown")
                
                # Calculate overlap percentage
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
            logger.error(f"Error in get_overlapping_ncrnas: {e}")
            return f"An error occurred while querying overlap: {str(e)}"

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
        url = f"https://rnacentral.org/api/v1/litsumm/{rna_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                logger.debug(f"Request URL: {url}")
                response.raise_for_status()
                data = await response.json()
                return data.get("summary", "No description available")
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
    if databases is None:
        databases = []
    
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
        
        status = ""
        attempts = 0
        max_attempts = 30
        
        while attempts < max_attempts:
            attempts += 1
            async with session.get(f"{RNA_CENTRAL_SERVER}api/job-status/{job_id}") as response:
                if response.status == 200:
                    status_data = await response.json()
                    status = status_data.get("status", "")
                    if status in ["success", "partial_success"]:
                        break
                    elif status == "failed":
                        return "Search job failed."
                await asyncio.sleep(2) # Sensible polling interval
        
        if status not in ["success", "partial_success"]:
            return "Search timed out."
        
        async with session.get(f"{RNA_CENTRAL_SERVER}api/job-result/{job_id}") as response:
            if response.status == 200:
                results = await response.json()
                return format_results(results, job_id, sequence)
            return f"Error retrieving results: {response.status}"

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

@click.command()
@click.option('--log-dir', type=click.Path(file_okay=False, dir_okay=True, writable=True), help="Directory to store log files.")
def main(log_dir: Optional[str]):
    """Main function to run the MCP server."""
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

if __name__ == "__main__":
    main()
