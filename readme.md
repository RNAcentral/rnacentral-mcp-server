# RNAcentral MCP Server

This is an MCP server that wraps the RNAcentral sequence search API, allowing you to easily search for RNA sequences and get nicely formatted results.

## Features

- Search for RNA sequences across multiple databases
- Optional filtering by specific databases
- Progress tracking during search
- Markdown-formatted results with links to RNAcentral entries
- Summary of top hits with detailed information

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

2. Save the `rnacentral_server.py` file to your project directory.

## Running the Server

### Development Mode (with MCP Inspector)

```bash
mcp dev rnacentral_server.py
```

This will start the server and open the MCP Inspector, allowing you to test the server interactively.

### Using with Claude Desktop

To install the server in Claude Desktop, add this to your claude_desktop_config.json:
json
```
  {
    "mcpServers": {
      "rnacentral": {
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/rnacentral/rnacentral-mcp-server.git",
          "run-server"
        ]
      }
    }
  }
```

### Direct Execution

```bash
python rnacentral_server.py
```

Or:

```bash
mcp run rnacentral_server.py
```

## Usage Examples

Once the server is running, you can search for RNA sequences:

### Basic search

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
