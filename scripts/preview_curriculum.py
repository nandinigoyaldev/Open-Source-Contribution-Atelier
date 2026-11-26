#!/usr/bin/env python3
"""
Validate and preview a curriculum lesson locally without starting the full app.

Reuses validation rules from ``scripts/validate_curriculum.py`` and
``scripts/validate_curriculum_frontmatter.py`` and parses lesson Markdown using
the same block, inline, shortcode, glossary, safe-URL, and reading-time rules
as the frontend lesson renderer.

Usage:
    python scripts/preview_curriculum.py what-is-open-source
    python scripts/preview_curriculum.py what-is-open-source --format html
    python scripts/preview_curriculum.py --list-slugs
"""

from __future__ import annotations

import argparse
import difflib
import html
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from validate_curriculum import (  # noqa: E402
    DEFAULT_CONTENT_DIR,
    SLUG_RE,
    Problem,
    _load_json,
    check_front_matter,
    check_links_and_assets,
    check_quiz,
)
from validate_curriculum_frontmatter import parse_frontmatter  # noqa: E402

INLINE_TOKEN_RE = re.compile(r"(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))")
CODE_MASK_RE = re.compile(r"(`+)([\s\S]*?)\1")
SHORTCODE_RE = re.compile(r"^\[([a-zA-Z0-9-]+)(?:\s+(.*?))?\]$")
SHORTCODE_PROP_RE = re.compile(r'([a-zA-Z0-9-]+)="([^"]*)"')
HR_RE = re.compile(r"^(\s*[-*_]\s*){3,}$")
NUMBERED_RE = re.compile(r"^\d+\.\s")
IMG_TAG_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"[^>]*/?', re.I)
IMG_MD_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)$")
ALERT_TYPE_RE = re.compile(r"> \[!(.*?)\]")
HTML_TAG_RE = re.compile(r"<[^>]*>?")
DISALLOWED_HTML_TAG_RE = re.compile(
    r"</?(?!(?:b|i|em|strong|a|img|p|div|span|code|pre|h[1-6]|ul|ol|li|"
    r"blockquote|hr|br|table|thead|tbody|tr|th|td)\b)[a-zA-Z][a-zA-Z0-9-]*"
    r"(?:\s+[^>]*)?>",
    re.I,
)


class CurriculumPreviewError(Exception):
    """Raised when a slug cannot be resolved or fails curriculum validation."""

    def __init__(self, message: str, problems: Optional[Sequence[Problem]] = None):
        super().__init__(message)
        self.problems = list(problems or [])


@dataclass(frozen=True)
class GlossaryTerm:
    id: str
    term: str
    aliases: Tuple[str, ...]
    short: str
    definition: str


@dataclass(frozen=True)
class LessonPreviewData:
    module: Dict[str, Any]
    lesson: Dict[str, Any]
    frontmatter: Dict[str, Any]
    body: str
    reading_minutes: int
    estimated_minutes: Optional[int]
    quizzes: List[Dict[str, Any]]
    quiz_bank: Dict[str, Dict[str, Any]]
    glossary_terms: List[GlossaryTerm]


def safe_link_href(href: str) -> str:
    """Mirror safeUrl.ts safeLinkHref: reject script/data schemes, preserve relative links."""
    trimmed = href.strip()
    lower = trimmed.lower()
    if (
        lower.startswith("javascript:")
        or lower.startswith("vbscript:")
        or lower.startswith("data:")
    ):
        return "#"
    return trimmed


def safe_image_src(src: str) -> str:
    """Mirror safeUrl.ts safeImageSrc: allow relative paths and drop script-capable schemes."""
    trimmed = src.strip()
    lower = trimmed.lower()
    if (
        lower.startswith("javascript:")
        or lower.startswith("vbscript:")
        or lower.startswith("data:text/html")
    ):
        return ""
    return trimmed


def safe_url(url: str) -> str:
    """Apply link URL sanitization while preserving relative paths."""
    return safe_link_href(url)


def sanitize_lesson_markdown(content: str) -> str:
    """Mirror MarkdownRenderer's DOMPurify allowlist (KEEP_CONTENT=True)."""
    return DISALLOWED_HTML_TAG_RE.sub("", content)


def calculate_reading_time(content: str, words_per_minute: int = 200) -> int:
    """Mirror frontend/src/lib/readingTime.ts reading time calculation."""
    if not content:
        return 1
    clean_text = HTML_TAG_RE.sub("", content).strip()
    words = [w for w in clean_text.split() if w]
    return max(1, math.ceil(len(words) / words_per_minute))


def split_table_row(row: str) -> List[str]:
    """Mirror frontend/src/components/ui/lessonBlocks/table.tsx splitTableRow."""
    trimmed = row.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|") and not trimmed.endswith("\\|"):
        trimmed = trimmed[:-1]

    masked_row = CODE_MASK_RE.sub(
        lambda m: m.group(1) + m.group(2).replace("|", "__ESCAPED_PIPE__") + m.group(1),
        trimmed,
    )

    cells: List[str] = []
    current: List[str] = []
    for idx, ch in enumerate(masked_row):
        prev = masked_row[idx - 1] if idx > 0 else ""
        if ch == "|" and prev != "\\":
            cells.append("".join(current).strip().replace("__ESCAPED_PIPE__", "|"))
            current = []
        else:
            current.append(ch)
    cells.append("".join(current).strip().replace("__ESCAPED_PIPE__", "|"))
    return cells


