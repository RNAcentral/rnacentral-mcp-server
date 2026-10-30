# Triage of an unknown sequence

**Paper:** Narunsky A. *et al.* "The discovery of novel noncoding RNAs in 50 bacterial
genomes." *Nucleic Acids Research* (2024).
[PMC11109978](https://pmc.ncbi.nlm.nih.gov/articles/PMC11109978/),
doi:[10.1093/nar/gkae248](https://doi.org/10.1093/nar/gkae248).

## The workflow in the paper

A pipeline sorts intergenic regions (IGRs) by length and GC content, removes any that
contain a known protein-coding region (BLASTX), then examines the remaining long, GC-rich
IGRs for sequence and structural similarity to other genomes (Infernal against RefSeq).
Across 50 genomes it found more than 4,700 candidate IGRs, which yielded 44 novel riboswitch
candidates and other putative ncRNA motifs.

## What the server can reproduce

The paper's *candidates* are novel, so by design they have no good match in RNAcentral,
and the paper does not publish them as sequences in its text. What the server can do is the
triage step: **is this region already a known ncRNA, or genuinely new?** A strong hit says
"known, skip it"; no hit supports "worth a closer look".

To demonstrate that, this example uses a **positive control**: the *E. coli* 6S RNA
(URS00002F163A, 183 nt) with 8 transition mutations added, to stand in for the same RNA in
a newly sequenced relative. It is not a sequence from the paper.

```
AUUUCUCUGAAAUGUUCGCAAGCGGGCCGGUCCCCUGAGCCGAUAUUCCAUACCACAAGAAUGUGGUGCUCCGCGGUUGGUGAGCGUGCUCGGUCCGUCCGAGAGGCCUUAAAACUGCGACGAUACAUUCACCUUGAACCAAAGGUUCAAGGGUUACAGCCUGCGGCGGCAUCUCGGAGAUUC
```

## Walkthrough

**Prompt**

> I have this 183-nt intergenic sequence from a new Enterobacterales genome. Is it a known
> ncRNA?

**1. Submit** — `search_sequence(sequence=...)` returns immediately; the search runs in the
background and can take minutes to hours under load:

```
Search job submitted. Job ID: `1fe4d7e4-5b98-4fff-bbd7-e062129e8dd4`
The search runs in the background and may take minutes to hours. Poll
`get_sequence_search_results` with this job ID until it reports the job is finished.
```

**2. Poll** — `get_sequence_search_results(job_id)`, repeated. In this run:

```
  0 s | pending: 0% complete (0/146 databases). Still running; check again later.
 40 s | pending: 45% complete
 60 s | running: 98% complete (136/146 databases).
 85 s | finished, but returned no hits yet ...
105 s | # RNAcentral Search Results — Found 23440 potential matches.
```

The service marks a job `finished` about 20 seconds before the hits can be read, so one
more check is sometimes needed. The tool says so rather than reporting "no matches".
Under load, expect the first phase to be much longer.

**3. Results**

```
Found 23440 potential matches.
1. URS00022C20C3_562   Score 169.0  E-value 9.5e-47  Identity 96.2%  Query coverage 100.0%
2. URS0001EE1A0E_562   Score 168.7  E-value 1.2e-46  Identity 96.2%  Query coverage 100.0%
3. URS0001EE1A0E_624   Score 168.7  E-value 1.2e-46  Identity 96.2%  Query coverage 100.0%
4. URS00022DC518_562   Score 168.6  E-value 1.3e-46  Identity 96.2%  Query coverage 100.0%
5. URS000304B653_562   Score 168.6  E-value 1.3e-46  Identity 96.2%  Query coverage 100.0%
```

High identity over the full query length, with E-values around 1e-46, means this is a
known ncRNA. The taxon IDs (562 *E. coli*, 624 *Shigella sonnei*) show it is conserved across
relatives. The top hits have no description in the service's response, so identify them
through their cross-references.

**4. Follow up**

- `map_rna_id("URS00022C20C3_562")` lists nine ENA contig locations for the same 184-nt
  sequence, but no named gene or canonical ID.
- `get_secondary_structure_svg("URS00002F163A")` returns the 2D diagram of the original
  *E. coli* 6S RNA (the control's source).
- `get_rna_description` returns a 404 for these entries: no literature summary exists.

Naming the hit as "6S RNA" came from the source entry's description in `query_rnacentral`,
not from the search result.

## Caveats

- The service searched 146 databases and reported 5 as failed; the job still finished.
- Keep the job ID and resume polling rather than resubmitting; every submission starts a
  new job on the shared service.
- Do not fetch results straight from the service API while a job is still running. In
  testing, jobs polled that way stayed empty even after they finished. The tool only
  reads results once the job reports `finished`.
