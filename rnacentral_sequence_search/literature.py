import aiohttp
import logging

logger = logging.getLogger('rna_search')

async def fetch_rna_description(rna_id: str) -> str:
    """Core logic for getting a literature summary description of an RNA sequence."""
    try:
        url = f"https://rnacentral.org/api/v1/litsumm/{rna_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                logger.debug(f"Request URL: {url}")
                response.raise_for_status()
                data = await response.json()
                return data.get("summary", "No description available")
    except Exception as e:
        logger.error(f"Error in fetch_rna_description: {e}")
        return f"Error querying RNAcentral API: {str(e)}"
