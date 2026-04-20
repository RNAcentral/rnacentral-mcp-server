# `query_rnacentral`

Text and metadata search over RNAcentral. Combines the EBI Search backend (for fast
filtered lookup) with the RNAcentral REST API (for enriched per-hit metadata such as
Rfam hits, GO annotations, and whether a 2D structure is available).

Use this when you have a name, keyword, or accession and want to find matching RNAs.
Use {doc}`search_sequence` instead if you have a raw nucleotide sequence.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | `str` | yes | Free-text search term (e.g. `"telomerase"`, `"hsa-mir-126"`, `"HOTAIR"`). |
| `rna_type` | `str` | no | Restrict to an RNA type — e.g. `"miRNA"`, `"lncRNA"`, `"tRNA"`, `"rRNA"`, `"snoRNA"`. |
| `taxon` | `str` | no | Scientific name (preferred) or NCBI Taxonomy ID — e.g. `"Homo sapiens"` or `"9606"`. |
| `expert_db` | `str` | no | Source database filter — e.g. `"miRBase"`, `"GENCODE"`, `"Ensembl"`, `"Rfam"`. |
| `has_secondary_structure` | `bool` | no | If `true`, only return RNAs that have a 2D structure available. |
| `limit` | `int` | no | Number of hits to return (1–20, default 10). |

## Returns

A markdown-formatted summary, one entry per hit, including the URS ID, description,
RNA type, organism, length, source databases, and any Rfam/GO metadata that could be
fetched.

## Upstream services

- EBI Search (`ebisearch.ebi.ac.uk`) for the filtered text query.
- RNAcentral REST API (`rnacentral.org/api/v1`) for per-hit enrichment.
