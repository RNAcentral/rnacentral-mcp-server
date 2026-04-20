# `map_rna_id`

Bidirectional mapping between RNAcentral URS IDs and external database identifiers.
Accepts either direction and returns the full set of cross-references that
RNAcentral holds for the entry.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `identifier` | `str` | yes | A URS ID (`"URS0000759B6D"`) **or** an external accession (`"MIMAT0000062"`, `"ENSG00000228630"`, `"HGNC:31023"`, ...). |
| `taxon` | `str` | no | Scientific name (preferred) or NCBI Taxonomy ID. Required to disambiguate when an external ID is shared across organisms. |

## Returns

A markdown summary listing the canonical URS ID, the organism, and every known
cross-reference grouped by source database.

## Examples

- `identifier="MIMAT0000062", taxon="Homo sapiens"` — map a miRBase mature miRNA
  accession to its URS ID and all other xrefs.
- `identifier="URS0000759B6D"` — list every external ID that points at this URS.
