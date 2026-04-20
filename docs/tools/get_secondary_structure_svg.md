# `get_secondary_structure_svg`

Return the 2D secondary-structure diagram for a given URS ID as SVG. The SVG comes
from RNAcentral's structure service (R2DT or curated layouts, depending on the
entry) and can be rendered directly by MCP clients that support image content.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `urs_id` | `str` | yes | The RNAcentral URS ID (e.g. `"URS0000049E57"`). The taxon suffix (`_9606`) is optional. |

## Returns

The SVG document as a string. If the entry has no 2D structure available, the
tool returns an explanatory message rather than raising.

## Tips

- Not every RNAcentral entry has a 2D structure. Pre-filter with
  `query_rnacentral(..., has_secondary_structure=True)` if you need to guarantee
  a hit.
- Large or complex structures produce large SVGs — clients that inline the
  payload in the chat transcript may truncate it.