def load_glossary_terms(content_dir: Path) -> List[GlossaryTerm]:
    """Load optional glossary.json entries."""
    glossary_path = content_dir / "glossary.json"
    if not glossary_path.is_file():
        return []
    problems: List[Problem] = []
    data = _load_json(glossary_path, problems)
    if problems or not isinstance(data, dict):
        return []
    terms_raw = data.get("terms")
    if not isinstance(terms_raw, list):
        return []
    terms: List[GlossaryTerm] = []
    for raw in terms_raw:
        if not isinstance(raw, dict):
            continue
        term_id = str(raw.get("id") or "").strip()
        term = str(raw.get("term") or "").strip()
        if not term_id or not term:
            continue
        raw_aliases = raw.get("aliases")
        aliases = (
            tuple(str(a).strip() for a in raw_aliases if str(a).strip())
            if isinstance(raw_aliases, list)
            else ()
        )
        terms.append(
            GlossaryTerm(
                id=term_id,
                term=term,
                aliases=aliases,
                short=str(raw.get("short") or "").strip(),
                definition=str(raw.get("definition") or "").strip(),
            )
        )
    return terms


def _compile_glossary_patterns(
    terms: Sequence[GlossaryTerm],
) -> List[Tuple[str, GlossaryTerm, re.Pattern[str]]]:
    """Compile case-insensitive word-boundary glossary matchers, longest first."""
    patterns: List[Tuple[str, GlossaryTerm, re.Pattern[str]]] = []
    for entry in terms:
        seen_phrases: Set[str] = set()
        phrases = [entry.term, *entry.aliases]
        for raw_phrase in sorted(phrases, key=len, reverse=True):
            phrase = raw_phrase.strip()
            if not phrase or phrase in seen_phrases:
                continue
            seen_phrases.add(phrase)
            escaped = re.escape(phrase)
            # Match whitespace sequences across spaces like glossary.ts does.
            pattern_str = r"\b" + re.sub(r"(?:\\\s)+", r"\\s+", escaped) + r"\b"
            patterns.append((phrase, entry, re.compile(pattern_str, re.IGNORECASE)))
    patterns.sort(key=lambda item: len(item[0]), reverse=True)
    return patterns


def split_text_with_glossary(
    text: str,
    patterns: Sequence[Tuple[str, GlossaryTerm, re.Pattern[str]]],
) -> List[Tuple[str, Optional[GlossaryTerm]]]:
    """Split non-code text into plain chunks and glossary term matches."""
    if not text or not patterns:
        return [(text, None)] if text else []

    segments: List[Tuple[str, Optional[GlossaryTerm]]] = []
    remaining = text
    while remaining:
        earliest: Optional[Tuple[int, int, GlossaryTerm, str]] = None
        for _phrase, entry, regex in patterns:
            match = regex.search(remaining)
            if not match:
                continue
            start, end = match.span()
            length = end - start
            if (
                earliest is None
                or start < earliest[0]
                or (start == earliest[0] and length > earliest[1])
            ):
                earliest = (start, length, entry, match.group(0))
        if earliest is None:
            segments.append((remaining, None))
            break
        start, length, entry, matched = earliest
        if start > 0:
            segments.append((remaining[:start], None))
        segments.append((matched, entry))
        remaining = remaining[start + length :]
    return segments


