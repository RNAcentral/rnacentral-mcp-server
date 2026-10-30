# Harmonising a miRNA panel

**Paper:** Kotsiou O. S. *et al.* "Prioritizing extracellular miRNA candidates in asthma:
transparent in silico integration, literature-based concordance, and mechanistic network
analysis." *Frontiers in Allergy* (2026).
[PMC13485710](https://pmc.ncbi.nlm.nih.gov/articles/PMC13485710/),
doi:[10.3389/falgy.2026.1856862](https://doi.org/10.3389/falgy.2026.1856862).

## The workflow in the paper

The authors integrate several resources (RNADisease, miEAA, miRPathDB, miRDB, Reactome)
to prioritise extracellular miRNAs in asthma. A candidate counts as *formally concordant*
with a published study only if it matches an **exact mature-arm identifier**, harmonised to
miRBase v22.1 nomenclature. Opposite arms, arm-unspecified names and different family
members are not treated as equivalent.

That gave six formally concordant candidates: hsa-miR-126-3p, -146a-5p, -223-3p, -191-5p,
-125b-5p and -122-5p. Other studies reported names such as miR-124, miR-125b, miR-133b,
miR-130a, miR-155 and miR-221 without a -3p/-5p arm, so those were kept only as context.

## What the server can reproduce

Checking that each name resolves to one specific mature miRNA, and finding what an
ambiguous name could mean. The disease-database integration, target prediction and pathway
statistics are out of scope.

## Walkthrough

**Prompt**

> Map these six human miRNAs to RNAcentral and miRBase accessions: hsa-miR-126-3p,
> hsa-miR-146a-5p, hsa-miR-223-3p, hsa-miR-191-5p, hsa-miR-125b-5p, hsa-miR-122-5p. Then
> tell me what "hsa-miR-124" refers to.

**1. Exact-arm names** — `map_rna_id(name, taxon="Homo sapiens")` for each:

| Name | RNAcentral ID | miRBase mature |
| --- | --- | --- |
| hsa-miR-126-3p | URS00001F1DA8_9606 | MIMAT0000445 |
| hsa-miR-146a-5p | URS000050B527_9606 | MIMAT0000449 |
| hsa-miR-223-3p | URS00000B7E30_9606 | MIMAT0000280 |
| hsa-miR-191-5p | URS00005C2E31_9606 | MIMAT0000440 |
| hsa-miR-125b-5p | URS0000209905_9606 | MIMAT0000423 |
| hsa-miR-122-5p | URS00003380CC_9606 | MIMAT0000421 |

All six resolve to exactly one entry each. The entry also lists RefSeq, TarBase, MirGeneDB
and gene-level IDs. For example, hsa-miR-125b-5p maps to both MIR125B1 and MIR125B2,
because two loci produce the identical mature sequence.

**2. An arm-unspecified name** — `map_rna_id("hsa-miR-124", taxon="Homo sapiens")`

```
No RNAcentral entry found for external ID: hsa-miR-124
```

That is the behaviour the paper's rule calls for: the name is ambiguous, so it does not
silently map. To see what it could mean, search:

`query_rnacentral(query="hsa-miR-124", rna_type="miRNA", taxon="Homo sapiens", expert_db="miRBase")`

```
### 1. URS00000ADB79_9606  hsa-miR-124-3p  miRNA  22 nt  (2D structure available)
### 2. URS00003AA409_9606  hsa-miR-124-5p  miRNA  22 nt
```

Two different mature miRNAs. Without the arm you cannot tell which one a study measured.
Only `hsa-miR-124` was tested here; the other arm-unspecified names are likely to behave
the same way but were not run.

**3. Context** — `get_rna_description("hsa-mir-126")` returns an AI-generated literature
summary, flagged as such. It cites studies on down-regulation in lung cancer and on qPCR
primers, and nothing about asthma. Treat it as a pointer into the literature, not as
evidence for a specific disease.

## Takeaways

- `map_rna_id` enforces the arm-level strictness the paper adopts: exact names resolve,
  ambiguous ones do not.
- `query_rnacentral` shows the candidates behind an ambiguous name.
- The paper reports that hsa-miR-126-3p was one of four candidates it could not map to
  MIR:MIRDB target sets. That was a limitation of that particular resource; here the
  same name resolves cleanly.
