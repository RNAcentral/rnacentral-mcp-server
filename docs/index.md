# RNAcentral MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes the
[RNAcentral](https://rnacentral.org) database — non-coding RNA sequences, cross-references,
genomic context, 2D structures, and literature summaries — as tools your LLM can call.

The server orchestrates several upstream APIs (EBI Search, RNAcentral REST, Ensembl GraphQL,
the sequence-search and export microservices) so the model can answer a single question with
a single tool call instead of chaining raw HTTP requests.

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
```

```{toctree}
:maxdepth: 2
:caption: Tool reference

tools/index
```

```{toctree}
:maxdepth: 1
:caption: Examples

examples
```
