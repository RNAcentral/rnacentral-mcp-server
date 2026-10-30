# `search_sequence`

Similarity search by raw RNA sequence. Submits the sequence to the RNAcentral
sequence-search service as a background job and returns a job ID immediately. Fetch the
hits with {doc}`get_sequence_search_results`.

Use this when you have a nucleotide sequence and want to know what it matches in
RNAcentral. If you already have an accession or a name, use {doc}`query_rnacentral`.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `sequence` | `str` | yes | The RNA (or DNA) sequence to search. Case-insensitive; whitespace is ignored. |
| `databases` | `list[str]` | no | Restrict the search to specific member databases. Defaults to all. |

## Returns

A job ID, with an instruction to poll {doc}`get_sequence_search_results`. The search
itself runs on the service and can take from about two minutes to hours under load.

## Notes

- The tool does not wait for the search. Poll `get_sequence_search_results` with the job
  ID until it reports results.
- Sequences must be 10–7000 nucleotides. RNA (`U`) and DNA (`T`) alphabets are both
  accepted.
- Very long or highly repetitive sequences may be rejected by the upstream service; the
  tool surfaces the HTTP status.
