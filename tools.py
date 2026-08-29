import os
import re

from crewai.tools import tool
from firecrawl import FirecrawlApp, ScrapeOptions


# Tight limits: Indeed listing pages + repeated tool calls blow 128k context.
DEFAULT_SEARCH_LIMIT = 5
MAX_MARKDOWN_CHARS = 1_500
MAX_TOOL_CALLS_HINT = 2


class WebSearchError(RuntimeError):
    pass


def clean_search_markdown(
    markdown: str,
    max_chars: int = MAX_MARKDOWN_CHARS,
) -> str:
    """Preserve links/URLs; collapse blank lines; truncate for LLM context."""
    cleaned = re.sub(r"\n{2,}", "\n", markdown).strip()
    if max_chars > 0 and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "\n…[truncated]"
    return cleaned


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
                "markdown": clean_search_markdown(result.get("markdown") or ""),
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
        A list of search results with truncated website content in Markdown format.
    """
    return search_web(query)
