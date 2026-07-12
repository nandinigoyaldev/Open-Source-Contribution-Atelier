import math
import re


def strip_markdown(text: str) -> str:
    """Remove Markdown formatting elements to get a clean text representation for word counting."""
    if not text:
        return ""

    # 1. Remove HTML tags
    text = re.sub(r"<[^>]*>", " ", text)

    # 2. Replace code block markers (```python or ```) with spaces, keeping the code content inside
    text = re.sub(r"```[a-zA-Z0-9_-]*", " ", text)

    # 3. Replace inline code backticks with spaces
    text = re.sub(r"`", " ", text)

    # 4. Remove images: ![alt](url) -> keep alt text, discard url
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r" \1 ", text)

    # 5. Remove links: [text](url) -> keep text, discard url
    text = re.sub(r"\[([^\]]*)\]\([^\)]+\)", r" \1 ", text)

    # 6. Remove headers, blockquotes, and list markers
    # Replace leading #, >, *, -, +, or numbers with dots/hyphens with space
    text = re.sub(r"^\s*#+\s+", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s+", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", " ", text, flags=re.MULTILINE)

    # 7. Remove emphasis markers: bold/italic (*, _, ~)
    text = re.sub(r"[\*_~]", " ", text)

    return text


def calculate_reading_time(content: str) -> int:
    """Calculate estimated reading time in minutes for a given content.

    Assumes average reading speed of 200 words per minute.
    Returns a minimum value of 1.
    """
    if not content:
        return 1

    clean_text = strip_markdown(content)
    words = clean_text.split()
    word_count = len(words)

    reading_time = math.ceil(word_count / 200)
    return max(1, reading_time)
