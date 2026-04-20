# `search_sequence`

Similarity search by raw RNA sequence. Submits the sequence to the RNAcentral
sequence-search service, polls for completion, and returns the top hits across the
member databases.

Use this when you have a nucleotide sequence and want to know what it matches in
RNAcentral. If you already have an accession or a name, use {doc}`query_rnacentral`.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `sequence` | `str` | yes | The RNA (or DNA) sequence to search. Case-insensitive; whitespace is ignored. |
| `databases` | `list[str]` | no | Restrict the search to specific member databases. Defaults to all. |

## Returns

A markdown summary of the hits: accession, description, organism, E-value/identity,
and the source database.

## Notes

- The upstream service is asynchronous — the tool submits a job and polls until
  results are ready or a timeout is hit. Expect a few seconds of latency on a cold
  cache.
- Very long sequences or highly repetitive sequences may be rejected by the
  upstream service; the tool surfaces the error message verbatim.
