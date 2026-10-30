# From a GWAS locus to candidate ncRNAs

**Paper:** Farashi S. *et al.* "HTRA1/lncRNA HTRA1-AS1 dominates in age-related macular
degeneration reticular pseudodrusen genetic risk with no complement involvement."
*Nature Communications* (2025). [PMC12685958](https://pmc.ncbi.nlm.nih.gov/articles/PMC12685958/),
doi:[10.1038/s41467-025-65903-9](https://doi.org/10.1038/s41467-025-65903-9).

## The workflow in the paper

A GWAS of reticular pseudodrusen (RPD) found one genome-wide significant region on
chromosome 10 (lead SNP rs11200638, the ARMS2/HTRA1 locus). Besides the two protein-coding
genes, the region contains a long non-coding RNA, *HTRA1-AS1* (also called BX842242.1,
ENSG00000285955). The authors then show it has a strong retinal eQTL signal and colocalises
with retinal thickness markers.

The question this example answers: *given the risk locus, which non-coding RNAs sit in it,
and what do we know about the interesting one?*

## What the server can reproduce

| Paper step | Tool |
| --- | --- |
| List ncRNAs in the risk region | `get_overlapping_ncrnas` |
| Find and identify the lncRNA of interest | `query_rnacentral` |
| Cross-reference its Ensembl IDs | `map_rna_id` |
| Literature and structure check | `get_rna_description`, `get_secondary_structure_svg` |

Not reproducible here: the GWAS itself, eQTL and colocalisation analysis, and
whole-genome sequencing of extreme phenotypes.

## Walkthrough

**Prompt**

> The lead SNP for a retinal GWAS sits at the HTRA1 locus. Which non-coding RNAs overlap
> HTRA1 in human, and is there a lncRNA called HTRA1-AS1 I should look at?

**1. Overlapping ncRNAs** — `get_overlapping_ncrnas(species="human", gene_symbol="HTRA1")`

```
# Overlapping ncRNAs in Homo sapiens
**Region**: `10:122458551-122516001`
**Gene Symbol**: `HTRA1`

Found **80** overlapping ncRNAs.
...
### 2. URS0000EA3140_9606   10/122473853-122474755,122494695-122495029:-   HSALNT0169283   lncRNA
### 3. URS00019DB5CC_9606   10/122458640-122458666,122458918-122459440:-   LNC_000572       lncRNA
### 9. URS00034DC4BC_9606   10/122510153-122510488:+   ENSG00000166033.13 circular RNA   circRNA
...
*Showing first 15 of 80 results.*
```

The gene symbol is resolved to coordinates through Ensembl. The 15 shown are a mix of
piRNAs, lncRNAs from lncRNA catalogues and circRNAs. *HTRA1-AS1* is not among those 15,
because the output is truncated, so name it directly in the next step.

```{note}
The region returned is on GRCh38. The variant position quoted in the paper
(`10:124227624`, rs60401382) is about 1.77 Mb higher, which suggests GRCh37. Convert
coordinates before passing them to `get_overlapping_ncrnas` as a range.
```

**2. Find the lncRNA** — `query_rnacentral(query="HTRA1-AS1", taxon="Homo sapiens", rna_type="lncRNA", limit=5)`

```
### 1. URS00034223F8_9606  HTRA1 and ARMS2 antisense RNA 1 (HTRA1-AS1)  lncRNA  4755 nt  HGNC, RefSeq
### 2. URS0002A66FBE_9606  HTRA1 and ARMS2 antisense RNA 1               lncRNA   837 nt  Ensembl/GENCODE, Expression Atlas, GeneCards, Ensembl
### 3. URS0002A1F31B_9606  HTRA1 and ARMS2 antisense RNA 1               lncRNA   761 nt  Ensembl/GENCODE, ...
### 4. URS0000DB9660_9606  HTRA1 and ARMS2 antisense RNA 1               lncRNA   566 nt  GeneCards, Ensembl, Expression Atlas, ENA, LncBook, ...
```

RNAcentral holds several distinct sequences for the one gene: the HGNC/RefSeq entry is
4,755 nt, while the Ensembl transcripts are 566–837 nt. Which isoform a paper means
matters, so check lengths against the paper.

**3. Map the Ensembl IDs** — `map_rna_id`

The paper's gene ID does not map directly:

```
map_rna_id("ENSG00000285955", taxon="Homo sapiens")
-> No RNAcentral entry found for external ID: ENSG00000285955
```

RNAcentral appears to index Ensembl *transcripts* rather than genes, so use the transcript ID, or the URS from step 2:

```
map_rna_id("ENST00000811415", taxon="Homo sapiens")
-> Primary ID: URS0002A66FBE_9606     Canonical ID: Ensembl: ENSG00000285955.2
   Ensembl: ENST00000811415(.1)   Expression Atlas: ENSG00000285955
```

**4. Literature and structure** — `get_rna_description("URS0002A66FBE")` and
`get_secondary_structure_svg("URS0002A66FBE")` both returned a 404: RNAcentral has no
literature summary and no 2D structure for this entry. This is common for lncRNAs. Say so
rather than guessing, and read the paper for the functional evidence.

## Takeaways

- The tools get you from a locus to named, cross-referenced candidates quickly.
- Gene-level IDs (ENSG) may need converting to transcript IDs or URS IDs first.
- Check the genome assembly before using coordinates from a paper.
