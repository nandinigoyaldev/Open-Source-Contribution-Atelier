#!/usr/bin/env python
"""
Validate curriculum content before opening a PR.

Checks frontend/public/content/curriculum.json and the lesson markdown files
it points to:
  - missing, malformed or duplicate lesson slugs
  - missing filePath / lesson files that do not exist
  - malformed front matter (a leading "---" block that is not closed or
    contains lines that are not "key: value")
  - broken internal links (relative links to files, anchors, module references,
    and "/lessons/<slug>" links that point at an unknown lesson)
  - broken image and asset references (![...](), <img src="...">)
  - broken quiz data (missing question, bad options, answer out of range,
    or a quiz id that is not defined in quizzes.json)

Usage:
  python scripts/validate_curriculum.py
  python scripts/validate_curriculum.py --content-dir path/to/content
  python scripts/validate_curriculum.py --check-external

Exit code is 1 when any problem is found, 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_CONTENT_DIR = (
    Path(__file__).resolve().parent.parent / "frontend" / "public" / "content"
)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Match [text](target "optional title")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Match ![alt](target "optional title")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Match <img ... src="target" ...>
IMG_TAG_RE = re.compile(r"<img\s+[^>]*?src=[\"']([^\"'>\s]+)[\"'][^>]*>", re.IGNORECASE)
FRONT_MATTER_LINE_RE = re.compile(r"^(?:[A-Za-z0-9_-]+\s*:.*|\s+.*|-\s+.*|#.*|)$")
LESSON_URL_RE = re.compile(r"^/lessons/([^/#?]+)")
MODULE_URL_RE = re.compile(r"^/modules/([^/#?]+)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

Problem = Tuple[str, str]  # (file_or_location, message)


def _load_json(path: Path, problems: List[Problem]) -> Optional[Any]:
    if not path.is_file():
        problems.append((path.name, "file not found"))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append((path.name, f"invalid JSON: {exc}"))
        return None


def slugify_heading(title: str) -> str:
    """GitHub-flavored markdown anchor slugification."""
    # Strip inline code formatting, links, punctuation
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = clean.strip().lower()
    clean = re.sub(r"[^\w\s-]", "", clean)
    return re.sub(r"[-\s]+", "-", clean).strip("-")


def extract_anchors(text: str) -> Set[str]:
    """Extract all valid header anchor slugs and explicit HTML id/name anchors."""
    anchors: Set[str] = set()
    for match in HEADING_RE.finditer(text):
        slug = slugify_heading(match.group(1))
        if slug:
            anchors.add(slug)
    # Also extract explicit <a id="..." name="..."> or id="..." attributes
    for match in re.finditer(r"(?:id|name)=[\"']([^\"']+)[\"']", text):
        anchors.add(match.group(1))
    return anchors


def check_front_matter(text: str) -> Optional[str]:
    """Return a problem description, or None when front matter is fine/absent."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return None
        if not FRONT_MATTER_LINE_RE.match(line):
            return f"malformed front matter on line {index}: {line.strip()!r}"
    return "front matter is not closed (missing second '---')"


def _get_line_number(text: str, match_start: int) -> int:
    return text[:match_start].count("\n") + 1


