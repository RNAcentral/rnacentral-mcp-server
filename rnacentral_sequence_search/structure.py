import aiohttp
import base64
import logging
from mcp.types import ImageContent, TextContent, CallToolResult

logger = logging.getLogger('rna_search')

async def fetch_secondary_structure_svg(urs_id: str) -> CallToolResult:
    """
    Fetch the secondary structure SVG for a given RNAcentral URS ID.
    """
    # Canonicalize URS ID (e.g. URS0000759B6D_9606 -> URS0000759B6D)
    urs_base = urs_id.split('_')[0].upper()
    url = f"https://rnacentral.org/api/v1/rna/{urs_base}/2d/svg/"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Error: Could not find secondary structure for {urs_id}. (Status {response.status})")],
                        isError=True
                    )
                
                svg_data = await response.text()
                
                # Check if it's actually an SVG (sometimes it might return an empty or error response)
                if not svg_data or "<svg" not in svg_data:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"No secondary structure diagram available for {urs_id}.")],
                        isError=False
                    )

                # Base64 encode for the image content
                base64_svg = base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
                
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text", 
                            text=f"Secondary structure diagram for {urs_id}:\n\n{svg_data}"
                        ),
                        ImageContent(
                            type="image",
                            data=base64_svg,
                            mimeType="image/svg+xml"
                        )
                    ]
                )
        except Exception as e:
            logger.error(f"Error fetching SVG for {urs_id}: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"An error occurred while fetching the structure: {str(e)}")],
                isError=True
            )
