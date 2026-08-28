import os
import re

from crewai.tools import tool
from firecrawl import FirecrawlApp, ScrapeOptions


DEFAULT_SEARCH_LIMIT = 15


class WebSearchError(RuntimeError):
    pass


def clean_search_markdown(markdown: str) -> str:
    """Preserve links/URLs; collapse 2+ consecutive newlines to one."""
    cleaned = re.sub(r"\n{2,}", "\n", markdown)
    return cleaned.strip()


def search_web(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise WebSearchError("FIRECRAWL_API_KEY is not set")

    app = FirecrawlApp(api_key=api_key)
    response = app.search(
        query=query,
        limit=limit,
        scrape_options=ScrapeOptions(formats=["markdown"]),
    )

    if not response.success:
        detail = getattr(response, "error", None) or "unknown error"
        raise WebSearchError(f"Firecrawl search failed: {detail}")

    cleaned_chunks: list[dict] = []
    for result in response.data or []:
        cleaned_chunks.append(
            {
                "title": result["title"],
                "url": result["url"],
                "markdown": clean_search_markdown(result["markdown"]),
            }
        )
    return cleaned_chunks


@tool
def web_search_tool(query: str):
    """
    Web Search Tool.
    Args:
        query: str
            The query to search the web for.
    Returns
        A list of search results with the website content in Markdown format.
    """
    return search_web(query)
