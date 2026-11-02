#!/usr/bin/env python3
"""
Duplicate issue candidate finder.

Normalizes issue titles and ranks open issues by similarity to a new issue.
It only suggests candidates; it never closes or labels anything.

Input (stdin or --input): JSON {"title": str, "number": int, "issues": [{"number": int, "title": str}]}
Output: JSON list of candidates, best first.
"""

import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List

# Titles scoring at or above this are suggested as possible duplicates.
SIMILARITY_THRESHOLD = 0.8
# Titles with fewer meaningful words than this only match when identical
# after normalization, so short generic titles are not flagged.
MIN_TOKENS_FOR_FUZZY = 3
MAX_CANDIDATES = 5

_BRACKET_PREFIX = re.compile(r"^\s*(?:[\[\(][^\]\)]{0,40}[\]\)]\s*)+")
_CONVENTIONAL_PREFIX = re.compile(
    r"^\s*(?:bug|feature|feat|fix|enhancement|docs?|chore|refactor|task|issue|request)"
    r"(?:\([^)]*\))?\s*[:\-]\s*",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^\w\s]|_", re.UNICODE)


def normalize_title(title: str) -> str:
    """Lowercase, drop [Tag]/'bug:' style prefixes, punctuation and extra spaces."""
    text = unicodedata.normalize("NFKC", title or "")
    text = _BRACKET_PREFIX.sub("", text)
    text = _CONVENTIONAL_PREFIX.sub("", text)
    text = _NON_WORD.sub(" ", text.lower())
    return " ".join(text.split())


def similarity(a: str, b: str) -> float:
    """Score two titles from 0 to 1 using their normalized forms."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = na.split(), nb.split()
    if min(len(ta), len(tb)) < MIN_TOKENS_FOR_FUZZY:
        return 0.0
    jaccard = len(set(ta) & set(tb)) / len(set(ta) | set(tb))
    ratio = SequenceMatcher(None, na, nb).ratio()
    return round(max(jaccard, ratio), 4)


def find_candidates(
    title: str,
    issues: List[Dict],
    exclude_number=None,
    threshold: float = SIMILARITY_THRESHOLD,
    limit: int = MAX_CANDIDATES,
) -> List[Dict]:
    """Return issues similar to title, best score first, ties by issue number."""
    scored = []
    for issue in issues:
        if exclude_number is not None and issue.get("number") == exclude_number:
            continue
        score = similarity(title, issue.get("title", ""))
        if score >= threshold:
            scored.append(
                {"number": issue["number"], "title": issue.get("title", ""), "score": score}
            )
    scored.sort(key=lambda c: (-c["score"], c["number"]))
    return scored[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSON file (default: stdin)")
    args = parser.parse_args()
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = json.load(sys.stdin)
    result = find_candidates(data["title"], data.get("issues", []), data.get("number"))
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
