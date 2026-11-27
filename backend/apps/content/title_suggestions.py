"""Typo tolerant "did you mean" suggestions for lesson titles.

Plain Python, so it behaves the same on SQLite and Postgres. The cost of one
request is bounded by the query length, the number of query words, the number of
titles scanned and the number of words read from each title.
"""

import re
import unicodedata

from .models import Lesson

MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 80
MAX_QUERY_WORDS = 8
MAX_SUGGESTIONS = 5
MAX_TITLES_SCANNED = 1000
MAX_TITLE_WORDS = 20
MAX_WORD_LENGTH = 32


def normalize(text):
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", folded))


def allowed_edits(word):
    if len(word) <= 2:
        return 0
    return 1 if len(word) <= 5 else 2


def edit_distance(a, b, limit):
    """Edit distance where swapping two neighbouring letters counts as one edit.

    Stops early and returns ``limit + 1`` once the distance cannot be within
    ``limit``.
    """
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    two_back = []
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            cost = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            )
            if i > 1 and j > 1 and char_a == b[j - 2] and a[i - 2] == char_b:
                cost = min(cost, two_back[j - 2] + 1)
            current.append(cost)
        if min(current) > limit:
            return limit + 1
        two_back, previous = previous, current
    return min(previous[-1], limit + 1)


def _title_distance(query_words, title_words, memo):
    """Total edits needed to find every query word in the title, or None."""
    total = 0
    for word in query_words:
        limit = allowed_edits(word)
        best = limit + 1
        for title_word in title_words:
            key = (word, title_word)
            if key not in memo:
                memo[key] = edit_distance(word, title_word, limit)
            best = min(best, memo[key])
            if best == 0:
                break
        if best > limit:
            return None
        total += best
    return total


def rank_title_suggestions(query, titles, limit=MAX_SUGGESTIONS):
    """Rank ``(slug, title)`` pairs that are a close, but not direct, match.

    Returns nothing when the query already appears in a title, because that is a
    normal search hit and must not compete with guesses.
    """
    query = query.strip()
    if not MIN_QUERY_LENGTH <= len(query) <= MAX_QUERY_LENGTH:
        return []
    normalized = normalize(query)
    words = [word[:MAX_WORD_LENGTH] for word in normalized.split()]
    if len(words) > MAX_QUERY_WORDS:
        return []
    # Very short words ("a", "to") only count when there is nothing longer.
    words = [word for word in words if len(word) > 2] or words
    if not words:
        return []

    memo = {}
    ranked = []
    for slug, title in titles:
        normalized_title = normalize(title)
        if normalized in normalized_title:
            return []
        title_words = [
            word[:MAX_WORD_LENGTH]
            for word in normalized_title.split()[:MAX_TITLE_WORDS]
        ]
        distance = _title_distance(words, title_words, memo)
        if distance is not None:
            ranked.append((distance, len(title_words), title.casefold(), slug, title))

    ranked.sort()
    return [
        {"slug": slug, "title": title, "kind": "suggestion"}
        for _, _, _, slug, title in ranked[: min(limit, MAX_SUGGESTIONS)]
    ]


def lesson_title_suggestions(query):
    """Suggestions drawn from public lessons (the ones with no organization)."""
    query = query.strip()
    if not MIN_QUERY_LENGTH <= len(query) <= MAX_QUERY_LENGTH:
        return []
    titles = (
        Lesson.objects.filter(organization__isnull=True)
        .order_by("order", "id")
        .values_list("slug", "title")[:MAX_TITLES_SCANNED]
    )
    return rank_title_suggestions(query, titles)
