import logging

from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from helpers.query_text import clean_search_query

logger = logging.getLogger(MAIN_LOGGER_NAME)


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_datasets(query: str, page: int = 1, page_size: int = 20) -> str:
        """
        Search for datasets on data.gouv.fr by keywords.

        This is typically the first step in exploring data.gouv.fr.
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Typical workflow: search_datasets → list_dataset_resources → query_resource_data.
        """
        # Clean the query to remove generic stop words that break AND-based searches
        cleaned_query = clean_search_query(query)

        # Try with cleaned query first
        result = await datagouv_api_client.search_datasets(
            query=cleaned_query, page=page, page_size=page_size
        )

        # Format the result as text content
        datasets = result.get("data", [])

        # Fallback: if cleaned query returns no results and it differs from original,
        # try with the original query
        if not datasets and cleaned_query != query:
            logger.debug(
                "No results with cleaned query '%s', trying original query '%s'",
                cleaned_query,
                query,
            )
            result = await datagouv_api_client.search_datasets(
                query=query, page=page, page_size=page_size
            )
            datasets = result.get("data", [])

        if not datasets:
            return f"No datasets found for query: '{query}'"

        content_parts = [
            f"Found {result.get('total', len(datasets))} dataset(s) for query: '{query}'",
            f"Page {result.get('page', 1)} of results:\n",
        ]
        for i, ds in enumerate(datasets, 1):
            content_parts.append(f"{i}. {ds.get('title', 'Untitled')}")
            content_parts.append(f"   ID: {ds.get('id')}")
            if ds.get("description_short"):
                desc = ds.get("description_short", "")[:200]
                content_parts.append(f"   Description: {desc}...")
            if ds.get("organization"):
                content_parts.append(f"   Organization: {ds.get('organization')}")
            if ds.get("tags"):
                tags = ", ".join(ds.get("tags", [])[:5])
                content_parts.append(f"   Tags: {tags}")
            content_parts.append(f"   Resources: {ds.get('resources_count', 0)}")
            content_parts.append(f"   URL: {ds.get('url')}")
            content_parts.append("")

        return "\n".join(content_parts)
