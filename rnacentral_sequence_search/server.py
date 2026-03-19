#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import os
from typing import List, Optional
import aiohttp.web
import click
from mcp.server.fastmcp import FastMCP, Context

import logging

logger = logging.getLogger('rna_search')

# Initialize the MCP server
mcp = FastMCP("RNAcentral Sequence Search", dependencies=["aiohttp", "mcp"])

# Base URL for the RNAcentral API
RNA_CENTRAL_SERVER = "https://search.rnacentral.org/"


@mcp.tool()
async def get_rna_description(rna_id: str) -> str:
    """
    Get a literature summary description of an RNA sequence from RNAcentral.
    
    Args:
        rna_id: The ID of the RNA (e.g., "mmu-mir-191")
    
    Returns:
        A textual description of the RNA sequence based on literature analysis.
    """
    try:
        # Format the API URL
        url = f"https://rnacentral.org/api/v1/litsumm/{rna_id}"
        
        # Make the API request
        async with aiohttp.ClientSession() as session:
            response = await session.get(url)
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Response status: {response.status}")
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Parse the response
            data = await response.json()
            # Check if description is available
            return data.get("summary", "No description available")
            
    
    except aiohttp.web.HTTPException as e:
        logger.error(f"HTTP error: {e}")
        if e.response.status_code == 404:
            return f"RNA ID '{rna_id}' not found in RNAcentral database."
        else:
            return f"Error querying RNAcentral API: HTTP {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error querying RNAcentral API: {str(e)}"

@mcp.tool()
async def search_sequence(
    sequence: str,
    databases: Optional[List[str]] = None,
) -> str:
    """
    Search the RNAcentral database for a given RNA sequence.
    
    Args:
        sequence: The RNA sequence to search for
        databases: Optional list of specific databases to search within (default: all databases)

    Returns:
        A markdown formatted summary of search results
    """
    logging.error("starting?")
    
    # Default to empty list for searching all databases
    if databases is None:
        databases = []
    
    # Format data for API call
    data = {"databases": databases, "query": str(sequence)}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{RNA_CENTRAL_SERVER}api/submit-job", json=data) as response:
            if response.status != 201:
                error_text = await response.text()
                return f"Error submitting search job: {response.status} - {error_text}"
            
            job_data = await response.json()
            job_id = job_data.get("job_id")
            
            if not job_id:
                return "Error: No job ID returned from RNAcentral"
        
        # Poll for job status      
        status = ""
        attempts = 0
        max_attempts = 30  # Maximum number of polling attempts
        
        while attempts < max_attempts:
            attempts += 1
            
            async with session.get(f"{RNA_CENTRAL_SERVER}api/job-status/{job_id}") as response:
                if response.status != 200:
                    return f"Error checking job status: {response.status}"
                
                status_data = await response.json()
                status = status_data.get("status", "")
                
                if status in ["success", "partial_success"]:
                    break
                elif status == "failed":
                    return "Search job failed. Please try again with a different sequence."
                
                # Wait before polling again
                await asyncio.sleep(100)
        
        if status not in ["success", "partial_success"]:
            return "Search timed out. Please try a shorter sequence or try again later."
        
        async with session.get(f"{RNA_CENTRAL_SERVER}api/job-result/{job_id}") as response:
            if response.status != 200:
                return f"Error retrieving results: {response.status}"
            
            results = await response.json()
            
        # Process and format results
        report = format_results(results, job_id, sequence)
        return report 


def format_results(results, job_id, sequence):
    """Format search results as markdown"""
    hits = results#.get("hits", [])
    num_hits = len(hits)
    
    if num_hits == 0:
        return f"No matches found for the provided sequence: '{sequence[:30]}...'"
    
    # Prepare markdown output
    markdown = [
        f"# RNAcentral Search Results",
        f"Found **{num_hits}** potential matches for your sequence.",
        f"",
        f"## Top Hits"
    ]
    
    # Process top 5 hits (or fewer if less than 5 results)
    for i, hit in enumerate(hits[:5]):
        rnacentral_id = hit.get("rnacentral_id", "Unknown")
        description = hit.get("description", "No description available")
        score = hit.get("score", "N/A")
        
        markdown.append(f"### {i+1}. {description}")
        markdown.append(f"**RNAcentral ID**: [{rnacentral_id}](https://rnacentral.org/rna/{rnacentral_id})")
        markdown.append(f"**Score**: {score}")
        markdown.append("")
    
    # Add link to full results
    markdown.append(f"## View Complete Results")
    markdown.append(f"View the full results at: [RNAcentral Search Results]({RNA_CENTRAL_SERVER}?jobid={job_id})")
    print("\n".join(markdown))
    return "\n".join(markdown)

@click.command()
@click.option('--log-dir', type=click.Path(file_okay=False, dir_okay=True, writable=True), help="Directory to store log files.")
def main(log_dir: Optional[str]):
    """
    Main function to run the MCP server.
    """
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "rnacentral_mcp.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True
        )
    else:
        logging.basicConfig(level=logging.INFO, force=True)
    
    mcp.run()

# Run the server if executed directly
if __name__ == "__main__":
    main()