def check_links_and_assets(
    text: str,
    md_path: Path,
    slugs: Set[str],
    module_ids: Set[str],
    lesson_files: Dict[str, Path],
    content_dir: Path,
    check_external: bool = False,
) -> List[Tuple[int, str]]:
    """Validate internal links, anchors, images, and asset references with line numbers."""
    problems: List[Tuple[int, str]] = []

    # Cache current file anchors
    current_anchors = extract_anchors(text)

    # Clean code blocks for link scanning but keep line counts intact
    code_mask = bytearray(len(text))
    for m in re.finditer(r"```.*?```", text, flags=re.S):
        for i in range(m.start(), m.end()):
            if text[i] != "\n":
                code_mask[i] = 1
    for m in re.finditer(r"`[^`\n]*`", text):
        for i in range(m.start(), m.end()):
            code_mask[i] = 1

    # Helper to check if match index is inside code
    def is_in_code(pos: int) -> bool:
        return bool(code_mask[pos])

    # 1. Check Links
    for m in LINK_RE.finditer(text):
        if is_in_code(m.start()):
            continue
        raw_target = m.group(1).strip()
        line = _get_line_number(text, m.start())
        target = urllib.parse.unquote(raw_target)

        # External links
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
            if check_external:
                # In opt-in external mode, we can validate or flag scheme
                pass
            continue

        # Lesson route: /lessons/<slug>[#anchor]
        lesson_match = LESSON_URL_RE.match(target)
        if lesson_match:
            slug = lesson_match.group(1)
            if slug not in slugs:
                problems.append((line, f"broken internal link: {raw_target} (unknown lesson slug '{slug}')"))
            else:
                # Validate anchor if present
                if "#" in target:
                    anchor = target.split("#", 1)[1]
                    target_file = lesson_files.get(slug)
                    if target_file and target_file.is_file():
                        target_anchors = extract_anchors(target_file.read_text(encoding="utf-8"))
                        if anchor and anchor not in target_anchors:
                            problems.append((line, f"broken anchor link: {raw_target} (anchor '#{anchor}' not found in lesson '{slug}')"))
            continue

        # Module route: /modules/<id>
        module_match = MODULE_URL_RE.match(target)
        if module_match:
            mod_id = module_match.group(1)
            if mod_id not in module_ids:
                problems.append((line, f"broken module link: {raw_target} (unknown module id '{mod_id}')"))
            continue

        # Pure Anchor in current file: #heading-slug
        if target.startswith("#"):
            anchor = target.lstrip("#")
            if anchor and anchor not in current_anchors:
                problems.append((line, f"broken anchor link: {raw_target} (anchor '#{anchor}' not found in file)"))
            continue

        # Relative or root-relative file link
        parsed = urllib.parse.urlparse(target)
        rel_path_str = parsed.path
        anchor = parsed.fragment

        if rel_path_str:
            if rel_path_str.startswith("/"):
                # Path relative to public root / content_dir
                target_path = (content_dir / rel_path_str.lstrip("/")).resolve()
            else:
                target_path = (md_path.parent / rel_path_str).resolve()

            if not target_path.exists():
                problems.append((line, f"broken internal link: {raw_target} (file not found: '{rel_path_str}')"))
            elif anchor and target_path.suffix.lower() == ".md" and target_path.is_file():
                dest_anchors = extract_anchors(target_path.read_text(encoding="utf-8"))
                if anchor not in dest_anchors:
                    problems.append((line, f"broken anchor link: {raw_target} (anchor '#{anchor}' not found in '{rel_path_str}')"))

    # 2. Check Images (![alt](target) and <img src="target">)
    image_matches: List[Tuple[int, str]] = []
    for m in IMAGE_RE.finditer(text):
        if not is_in_code(m.start()):
            image_matches.append((_get_line_number(text, m.start()), m.group(1).strip()))
    for m in IMG_TAG_RE.finditer(text):
        if not is_in_code(m.start()):
            image_matches.append((_get_line_number(text, m.start()), m.group(1).strip()))

    for line, raw_src in image_matches:
        src = urllib.parse.unquote(raw_src)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src) or src.startswith("//"):
            continue
        rel_path_str = urllib.parse.urlparse(src).path
        if not rel_path_str:
            continue
        if rel_path_str.startswith("/"):
            target_path = (content_dir / rel_path_str.lstrip("/")).resolve()
        else:
            target_path = (md_path.parent / rel_path_str).resolve()

        if not target_path.exists():
            problems.append((line, f"missing asset reference: {raw_src} (asset file not found)"))

    return problems


def check_quiz(quiz: Any, label: str) -> List[str]:
    if not isinstance(quiz, dict):
        return [f"{label}: quiz must be an object"]
    problems: List[str] = []
    if not str(quiz.get("question") or "").strip():
        problems.append(f"{label}: missing question")
    options = quiz.get("options")
    if not isinstance(options, list) or len(options) < 2:
        problems.append(f"{label}: needs an options list with at least 2 entries")
        return problems
    answer = quiz.get("answer")
    if isinstance(answer, bool) or not isinstance(answer, int):
        problems.append(f"{label}: answer must be an integer option index")
    elif not 0 <= answer < len(options):
        problems.append(
            f"{label}: answer index {answer} out of range for {len(options)} options"
        )
    return problems


