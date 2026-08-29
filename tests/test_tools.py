from unittest.mock import MagicMock, patch

import pytest

from tools import (
    DEFAULT_SEARCH_LIMIT,
    MAX_MARKDOWN_CHARS,
    WebSearchError,
    clean_search_markdown,
    search_web,
)


def test_clean_search_markdown_preserves_urls():
    text = "Backend role at https://example.com/jobs/1 apply now"
    assert "https://example.com/jobs/1" in clean_search_markdown(text)


def test_clean_search_markdown_preserves_markdown_links():
    text = "See [job posting](https://example.com/jobs/2) for details"
    cleaned = clean_search_markdown(text)
    assert "https://example.com/jobs/2" in cleaned
    assert "[job posting]" in cleaned


def test_clean_search_markdown_collapses_excessive_newlines():
    text = "Line one\n\n\n\nLine two"
    assert clean_search_markdown(text) == "Line one\nLine two"


def test_clean_search_markdown_keeps_single_newlines():
    text = "Job A\nJob B\nJob C"
    assert clean_search_markdown(text) == text


def test_clean_search_markdown_truncates_long_content():
    text = "A" * (MAX_MARKDOWN_CHARS + 500)
    cleaned = clean_search_markdown(text)
    assert len(cleaned) <= MAX_MARKDOWN_CHARS + len("\n…[truncated]")
    assert cleaned.endswith("…[truncated]")


@patch("tools.FirecrawlApp")
def test_search_web_raises_on_failure(mock_app_cls):
    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app
    mock_app.search.return_value = MagicMock(success=False, error="rate limited")

    with pytest.raises(WebSearchError, match="Firecrawl search failed"):
        search_web("backend engineer Tokyo")


@patch("tools.FirecrawlApp")
def test_search_web_uses_default_limit(mock_app_cls):
    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app
    mock_app.search.return_value = MagicMock(
        success=True,
        data=[
            {
                "title": "Backend",
                "url": "https://example.com/job",
                "markdown": "API developer\nhttps://example.com/job",
            }
        ],
    )

    results = search_web("backend engineer Tokyo")

    assert mock_app.search.call_args.kwargs["limit"] == DEFAULT_SEARCH_LIMIT
    assert results[0]["url"] == "https://example.com/job"
    assert "https://example.com/job" in results[0]["markdown"]


@patch("tools.FirecrawlApp")
def test_search_web_truncates_markdown_per_result(mock_app_cls):
    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app
    mock_app.search.return_value = MagicMock(
        success=True,
        data=[
            {
                "title": "Huge listing",
                "url": "https://jp.indeed.com/jobs",
                "markdown": "X" * 20_000,
            }
        ],
    )

    results = search_web("backend Tokyo")
    assert results[0]["markdown"].endswith("…[truncated]")
    assert len(results[0]["markdown"]) <= MAX_MARKDOWN_CHARS + len("\n…[truncated]")