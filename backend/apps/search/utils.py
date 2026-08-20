from django.core.cache import cache
import re
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import warnings

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def get_search_cache_version():
    """
    Retrieves the current search cache version.
    Defaults to 1 if not set.
    """
    return cache.get("search_api_version", 1)


def bump_search_cache_version():
    """
    Increments the search cache version.
    This effectively invalidates all existing search caches
    without requiring a wildcard deletion.
    """
    try:
        cache.incr("search_api_version")
    except ValueError:
        cache.set("search_api_version", 1)


def extract_searchable_text(markdown_content: str) -> str:
    """
    Extracts searchable plain text from Markdown content.
    Strips code blocks and safely handles raw HTML tags to prevent parsing crashes.
    """
    if not markdown_content:
        return ""

    # Strip multi-line and inline code blocks to prevent BeautifulSoup parsing errors
    cleaned = re.sub(r"```[\s\S]*?```", "", markdown_content)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)

    try:
        # Use BeautifulSoup to parse and extract text safely
        soup = BeautifulSoup(cleaned, "html.parser")
        text = soup.get_text(separator=" ")
    except Exception:
        # Fallback raw string cleanup if parser encounters malformed tags
        text = re.sub(r"<[^>]*>", "", cleaned)

    return " ".join(text.split())
