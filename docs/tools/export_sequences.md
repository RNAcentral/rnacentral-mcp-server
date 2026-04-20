# `export_sequences`

Bulk export of RNA sequences matching a query. Unlike {doc}`query_rnacentral`,
which returns a handful of enriched hits for a human reader, this tool streams
the full result set through the RNAcentral export microservice and returns it in
a format suitable for downstream processing — FASTA for bioinformatics tools,
Parquet for ML pipelines.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | `str` | yes | Free-text search term. |
| `rna_type` | `str` | no | Restrict to an RNA type (e.g. `"miRNA"`, `"lncRNA"`). |
| `taxon` | `str` | no | Scientific name (preferred) or NCBI Taxonomy ID. |
| `expert_db` | `str` | no | Source database filter. |
| `has_secondary_structure` | `bool` | no | Only include RNAs with a known 2D structure. |
| `min_length` | `int` | no | Minimum sequence length in nucleotides. |
| `max_length` | `int` | no | Maximum sequence length in nucleotides. |
| `format` | `str` | no | `"fasta"` (default) or `"parquet"`. |

## Returns

For `fasta`, a string of FASTA records. For `parquet`, a path (or URL) to the
generated file returned by the export service.

## Notes

- The export service handles pagination internally; there is no client-side
  `limit`. Narrow the query with the filter arguments if you don't want every
  match.
- Long-running exports may take tens of seconds for large result sets.
