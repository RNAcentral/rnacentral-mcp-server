import aiohttp
import logging
from typing import Optional
from rnacentral_sequence_search.utils import resolve_taxid

logger = logging.getLogger('rna_search')

async def fetch_rna_mapping(identifier: str, taxon: Optional[str] = None) -> str:
    """Core logic for bidirectional ID mapping for RNA sequences."""
    async with aiohttp.ClientSession() as session:
        # Normalize identifier
        identifier = identifier.strip()
        urs = identifier.split('_')[0] if identifier.upper().startswith("URS") else None
        
        # 1. If not a URS, try to find the URS from external ID
        if not urs:
            url = f"https://rnacentral.org/api/v1/rna/?external_id={identifier}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        urs = results[0].get("rnacentral_id")
                    else:
                        return f"No RNAcentral entry found for external ID: {identifier}"
                else:
                    return f"Error looking up external ID {identifier}: HTTP {resp.status}"

        # 2. Determine Taxon ID
        taxon_id = await resolve_taxid(session, taxon)
        
        if not taxon_id:
            # If no taxon specified or resolved, try to find one from available xrefs
            xrefs_url = f"https://rnacentral.org/api/v1/rna/{urs}/xrefs"
            async with session.get(xrefs_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        # Prefer human (9606) or the first taxid found
                        human_xref = next((x for x in results if x.get("taxid") == 9606), None)
                        taxon_id = 9606 if human_xref else results[0].get("taxid")
        
        if not taxon_id:
            return f"Could not determine a valid Taxon ID for {urs}"

        # 3. Fetch all cross-references for this taxon
        current_url = f"https://rnacentral.org/api/v1/rna/{urs}/xrefs/{taxon_id}/"
        all_xrefs = []
        for _ in range(5): # Paginate through taxon-specific xrefs
            async with session.get(current_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    all_xrefs.extend(data.get("results", []))
                    current_url = data.get("next")
                    if not current_url: break
                else:
                    break
        
        if not all_xrefs:
            return f"No cross-references found for {urs} in taxon {taxon_id}"

        # 4. Filter and Group IDs
        primary_id = f"{urs}_{taxon_id}"
        db_priority = ["HGNC", "miRBase", "Ensembl", "Rfam", "NCBI Gene", "GtRNAdb", "NONCODE"]
        
        canonical_id = None
        secondary_ids = set()
        
        # Find canonical ID
        for db in db_priority:
            for xref in all_xrefs:
                if xref.get("database", "").lower() == db.lower():
                    acc = xref.get("accession", {})
                    cid = acc.get("optional_id") or acc.get("id")
                    if cid:
                        canonical_id = f"{db}: {cid}"
                        break
            if canonical_id:
                break
        
        # Collect all other unique IDs
        for xref in all_xrefs:
            db = xref.get("database")
            acc = xref.get("accession", {})
            
            for field in ["id", "external_id", "optional_id"]:
                val = acc.get(field)
                if val:
                    # Clean up DB prefix if present
                    clean_val = val
                    if ":" in val and val.lower().startswith(db.lower()):
                        parts = val.split(":", 1)
                        if len(parts) > 1:
                            clean_val = parts[1].strip()
                    secondary_ids.add(f"{db}: {clean_val}")

        # Remove canonical from secondary
        if canonical_id:
            secondary_ids.discard(canonical_id)
            cid_val = canonical_id.split(": ")[-1]
            secondary_ids = {sid for sid in secondary_ids if not sid.endswith(f": {cid_val}")}

        # 5. Format Output
        markdown = [f"# ID Mapping for {identifier}", ""]
        markdown.append(f"**Primary ID**: `{primary_id}`")
        if taxon_id:
            markdown.append(f"**NCBI Taxon ID**: `{taxon_id}`")
        if canonical_id:
            markdown.append(f"**Canonical ID**: `{canonical_id}`")
        
        if secondary_ids:
            markdown.append("\n**Secondary Identifiers**:")
            for sid in sorted(list(secondary_ids)):
                markdown.append(f"- {sid}")
        
        return "\n".join(markdown)
