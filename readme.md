# RNAcentral MCP Server

This is an MCP server that wraps the RNAcentral sequence search API, allowing you to easily search for RNA sequences and get nicely formatted results.

## Features

- **Bidirectional ID Mapping**: Map between RNAcentral URS IDs and external database identifiers (miRBase, Ensembl, HGNC, etc.).
- **Comprehensive Search**: Query RNAcentral using natural language or filters (RNA type, taxon, expert database).
- **Metadata Enrichment**: Results include Rfam hits, GO annotations, and 2D structure availability.
- **Sequence Search**: Search for RNA sequences across multiple databases with progress tracking.
- **Markdown Results**: Formatted results with links to RNAcentral entries and external resources.

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

1. Set up a Python environment:

```bash
# Using uv (recommended)
uv init rnacentral-mcp
cd rnacentral-mcp
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Add dependencies
uv add "mcp[cli]" aiohttp
```

Or using pip:

```bash
# Using pip
pip install "mcp[cli]" aiohttp
```

2. Save the `rnacentral_sequence_search/server.py` file to your project directory.

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

Or via the MCP CLI:

```bash
mcp run rnacentral_sequence_search/server.py
```

## Usage Examples

Once the server is running, you can search for RNA sequences:

### Bidirectional ID Mapping

Map an external ID to RNAcentral and see all cross-references (optionally filtered by taxon name or ID):

```
Tool: map_rna_id
Arguments:
{
  "identifier": "MIMAT0000062",
  "taxon": "Homo sapiens"
}
```

### Comprehensive Search

Search for RNAs with specific criteria (e.g., human telomerase RNAs with 2D structure):

```
Tool: query_rnacentral
Arguments:
{
  "query": "telomerase",
  "taxon": "Homo sapiens",
  "has_secondary_structure": true
}
```

### Basic sequence search

Search for an RNA sequence across all databases:

```
Tool: search_sequence
Arguments:
{
  "sequence": "ACCGUGCAAUCGAUGCAU"
}
```

### Search specific databases

Search for a sequence in specific databases:

```
Tool: search_sequence
Arguments:
{
  "sequence": "ACCGUGCAAUCGAUGCAU",
  "databases": ["miRBase", "snoDB"]
}
```

## Notes

- The server polls the RNAcentral API for up to 30 attempts with 2-second intervals between attempts.
- For very large sequences or during high server load, searches might time out.
- The results display the top 5 hits by default, with links to the full results on the RNAcentral website.