def strip_frontmatter(text: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
    """Extract parsed frontmatter metadata, body, and any delimiter/parse error."""
    cleaned = text.lstrip("\ufeff")
    lines = cleaned.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, cleaned, None

    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            metadata, err = parse_frontmatter(cleaned)
            body = "\n".join(lines[idx + 1 :]).lstrip("\n")
            return (metadata or {}) if not err else {}, body, (err or None)
    return {}, cleaned, "front matter is not closed (missing second '---')"


def _format_unknown_slug_error(
    slug: str,
    known_slugs: Sequence[str],
    content_dir: Optional[Path] = None,
) -> str:
    clean_slug = slug.strip()
    lines = [f"Unknown lesson slug: {clean_slug!r}."]
    if clean_slug and not SLUG_RE.match(clean_slug):
        lines.append(
            "Lesson slugs use lowercase kebab-case (for example: 'what-is-open-source')."
        )
    suggestions = difflib.get_close_matches(clean_slug, known_slugs, n=3, cutoff=0.4)
    if suggestions:
        lines.append("Did you mean: " + ", ".join(suggestions) + "?")
    elif known_slugs:
        sample = ", ".join(known_slugs[:5])
        suffix = ", ..." if len(known_slugs) > 5 else ""
        lines.append(f"Sample slugs: {sample}{suffix}")
    list_cmd = "python scripts/preview_curriculum.py --list-slugs"
    if content_dir is not None and content_dir != DEFAULT_CONTENT_DIR:
        list_cmd += f" --content-dir {content_dir}"
    lines.append(f"Run `{list_cmd}` to see all lesson slugs.")
    return " ".join(lines)


def list_curriculum_lessons(
    content_dir: Path,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Return ordered (module, lesson) pairs from curriculum.json."""
    problems: List[Problem] = []
    curriculum = _load_json(content_dir / "curriculum.json", problems)
    if problems or curriculum is None:
        detail = "; ".join(f"{loc}: {msg}" for loc, msg in problems)
        raise CurriculumPreviewError(detail, problems)
    modules = curriculum.get("modules") if isinstance(curriculum, dict) else None
    if not isinstance(modules, list):
        raise CurriculumPreviewError(
            "curriculum.json: missing 'modules' list",
            [("curriculum.json", "missing 'modules' list")],
        )
    entries: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for m_index, module in enumerate(modules):
        if not isinstance(module, dict):
            continue
        mod_label = str(module.get("id") or module.get("slug") or f"modules[{m_index}]")
        raw_lessons = module.get("lessons")
        if raw_lessons is None:
            continue
        if not isinstance(raw_lessons, list):
            raise CurriculumPreviewError(
                f"curriculum.json: {mod_label}: 'lessons' must be a list",
                [("curriculum.json", f"{mod_label}: 'lessons' must be a list")],
            )
        for lesson in raw_lessons:
            if isinstance(lesson, dict):
                entries.append((module, lesson))
    return entries


def load_and_validate_lesson(content_dir: Path, slug: str) -> LessonPreviewData:
    """Validate curriculum manifest + selected lesson and return preview payload."""
    problems: List[Problem] = []
    curriculum = _load_json(content_dir / "curriculum.json", problems)
    quiz_bank: Any = {}
    if (content_dir / "quizzes.json").exists():
        quiz_bank = _load_json(content_dir / "quizzes.json", problems)
    if problems:
        detail = "; ".join(f"{loc}: {msg}" for loc, msg in problems)
        raise CurriculumPreviewError(detail, problems)

    modules = curriculum.get("modules") if isinstance(curriculum, dict) else None
    if not isinstance(modules, list):
        raise CurriculumPreviewError(
            "curriculum.json: missing 'modules' list",
            [("curriculum.json", "missing 'modules' list")],
        )

    if not isinstance(quiz_bank, dict):
        quiz_bank = {}

    module_ids: Set[str] = {
        str(m.get("id") or m.get("slug") or "")
        for m in modules
        if isinstance(m, dict) and (m.get("id") or m.get("slug"))
    }
    known_slugs: List[str] = []
    slugs_set: Set[str] = set()
    slug_counts: Dict[str, int] = {}
    lesson_files: Dict[str, Path] = {}
    target_pair: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None

    for m_index, module in enumerate(modules):
        if not isinstance(module, dict):
            continue
        mod_label = str(module.get("id") or module.get("slug") or f"modules[{m_index}]")
        raw_lessons = module.get("lessons")
        if raw_lessons is None:
            continue
        if not isinstance(raw_lessons, list):
            raise CurriculumPreviewError(
                f"curriculum.json: {mod_label}: 'lessons' must be a list",
                [("curriculum.json", f"{mod_label}: 'lessons' must be a list")],
            )
        for lesson in raw_lessons:
            if not isinstance(lesson, dict):
                continue
            item_slug = str(lesson.get("slug") or "").strip()
            if item_slug:
                slug_counts[item_slug] = slug_counts.get(item_slug, 0) + 1
                if item_slug not in slugs_set:
                    known_slugs.append(item_slug)
                    slugs_set.add(item_slug)
                fp = str(lesson.get("filePath") or "").strip()
                if fp and item_slug not in lesson_files:
                    lesson_files[item_slug] = content_dir / fp
                if item_slug == slug and target_pair is None:
                    target_pair = (module, lesson)

    if target_pair is None:
        raise CurriculumPreviewError(
            _format_unknown_slug_error(slug, known_slugs, content_dir)
        )

    module, lesson = target_pair
    lesson_problems: List[Problem] = []
    validated_bank_ids: Set[str] = set()

    if not SLUG_RE.match(slug):
        lesson_problems.append(("curriculum.json", f"malformed slug {slug!r}"))
    if slug_counts.get(slug, 0) > 1:
        lesson_problems.append(("curriculum.json", f"duplicate slug {slug!r}"))
    if not str(lesson.get("title") or "").strip():
        lesson_problems.append(("curriculum.json", f"{slug}: missing title"))

    estimated_minutes: Optional[int] = None
    if "estimatedMinutes" in lesson:
        minutes = lesson["estimatedMinutes"]
        if type(minutes) is not int or not 1 <= minutes <= 120:
            lesson_problems.append(
                (
                    "curriculum.json",
                    f"{slug}: estimatedMinutes must be an integer between 1 and 120",
                )
            )
        else:
            estimated_minutes = minutes

    resolved_quizzes: List[Dict[str, Any]] = []
    raw_quizzes = lesson.get("quizzes")
    if raw_quizzes is not None and not isinstance(raw_quizzes, list):
        lesson_problems.append(("curriculum.json", f"{slug}: 'quizzes' must be a list"))
        raw_quizzes = []
    for q_index, quiz in enumerate(raw_quizzes or []):
        label = f"{slug} quiz #{q_index + 1}"
        if isinstance(quiz, str):
            if quiz not in quiz_bank:
                lesson_problems.append(
                    ("curriculum.json", f"{label}: unknown quiz id {quiz!r}")
                )
                continue
            validated_bank_ids.add(quiz)
            bank_entry = quiz_bank[quiz]
            for msg in check_quiz(bank_entry, f"quiz '{quiz}'"):
                lesson_problems.append(("quizzes.json", msg))
            if isinstance(bank_entry, dict):
                resolved_quizzes.append({**bank_entry, "id": quiz})
            continue
        for msg in check_quiz(quiz, label):
            lesson_problems.append(("curriculum.json", msg))
        if isinstance(quiz, dict):
            resolved_quizzes.append(quiz)

    file_path = str(lesson.get("filePath") or "").strip()
    if not file_path:
        lesson_problems.append(("curriculum.json", f"{slug}: missing filePath"))
        raise CurriculumPreviewError(
            f"Validation failed for lesson {slug!r}.", lesson_problems
        )

    md_path = content_dir / file_path
    if not md_path.is_file():
        lesson_problems.append(
            ("curriculum.json", f"{slug}: file not found: {file_path}")
        )
        raise CurriculumPreviewError(
            f"Validation failed for lesson {slug!r}.", lesson_problems
        )

    try:
        raw_text = md_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        raise CurriculumPreviewError(
            f"Validation failed for lesson {slug!r}.",
            [(file_path, f"could not read markdown file as UTF-8: {exc}")],
        ) from exc

    if not raw_text.strip():
        lesson_problems.append((file_path, "lesson file is empty"))

    front_matter_error = check_front_matter(raw_text)
    if front_matter_error:
        lesson_problems.append((file_path, front_matter_error))

    frontmatter, body, parse_fm_error = strip_frontmatter(raw_text)
    if parse_fm_error and not front_matter_error:
        lesson_problems.append((file_path, parse_fm_error))

    link_issues = check_links_and_assets(
        text=raw_text,
        md_path=md_path,
        slugs=slugs_set,
        module_ids=module_ids,
        lesson_files=lesson_files,
        content_dir=content_dir,
        check_external=False,
    )
    for line, msg in link_issues:
        lesson_problems.append((f"{file_path}:{line}", msg))

    # Validate any quiz_bank records referenced directly by Markdown shortcodes.
    for blk in _parse_blocks(body):
        if blk["type"] != "shortcode" or blk["name"] != "interactive-quiz":
            continue
        sc_quiz_id = blk["props"].get("id")
        if (
            sc_quiz_id
            and sc_quiz_id in quiz_bank
            and sc_quiz_id not in validated_bank_ids
        ):
            validated_bank_ids.add(sc_quiz_id)
            for msg in check_quiz(quiz_bank[sc_quiz_id], f"quiz '{sc_quiz_id}'"):
                lesson_problems.append(("quizzes.json", msg))

    if lesson_problems:
        raise CurriculumPreviewError(
            f"Validation failed for lesson {slug!r}.", lesson_problems
        )

    glossary_terms = load_glossary_terms(content_dir)
    valid_quiz_bank = {
        k: v
        for k, v in quiz_bank.items()
        if isinstance(k, str)
        and isinstance(v, dict)
        and not check_quiz(v, f"quiz '{k}'")
    }
    return LessonPreviewData(
        module=module,
        lesson=lesson,
        frontmatter=frontmatter,
        body=body,
        reading_minutes=calculate_reading_time(body),
        estimated_minutes=estimated_minutes,
        quizzes=resolved_quizzes,
        quiz_bank=valid_quiz_bank,
        glossary_terms=glossary_terms,
    )


def _is_bullet(line: str) -> bool:
    trimmed = line.strip()
    return trimmed.startswith("- ") or trimmed.startswith("* ")


def _render_inline_text(
    text: str,
    patterns: Sequence[Tuple[str, GlossaryTerm, re.Pattern[str]]],
    matched_glossary: Dict[str, GlossaryTerm],
) -> str:
    """Render inline syntax to readable terminal text while tracking glossary hits."""
    parts = INLINE_TOKEN_RE.split(text)
    out: List[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            inner = part[2:-2]
            out.append(_track_glossary_plain(inner, patterns, matched_glossary))
            continue
        if part.startswith("`") and part.endswith("`"):
            # Inline code is never glossarized.
            out.append(part)
            continue
        if part.startswith("[") and "](" in part:
            match = re.match(r"\[(.*?)\]\((.*?)\)", part)
            if match:
                label, href = match.group(1), safe_link_href(match.group(2))
                rendered_label = _track_glossary_plain(
                    label, patterns, matched_glossary
                )
                out.append(f"{rendered_label} ({href})")
                continue
        out.append(_track_glossary_plain(part, patterns, matched_glossary))
    return "".join(out)


def _track_glossary_plain(
    text: str,
    patterns: Sequence[Tuple[str, GlossaryTerm, re.Pattern[str]]],
    matched_glossary: Dict[str, GlossaryTerm],
) -> str:
    for _chunk, entry in split_text_with_glossary(text, patterns):
        if entry is not None and entry.id not in matched_glossary:
            matched_glossary[entry.id] = entry
    return text


def _render_inline_html(
    text: str,
    patterns: Sequence[Tuple[str, GlossaryTerm, re.Pattern[str]]],
    rendered_term_ids: Set[str],
) -> str:
    """Render inline syntax to escaped HTML matching MarkdownRenderer."""
    parts = INLINE_TOKEN_RE.split(text)
    out: List[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            inner = _render_glossary_html(part[2:-2], patterns, rendered_term_ids)
            out.append(f"<strong>{inner}</strong>")
            continue
        if part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        if part.startswith("[") and "](" in part:
            match = re.match(r"\[(.*?)\]\((.*?)\)", part)
            if match:
                label = _render_glossary_html(
                    match.group(1), patterns, rendered_term_ids
                )
                href = html.escape(safe_link_href(match.group(2)), quote=True)
                out.append(
                    f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
                )
                continue
        out.append(_render_glossary_html(part, patterns, rendered_term_ids))
    return "".join(out)


def _render_glossary_html(
    text: str,
    patterns: Sequence[Tuple[str, GlossaryTerm, re.Pattern[str]]],
    rendered_term_ids: Set[str],
) -> str:
    if not patterns:
        return html.escape(text)
    out: List[str] = []
    for chunk, entry in split_text_with_glossary(text, patterns):
        escaped = html.escape(chunk)
        if entry is None:
            out.append(escaped)
        elif entry.id in rendered_term_ids:
            out.append(f"<span>{escaped}</span>")
        else:
            rendered_term_ids.add(entry.id)
            title = html.escape(entry.short or entry.definition, quote=True)
            term_id = html.escape(entry.id, quote=True)
            out.append(
                f'<span class="glossary-term" data-glossary-id="{term_id}" title="{title}">{escaped}</span>'
            )
    return "".join(out)


def _parse_blocks(body: str) -> List[Dict[str, Any]]:
    """Parse lesson markdown using the exact block precedence of builtInLessonBlocks."""
    sanitized = sanitize_lesson_markdown(body)
    lines = sanitized.split("\n")
    blocks: List[Dict[str, Any]] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        trimmed = line.strip()

        # 1. blankLineBlock
        if trimmed == "":
            index += 1
            continue

        # 2. codeFenceBlock
        if trimmed.startswith("```"):
            lang_match = re.match(r"^```([a-zA-Z0-9_-]+)", trimmed)
            lang = lang_match.group(1).lower() if lang_match else ""
            code_lines: List[str] = []
            nxt = index + 1
            while nxt < len(lines) and not lines[nxt].strip().startswith("```"):
                code_lines.append(lines[nxt])
                nxt += 1
            nxt += 1
            blocks.append(
                {
                    "type": "mermaid" if lang == "mermaid" else "code",
                    "lang": lang or "code",
                    "content": "\n".join(code_lines).strip(),
                }
            )
            index = nxt
            continue

        # 3. headingBlock (# , ## , ### )
        if line.startswith("# "):
            blocks.append({"type": "heading", "level": 1, "text": line[2:]})
            index += 1
            continue
        if line.startswith("## "):
            blocks.append({"type": "heading", "level": 2, "text": line[3:]})
            index += 1
            continue
        if line.startswith("### "):
            blocks.append({"type": "heading", "level": 3, "text": line[4:]})
            index += 1
            continue

        # 4. horizontalRuleBlock
        if HR_RE.match(trimmed):
            blocks.append({"type": "hr"})
            index += 1
            continue

        # 5. alertBlock
        if trimmed.startswith("> [!"):
            alert_match = ALERT_TYPE_RE.match(trimmed)
            alert_type = alert_match.group(1).upper() if alert_match else "NOTE"
            alert_parts: List[str] = []
            nxt = index + 1
            while nxt < len(lines) and lines[nxt].strip().startswith(">"):
                alert_parts.append(lines[nxt].strip()[1:].strip())
                nxt += 1
            blocks.append(
                {
                    "type": "alert",
                    "alert_type": alert_type,
                    "text": " ".join(p for p in alert_parts if p).strip(),
                }
            )
            index = nxt
            continue

        # 6. blockquoteBlock
        if trimmed.startswith(">"):
            quote_parts: List[str] = []
            nxt = index
            while nxt < len(lines) and lines[nxt].strip().startswith(">"):
                quote_parts.append(lines[nxt].strip()[1:].strip())
                nxt += 1
            blocks.append(
                {
                    "type": "blockquote",
                    "text": " ".join(p for p in quote_parts if p).strip(),
                }
            )
            index = nxt
            continue

        # 7. tableBlock
        if trimmed.startswith("|"):
            header_cells = split_table_row(line)
            nxt = index + 1
            if (
                nxt < len(lines)
                and lines[nxt].strip().startswith("|")
                and "-" in lines[nxt]
            ):
                nxt += 1
            rows: List[List[str]] = []
            while nxt < len(lines) and lines[nxt].strip().startswith("|"):
                rows.append(split_table_row(lines[nxt]))
                nxt += 1
            blocks.append({"type": "table", "headers": header_cells, "rows": rows})
            index = nxt
            continue

        # 8. bulletListBlock
        if _is_bullet(line):
            items: List[str] = []
            nxt = index
            while nxt < len(lines) and _is_bullet(lines[nxt]):
                items.append(lines[nxt].strip()[2:].strip())
                nxt += 1
            blocks.append({"type": "bullet_list", "items": items})
            index = nxt
            continue

        # 9. numberedListBlock
        if NUMBERED_RE.match(trimmed):
            first_match = re.match(r"^(\d+)\.\s", trimmed)
            start = int(first_match.group(1)) if first_match else 1
            items = []
            nxt = index
            while nxt < len(lines) and NUMBERED_RE.match(lines[nxt].strip()):
                items.append(NUMBERED_RE.sub("", lines[nxt].strip(), count=1))
                nxt += 1
            blocks.append({"type": "numbered_list", "start": start, "items": items})
            index = nxt
            continue

        # 10. shortcodeBlock
        sc_match = SHORTCODE_RE.match(trimmed)
        if sc_match and "](" not in line:
            props = dict(SHORTCODE_PROP_RE.findall(sc_match.group(2) or ""))
            blocks.append(
                {"type": "shortcode", "name": sc_match.group(1), "props": props}
            )
            index += 1
            continue

        # 11. htmlImageBlock
        img_tag_match = IMG_TAG_RE.search(trimmed)
        if img_tag_match:
            alt_m = re.search(r'alt="([^"]*)"', line, re.I)
            blocks.append(
                {
                    "type": "image",
                    "src": safe_image_src(img_tag_match.group(1)),
                    "alt": alt_m.group(1) if alt_m else "image",
                }
            )
            index += 1
            continue

        # 12. markdownImageBlock
        img_md_match = IMG_MD_RE.match(trimmed)
        if img_md_match:
            blocks.append(
                {
                    "type": "image",
                    "src": safe_image_src(img_md_match.group(2)),
                    "alt": img_md_match.group(1),
                }
            )
            index += 1
            continue

        # 13. paragraphBlock fallback
        blocks.append({"type": "paragraph", "text": line})
        index += 1

    return blocks


def _resolve_shortcode_quiz(
    data: LessonPreviewData, props: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    quiz_id = props.get("id")
    if quiz_id is not None:
        if quiz_id in data.quiz_bank:
            return {**data.quiz_bank[quiz_id], "id": quiz_id}
        for q in data.quizzes:
            if q.get("id") == quiz_id:
                return q
        return None
    if data.quizzes:
        return data.quizzes[0]
    return None


def render_preview_text(data: LessonPreviewData) -> str:
    """Render a validated lesson preview as human-readable terminal output."""
    lesson = data.lesson
    module = data.module
    patterns = _compile_glossary_patterns(data.glossary_terms)
    matched_glossary: Dict[str, GlossaryTerm] = {}
    blocks = _parse_blocks(data.body)

    display_minutes = (
        data.estimated_minutes
        if data.estimated_minutes is not None
        else data.reading_minutes
    )
    time_source = (
        "curriculum estimatedMinutes"
        if data.estimated_minutes is not None
        else "calculated @ 200 wpm"
    )

    out: List[str] = [
        f"=== Lesson Preview: {lesson.get('title', '')} ===",
        f"Slug:       {lesson.get('slug', '')}",
        f"Module:     {module.get('title', module.get('id', ''))} ({module.get('id', '')})",
        f"Difficulty: {lesson.get('difficulty', 'unspecified')}",
        f"Points:     {lesson.get('points', 'unspecified')}",
        f"Time:       {display_minutes} min ({time_source}; body read time: {data.reading_minutes} min)",
        f"File:       {lesson.get('filePath', '')}",
    ]
    if lesson.get("description"):
        out.append(f"Summary:    {lesson['description']}")
    if lesson.get("expected"):
        out.append(f"Expected:   {lesson['expected']}")
    if lesson.get("hint"):
        out.append(f"Hint:       {lesson['hint']}")
    if data.frontmatter:
        fm_pairs = ", ".join(f"{k}={v}" for k, v in data.frontmatter.items())
        out.append(f"Frontmatter:{' '}{fm_pairs}")
    out.append("")
    out.append("--- Rendered Content ---")

    for blk in blocks:
        btype = blk["type"]
        if btype == "heading":
            prefix = "#" * blk["level"]
            text = _render_inline_text(blk["text"], patterns, matched_glossary)
            out.append(f"{prefix} {text}")
            out.append("")
        elif btype == "hr":
            out.append("-" * 40)
        elif btype == "code":
            out.append(f"[{blk['lang'].upper()}]")
            out.append(blk["content"])
            out.append("[/CODE]")
            out.append("")
        elif btype == "mermaid":
            out.append("[MERMAID DIAGRAM]")
            out.append(blk["content"])
            out.append("[/MERMAID]")
            out.append("")
        elif btype == "alert":
            text = _render_inline_text(blk["text"], patterns, matched_glossary)
            out.append(f"[{blk['alert_type']}] {text}")
            out.append("")
        elif btype == "blockquote":
            text = _render_inline_text(blk["text"], patterns, matched_glossary)
            out.append(f"> {text}")
            out.append("")
        elif btype == "table":
            out.append(" | ".join(blk["headers"]))
            out.append(" | ".join("-" * max(3, len(h)) for h in blk["headers"]))
            for row in blk["rows"]:
                rendered_cells = [
                    _render_inline_text(cell, patterns, matched_glossary)
                    for cell in row
                ]
                out.append(" | ".join(rendered_cells))
            out.append("")
        elif btype == "bullet_list":
            for item in blk["items"]:
                out.append(
                    f"  - {_render_inline_text(item, patterns, matched_glossary)}"
                )
            out.append("")
        elif btype == "numbered_list":
            for offset, item in enumerate(blk["items"]):
                num = blk["start"] + offset
                out.append(
                    f"  {num}. {_render_inline_text(item, patterns, matched_glossary)}"
                )
            out.append("")
        elif btype == "shortcode":
            name = blk["name"]
            if name == "interactive-quiz":
                quiz = _resolve_shortcode_quiz(data, blk["props"])
                if quiz:
                    question_text = quiz.get("question", "")
                    out.append(f"[QUIZ: {quiz.get('id', 'inline')}] {question_text}")
                    for idx, opt in enumerate(quiz.get("options") or []):
                        marker = "*" if idx == quiz.get("answer") else " "
                        out.append(f"  [{marker}] {idx + 1}. {opt}")
                else:
                    out.append(
                        f"[QUIZ WARNING: interactive-quiz {blk['props'].get('id', '')!r} not found]"
                    )
            else:
                out.append(f"[WARNING] Unsupported interactive component: {name}")
            out.append("")
        elif btype == "image":
            out.append(f"[IMAGE alt={blk['alt']!r} src={blk['src']!r}]")
            out.append("")
        elif btype == "paragraph":
            out.append(_render_inline_text(blk["text"], patterns, matched_glossary))
            out.append("")

    if data.quizzes:
        out.append("--- Lesson Quizzes ---")
        for q_idx, quiz in enumerate(data.quizzes, start=1):
            out.append(f"{q_idx}. {quiz.get('question', '')}")
            for o_idx, opt in enumerate(quiz.get("options") or []):
                mark = "*" if o_idx == quiz.get("answer") else " "
                out.append(f"   [{mark}] {opt}")
        out.append("")

    if matched_glossary:
        out.append("--- Glossary Terms Highlighted ---")
        for entry in matched_glossary.values():
            summary = entry.short or entry.definition
            out.append(f"- {entry.term} ({entry.id}): {summary}")

    return "\n".join(out).rstrip() + "\n"


def render_preview_html(data: LessonPreviewData) -> str:
    """Render a validated lesson preview as a self-contained HTML fragment/document."""
    lesson = data.lesson
    module = data.module
    patterns = _compile_glossary_patterns(data.glossary_terms)
    rendered_terms: Set[str] = set()
    blocks = _parse_blocks(data.body)

    display_minutes = (
        data.estimated_minutes
        if data.estimated_minutes is not None
        else data.reading_minutes
    )

    parts: List[str] = [
        '<article class="lesson-preview">',
        "<header>",
        f"<h1>{html.escape(str(lesson.get('title') or ''))}</h1>",
        (
            f'<p class="lesson-meta">Module: {html.escape(str(module.get("title") or ""))} '
            f"| Slug: <code>{html.escape(str(lesson.get('slug') or ''))}</code> "
            f"| Difficulty: {html.escape(str(lesson.get('difficulty') or 'unspecified'))} "
            f"| {display_minutes} min read</p>"
        ),
    ]
    if lesson.get("description"):
        parts.append(
            f'<p class="lesson-description">{html.escape(str(lesson["description"]))}</p>'
        )
    parts.append("</header>")

    for blk in blocks:
        btype = blk["type"]
        if btype == "heading":
            tag = f"h{blk['level']}"
            inner = _render_inline_html(blk["text"], patterns, rendered_terms)
            parts.append(f"<{tag}>{inner}</{tag}>")
        elif btype == "hr":
            parts.append("<hr />")
        elif btype in ("code", "mermaid"):
            lang = html.escape(blk["lang"], quote=True)
            code = html.escape(blk["content"])
            parts.append(f'<pre data-lang="{lang}"><code>{code}</code></pre>')
        elif btype == "alert":
            atype = html.escape(blk["alert_type"], quote=True)
            inner = _render_inline_html(blk["text"], patterns, rendered_terms)
            parts.append(
                f'<div class="alert alert-{atype.lower()}"><strong>{atype}</strong><p>{inner}</p></div>'
            )
        elif btype == "blockquote":
            inner = _render_inline_html(blk["text"], patterns, rendered_terms)
            parts.append(f"<blockquote>{inner}</blockquote>")
        elif btype == "table":
            ths = "".join(f"<th>{html.escape(h)}</th>" for h in blk["headers"])
            trs = []
            for row in blk["rows"]:
                tds = "".join(
                    f"<td>{_render_inline_html(cell, patterns, rendered_terms)}</td>"
                    for cell in row
                )
                trs.append(f"<tr>{tds}</tr>")
            parts.append(
                f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
            )
        elif btype == "bullet_list":
            lis = "".join(
                f"<li>{_render_inline_html(item, patterns, rendered_terms)}</li>"
                for item in blk["items"]
            )
            parts.append(f"<ul>{lis}</ul>")
        elif btype == "numbered_list":
            lis = "".join(
                f"<li>{_render_inline_html(item, patterns, rendered_terms)}</li>"
                for item in blk["items"]
            )
            parts.append(f'<ol start="{blk["start"]}">{lis}</ol>')
        elif btype == "shortcode":
            name = blk["name"]
            if name == "interactive-quiz":
                quiz = _resolve_shortcode_quiz(data, blk["props"])
                if quiz:
                    question_text = str(quiz.get("question") or "")
                    opts = "".join(
                        f"<li>{html.escape(str(opt))}</li>"
                        for opt in (quiz.get("options") or [])
                    )
                    parts.append(
                        f'<section class="interactive-quiz"><p><strong>{html.escape(question_text)}</strong></p><ul>{opts}</ul></section>'
                    )
                else:
                    parts.append(
                        f'<div class="shortcode-warning">Unknown interactive-quiz id: {html.escape(blk["props"].get("id", ""))}</div>'
                    )
            else:
                parts.append(
                    f'<div class="shortcode-error">Unsupported interactive component: {html.escape(name)}</div>'
                )
        elif btype == "image":
            src = html.escape(blk["src"], quote=True)
            alt = html.escape(blk["alt"], quote=True)
            parts.append(f'<img src="{src}" alt="{alt}" />')
        elif btype == "paragraph":
            parts.append(
                f"<p>{_render_inline_html(blk['text'], patterns, rendered_terms)}</p>"
            )

    if data.quizzes:
        quiz_items: List[str] = []
        for quiz in data.quizzes:
            question = html.escape(str(quiz.get("question") or ""))
            opts = "".join(
                (
                    f'<li data-correct="true">{html.escape(str(opt))}</li>'
                    if o_idx == quiz.get("answer")
                    else f"<li>{html.escape(str(opt))}</li>"
                )
                for o_idx, opt in enumerate(quiz.get("options") or [])
            )
            quiz_items.append(
                f"<li><p><strong>{question}</strong></p><ul>{opts}</ul></li>"
            )
        parts.append(
            f'<section class="lesson-quizzes"><h2>Lesson Quizzes</h2><ol>{"".join(quiz_items)}</ol></section>'
        )

    parts.append("</article>")
    return "\n".join(parts) + "\n"


def format_slug_listing(
    entries: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]],
) -> str:
    """Format available module/lesson slugs for discovery."""
    lines = ["Available curriculum lesson slugs:"]
    for module, lesson in entries:
        slug = lesson.get("slug", "")
        title = lesson.get("title", "")
        mod_id = module.get("id", "")
        lines.append(f"  - {slug}  [{mod_id}] {title}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Validate and preview a curriculum lesson locally."
    )
    parser.add_argument(
        "slug",
        nargs="?",
        help="Lesson slug from curriculum.json (for example: 'what-is-open-source')",
    )
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=DEFAULT_CONTENT_DIR,
        help="Directory containing curriculum.json (default: frontend/public/content)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "html"),
        default="text",
        help="Preview output format (default: text)",
    )
    parser.add_argument(
        "--list-slugs",
        action="store_true",
        help="List all available lesson slugs and exit",
    )
    args = parser.parse_args(argv)

    try:
        if args.list_slugs:
            entries = list_curriculum_lessons(args.content_dir)
            print(format_slug_listing(entries), end="")
            return 0

        if not args.slug or not args.slug.strip():
            print(
                "Error: Please provide a lesson slug, or pass --list-slugs to see available lessons.",
                file=sys.stderr,
            )
            return 2

        data = load_and_validate_lesson(args.content_dir, args.slug.strip())
    except CurriculumPreviewError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        for location, msg in exc.problems:
            print(f"  - {location}: {msg}", file=sys.stderr)
        return 1

    output = (
        render_preview_html(data)
        if args.format == "html"
        else render_preview_text(data)
    )
    print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
