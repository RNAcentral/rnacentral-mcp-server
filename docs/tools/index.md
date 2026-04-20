# Tool reference

The server registers seven MCP tools. Each page below documents a tool's purpose,
arguments, return shape, and the upstream service it talks to.

```{toctree}
:maxdepth: 1

query_rnacentral
search_sequence
map_rna_id
export_sequences
get_overlapping_ncrnas
get_secondary_structure_svg
get_rna_description
```

## Tool summary

| Tool | Purpose |
| --- | --- |
| [`query_rnacentral`](query_rnacentral.md) | Text/metadata search over RNAcentral with enriched results |
| [`search_sequence`](search_sequence.md) | Similarity search by raw RNA sequence |
| [`map_rna_id`](map_rna_id.md) | Bidirectional mapping between URS IDs and external DB IDs |
| [`export_sequences`](export_sequences.md) | Bulk export of matching sequences (FASTA or Parquet) |
| [`get_overlapping_ncrnas`](get_overlapping_ncrnas.md) | Find ncRNAs overlapping genomic coordinates or a gene |
| [`get_secondary_structure_svg`](get_secondary_structure_svg.md) | Retrieve the 2D structure diagram for a URS ID |
| [`get_rna_description`](get_rna_description.md) | AI-generated literature summary for an RNA |