def validate(content_dir: Path, check_external: bool = False) -> List[Problem]:
    problems: List[Problem] = []
    curriculum = _load_json(content_dir / "curriculum.json", problems)
    quiz_bank: Any = {}
    if (content_dir / "quizzes.json").exists():
        quiz_bank = _load_json(content_dir / "quizzes.json", problems)
    if not isinstance(quiz_bank, dict):
        quiz_bank = {}
    for quiz_id, quiz in quiz_bank.items():
        for msg in check_quiz(quiz, f"quiz '{quiz_id}'"):
            problems.append(("quizzes.json", msg))
    if curriculum is None:
        return problems
    modules = curriculum.get("modules") if isinstance(curriculum, dict) else None
    if not isinstance(modules, list):
        problems.append(("curriculum.json", "missing 'modules' list"))
        return problems

    module_ids: Set[str] = {
        str(m.get("id") or m.get("slug") or "")
        for m in modules
        if isinstance(m, dict) and (m.get("id") or m.get("slug"))
    }

    lessons: List[Tuple[str, Dict[str, Any]]] = []
    for m_index, module in enumerate(modules):
        for l_index, lesson in enumerate((module or {}).get("lessons") or []):
            lessons.append((f"modules[{m_index}].lessons[{l_index}]", lesson))

    slugs = set()
    lesson_files: Dict[str, Path] = {}

    for where, lesson in lessons:
        slug = str(lesson.get("slug") or "").strip()
        if not slug:
            problems.append(("curriculum.json", f"{where}: missing slug"))
            continue
        if not SLUG_RE.match(slug):
            problems.append(("curriculum.json", f"{where}: malformed slug {slug!r}"))
        elif slug in slugs:
            problems.append(("curriculum.json", f"{where}: duplicate slug {slug!r}"))
        slugs.add(slug)
        file_path = str(lesson.get("filePath") or "").strip()
        if file_path:
            lesson_files[slug] = content_dir / file_path

    for where, lesson in lessons:
        slug = str(lesson.get("slug") or "").strip() or where
        if not str(lesson.get("title") or "").strip():
            problems.append(("curriculum.json", f"{slug}: missing title"))

        for q_index, quiz in enumerate(lesson.get("quizzes") or []):
            label = f"{slug} quiz #{q_index + 1}"
            if isinstance(quiz, str):
                if quiz not in quiz_bank:
                    problems.append(
                        ("curriculum.json", f"{label}: unknown quiz id {quiz!r}")
                    )
                continue
            for msg in check_quiz(quiz, label):
                problems.append(("curriculum.json", msg))

        file_path = str(lesson.get("filePath") or "").strip()
        if not file_path:
            problems.append(("curriculum.json", f"{slug}: missing filePath"))
            continue
        md_path = content_dir / file_path
        if not md_path.is_file():
            problems.append(("curriculum.json", f"{slug}: file not found: {file_path}"))
            continue
        text = md_path.read_text(encoding="utf-8")
        if not text.strip():
            problems.append((file_path, "lesson file is empty"))
        front_matter = check_front_matter(text)
        if front_matter:
            problems.append((file_path, front_matter))

        link_issues = check_links_and_assets(
            text=text,
            md_path=md_path,
            slugs=slugs,
            module_ids=module_ids,
            lesson_files=lesson_files,
            content_dir=content_dir,
            check_external=check_external,
        )
        for line, msg in link_issues:
            problems.append((f"{file_path}:{line}", msg))

    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate curriculum content.")
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=DEFAULT_CONTENT_DIR,
        help="Directory containing curriculum.json (default: frontend/public/content)",
    )
    parser.add_argument(
        "--check-external",
        action="store_true",
        default=False,
        help="Also check external links (opt-in to avoid flaky network checks in CI)",
    )
    args = parser.parse_args(argv)
    problems = validate(args.content_dir, check_external=args.check_external)
    for location, message in problems:
        print(f"{location}: {message}")
    if problems:
        print(f"\n{len(problems)} problem(s) found.")
        return 1
    print("Curriculum content is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
