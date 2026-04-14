#!/usr/bin/env python3
import asyncio
import os
import logging
from typing import List, Optional
import click
from mcp.server.fastmcp import FastMCP

# Import from feature modules
from rnacentral_sequence_search.mapping import fetch_rna_mapping
from rnacentral_sequence_search.search import perform_query_rnacentral, perform_export_sequences, perform_search_sequence
from rnacentral_sequence_search.overlap import fetch_overlapping_ncrnas
from rnacentral_sequence_search.literature import fetch_rna_description
from rnacentral_sequence_search.structure import fetch_secondary_structure_svg

# Configure logging
logger = logging.getLogger('rna_search')

# Initialize the MCP server
mcp = FastMCP("RNAcentral Sequence Search", dependencies=["aiohttp", "mcp"])

@mcp.tool()
async def get_secondary_structure_svg(urs_id: str):
    """
    Get the secondary structure (2D diagram) for an RNA sequence in SVG format.
    
    Args:
        urs_id: The RNAcentral URS ID (e.g., 'URS0000049E57')
    """
    return await fetch_secondary_structure_svg(urs_id)

@mcp.tool()
async def map_rna_id(identifier: str, taxon: Optional[str] = None) -> str:
    """
    Bidirectional ID mapping for RNA sequences.
    Maps between RNAcentral URS IDs and external database identifiers.
    
    Args:
        identifier: RNAcentral URS ID (e.g., "URS0000759B6D") or External ID (e.g., "MIMAT0000062")
        taxon: Optional taxon name or NCBI Taxonomy ID. Prefer scientific names (e.g. "Homo sapiens", "Mus musculus") if available.
    """
    return await fetch_rna_mapping(identifier, taxon)

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
    return await perform_query_rnacentral(
        query, rna_type, taxon, expert_db, has_secondary_structure, limit
    )

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
    return await perform_export_sequences(
        query, rna_type, taxon, expert_db, has_secondary_structure, min_length, max_length, format
    )

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
        
    return await fetch_overlapping_ncrnas(species, chromosome, start, end, gene_symbol)

@mcp.tool()
async def get_rna_description(rna_id: str) -> str:
    """
    Get a literature summary description of an RNA sequence from RNAcentral.
    
    Args:
        rna_id: The ID of the RNA (e.g., "mmu-mir-191")
    
    Returns:
        A textual description of the RNA sequence based on literature analysis.
    """
    return await fetch_rna_description(rna_id)

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
    return await perform_search_sequence(sequence, databases)

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
