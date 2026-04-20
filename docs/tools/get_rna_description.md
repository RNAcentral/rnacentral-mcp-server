# `get_rna_description`

Return a literature-derived summary of an RNA's known biological role. The
summary comes from RNAcentral's literature-summary pipeline, which aggregates
published mentions of the RNA into a short natural-language description.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `rna_id` | `str` | yes | An RNA identifier recognised by RNAcentral (e.g. `"mmu-mir-191"`, a miRBase name, or a URS ID). |

## Returns

A plain-text description. If no summary is available for the given ID, the tool
returns a message indicating so rather than raising.

## Good to know

- Summaries exist primarily for well-studied RNAs (miRNAs, lncRNAs with named
  entries, etc.). Novel or poorly-annotated RNAs often have no summary.
- The summary is generated from the literature — treat it as a pointer to
  primary sources, not as a definitive statement.
