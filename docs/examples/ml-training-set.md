# Building an ncRNA training set

**Paper:** Penić R. J. *et al.* "RiNALMo: general-purpose RNA language models can
generalize well on structure prediction tasks." *Nature Communications* (2025).
[PMC12219582](https://pmc.ncbi.nlm.nih.gov/articles/PMC12219582/),
doi:[10.1038/s41467-025-60872-5](https://doi.org/10.1038/s41467-025-60872-5).

## The workflow in the paper

RiNALMo is a 650M-parameter RNA language model pre-trained on about 36 million ncRNA
sequences. In the Methods ("Data preprocessing") the authors:

1. collected non-coding RNA sequences from RNAcentral, nt, Rfam and Ensembl;
2. removed sequences shorter than 16 or longer than 8192 nucleotides;
3. removed exact duplicates with `seqkit rmdup`;
4. clustered the rest with `mmseqs easy-linclust --min-seq-id 0.7 -c 0.8`.

## What the server can reproduce

Step 1 (for the RNAcentral part) and step 2: `export_sequences` filters by RNA type, taxon,
source database, length and presence of a secondary structure. The paper's full corpus is
far larger than a sensible single export, so this example builds a small, scoped version.
Deduplication and clustering happen locally afterwards.

## Walkthrough

**Prompt**

> Export all human tRNAs that have a known secondary structure, between 16 and 8192 nt, as
> Parquet so I can load them in pandas.

**1. Export** — `export_sequences(query="tRNA", rna_type="tRNA", taxon="Homo sapiens", has_secondary_structure=True, min_length=16, max_length=8192, format="parquet")`

```
# Bulk Sequence Export
Job `ac7ebfd6-b857-4878-a707-ce0b2c04f16b` completed.
### [Download Results](https://export.rnacentral.org/download/ac7ebfd6-b857-4878-a707-ce0b2c04f16b/parquet)
```

**2. Inspect it locally**

```python
import pandas as pd
d = pd.read_parquet("tRNA_human.parquet")
print(d.shape)                      # (3408, 8)
print(list(d.columns))
# ['rnacentral_id', 'taxid', 'description', 'rna_type', 'so_rna_type',
#  'databases', 'secondary_structure', 'sequence']
print(d.sequence.str.len().agg(["min", "max"]).tolist())   # [46, 96]
print(d.taxid.value_counts().head(3).to_dict())
# {9606: 3268, 63221: 65, 2845822: 43}
print(d.sequence.nunique())         # 3342
```

What this shows:

- Each row carries the sequence **and** a dot-bracket `secondary_structure`
  (for example `(((((((..((((.....)))).(((((.......)))))....` ), which is what a
  structure-prediction training set needs.
- A taxon of "Homo sapiens" includes sub-taxa: 65 rows are Neanderthal (taxid 63221).
  Filter on `taxid == 9606` if you want modern humans only.
- 3,408 rows hold only 3,342 distinct sequences, so the paper's deduplication step does real
  work even on this small set.
- Sequences use the DNA alphabet (`T`, not `U`). Convert with `str.replace("T", "U")` if
  your model expects RNA.

**3. Deduplicate and cluster as in the paper** (commands from the paper's Methods; not run
for this example)

```bash
seqkit rmdup -s tRNA_human.fasta > unique.fasta
mmseqs easy-linclust unique.fasta clusters tmp --min-seq-id 0.7 -c 0.8
```

## Caveats

- **FASTA export currently fails for this query.** The same request with `format="fasta"`
  failed four times (with and without the length and structure filters) with an
  `esl-sfetch ... returned non-zero exit status` error from the export service. A small
  FASTA export (`hsa-mir-126`) worked. Use Parquet for this kind of query for now.
- Each export is one job on a shared service. Exporting the paper's full 36M-sequence corpus
  this way is not realistic; scope to a type, taxon or source database.
