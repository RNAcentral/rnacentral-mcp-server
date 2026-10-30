# Examples

Four worked examples, each anchored to a recent open-access paper whose workflow can be
partly reproduced with this server. Every tool call and output below was run against the
live server on 2026-10-19; outputs are trimmed where noted, and results will drift as
RNAcentral releases new data.

Each page says plainly which steps of the paper the tools can reproduce, which they cannot
(statistics, eQTL analysis, wet-lab work), and where a tool returned nothing useful.

```{toctree}
:maxdepth: 1

gwas-locus-ncrnas
ml-training-set
mirna-id-harmonisation
unknown-sequence-triage
```

| Example | Paper | Tools used |
| --- | --- | --- |
| [From a GWAS locus to candidate ncRNAs](gwas-locus-ncrnas.md) | Farashi *et al.*, *Nat Commun* 2025 | `get_overlapping_ncrnas`, `query_rnacentral`, `map_rna_id` |
| [Building an ncRNA training set](ml-training-set.md) | Penić *et al.* (RiNALMo), *Nat Commun* 2025 | `export_sequences` |
| [Harmonising a miRNA panel](mirna-id-harmonisation.md) | Kotsiou *et al.*, *Front Allergy* 2026 | `map_rna_id`, `query_rnacentral`, `get_rna_description` |
| [Triage of an unknown sequence](unknown-sequence-triage.md) | Narunsky *et al.*, *NAR* 2024 | `search_sequence`, `get_sequence_search_results`, `map_rna_id`, `get_secondary_structure_svg` |
