import re
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import warnings
from django.core.cache import cache

# Suppress markup resembles locator warnings for plain text content if needed
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


def extract_searchable_text(content: str) -> str:
    """
    Extracts searchable text from Markdown content by stripping code blocks,
    fenced code snippets, and parsing HTML content safely without crashing.
    """
    if not content:
        return ""

    try:
        # 1. Remove fenced code blocks (e.g., ```html ... ```)
        cleaned = re.sub(r'```[\s\S]*?```', '', content)
        
        # 2. Remove inline code snippets (e.g., `<code>`)
        cleaned = re.sub(r'`[^`]*`', '', cleaned)

        # 3. Parse remaining content with BeautifulSoup safely
        soup = BeautifulSoup(cleaned, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        # Raise a caught/wrapped exception to be handled upstream by management commands
        raise ValueError(f"Failed to parse content text: {str(e)}")
