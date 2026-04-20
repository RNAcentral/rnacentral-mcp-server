# Installation

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) — used throughout this project for
  dependency and environment management

## Installing the server

Clone the repository and sync dependencies:

```bash
git clone https://github.com/rnacentral/rnacentral-mcp-server.git
cd rnacentral-mcp-server
uv sync
```

This creates a `.venv/` and installs the server plus its runtime dependencies. The
console script `run-server` becomes available inside that environment.

## Connecting the server to your LLM

The server speaks the Model Context Protocol over stdio, so any MCP-capable client
can launch it. The examples below cover the most common clients — if you're using
something different, point it at the same `uvx ... run-server` command.

### Claude Desktop

Add the server to `claude_desktop_config.json` (on macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

`--log-dir` is optional; pass it if you want on-disk logs for debugging.

Restart Claude Desktop and the `rnacentral` tools should appear in the tool picker.

### Claude Code

Register the server with `claude mcp add`:

```bash
claude mcp add rnacentral -- uvx --from \
  git+https://github.com/rnacentral/rnacentral-mcp-server.git run-server
```

### Other MCP clients

Any client that launches an MCP server over stdio works. The command to run is:

```bash
uvx --from git+https://github.com/rnacentral/rnacentral-mcp-server.git run-server
```

Or, from a local clone:

```bash
uv run run-server --log-dir ./logs
```

## Development mode

Run the server under the MCP Inspector to try tools interactively:

```bash
uv run mcp dev rnacentral_sequence_search/server.py
```

## Building these docs locally

```bash
uv sync --extra docs
uv run sphinx-build -b html docs docs/_build/html
```

Or, from inside `docs/`, `make html`.
