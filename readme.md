# RNAcentral MCP Server

[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue)](https://rnacentral.github.io/rnacentral-mcp-server/)

This is an MCP server that provides a comprehensive interface to the RNAcentral database, allowing for complex searches, sequence mapping, genomic analysis, and metadata retrieval for non-coding RNA sequences.

📖 **Full documentation:** <https://rnacentral.github.io/rnacentral-mcp-server/> — installation guides for Claude Desktop / Claude Code / other MCP clients, per-tool reference, and examples.

## Features

- **Comprehensive Search**: Query RNAcentral using natural language or filters (RNA type, taxon, expert database). Combines EBI Search and RNAcentral API data for enriched metadata (Rfam hits, GO annotations).
- **Sequence Search**: Search for RNA sequences across multiple databases to find identical or similar entries.
- **Bidirectional ID Mapping**: Map between RNAcentral URS IDs and external database identifiers (miRBase, Ensembl, HGNC, etc.) with automatic taxonomy resolution.
- **Bulk Sequence Export**: Export search results in FASTA or Parquet formats, ideal for downstream analysis or machine learning datasets.
- **Genomic Overlap (Ensembl)**: Find non-coding RNAs overlapping specific genomic coordinates or gene symbols using Ensembl's GraphQL integration.
- **2D Structure Diagrams**: Retrieve secondary structure (2D) diagrams in SVG format for RNAs with known or predicted folds.
- **Literature Summaries**: Access AI-generated literature summaries for RNA sequences to understand their biological context.

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

1. Set up a Python environment:

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Add dependencies
uv add "mcp[cli]" aiohttp
```

2. Install the package in editable mode:

```bash
uv pip install -e .
```

## Running the Server

### Development Mode (with MCP Inspector)

```bash
mcp dev rnacentral_sequence_search/server.py
```

This will start the server and open the MCP Inspector, allowing you to test the server interactively.

### Using with Claude Desktop

To install the server in Claude Desktop, add this to your `claude_desktop_config.json`. You can optionally specify a `--log-dir` to save logs to a specific directory:

```json
{
  "mcpServers": {
    "rnacentral": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/rnacentral/rnacentral-mcp-server.git",
        "run-server",
        "--log-dir",
        "/Users/YOUR_USERNAME/logs/rnacentral"
      ]
    }
  }
}
```

### Direct Execution

You can run the server directly using Python. Use the `--log-dir` argument to specify where to save log files:

```bash
python rnacentral_sequence_search/server.py --log-dir ./logs
```

Or using the installed script:

```bash
run-server --log-dir ./logs
```

## Usage Examples

Once the server is running, you can interact with various tools:

### Bidirectional ID Mapping

Map an external ID to RNAcentral and see all cross-references:

```
Tool: map_rna_id
Arguments:
{
  "identifier": "MIMAT0000062",
  "taxon": "Homo sapiens"
}
```

### Genomic Overlap

Find ncRNAs overlapping a specific gene in human:

```
Tool: get_overlapping_ncrnas
Arguments:
{
  "species": "human",
  "gene_symbol": "HOTAIR"
}
```

### 2D Structure Retrieval

Get the secondary structure diagram for a specific URS ID:

```
Tool: get_secondary_structure_svg
Arguments:
{
  "urs_id": "URS0000049E57"
}
```

### Bulk Sequence Export

Export a set of sequences matching a search query for machine learning:

```
Tool: export_sequences
Arguments:
{
  "query": "lncRNA",
  "taxon": "9606",
  "format": "parquet",
  "max_length": 500
}
```

### Literature Summaries

Get a summary of the known biological role of an RNA:

```
Tool: get_rna_description
Arguments:
{
  "rna_id": "mmu-mir-191"
}
```

## Notes

- The server handles complex queries by orchestrating multiple upstream APIs (EBI Search, RNAcentral, Ensembl).
- Sequence searches poll for results with a timeout to handle varying server loads.
- The 2D structure SVG can be used for direct visualization in supporting clients.
- For very large exports, use the `export_sequences` tool which uses specialized microservices for efficiency.
