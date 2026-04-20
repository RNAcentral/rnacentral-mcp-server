# `get_overlapping_ncrnas`

Find non-coding RNAs that overlap a genomic region. The region can be specified
either as explicit coordinates or as a gene symbol, in which case the tool uses
Ensembl's GraphQL API to resolve the symbol to coordinates first.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `species` | `str` | yes | Common name (e.g. `"human"`, `"mouse"`) or scientific name (`"homo_sapiens"`). |
| `chromosome` | `str` | conditional | Chromosome name — `"1"`, `"X"`, `"chr1"`. |
| `start` | `int` | conditional | Start coordinate (1-based, inclusive). |
| `end` | `int` | conditional | End coordinate (1-based, inclusive). |
| `gene_symbol` | `str` | conditional | Gene symbol (e.g. `"BRCA2"`, `"HOTAIR"`). |

You must supply **either** `gene_symbol` **or** the full `chromosome` / `start` /
`end` triple. Mixing the two is not supported; the tool returns an error if
neither is given.

## Returns

A markdown list of overlapping RNAcentral entries with URS IDs, RNA type,
genomic coordinates, strand, and source database.

## Upstream services

- Ensembl GraphQL API for `gene_symbol` → coordinates resolution.
- RNAcentral REST API for the overlap query.
