#!/usr/bin/env python
"""
Validate curriculum content before opening a PR.

Checks frontend/public/content/curriculum.json and the lesson markdown files
it points to:
  - missing, malformed or duplicate lesson slugs
  - missing filePath / lesson files that do not exist
  - malformed front matter (a leading "---" block that is not closed or
    contains lines that are not "key: value")
  - broken internal links (relative links to files and "/lessons/<slug>"
    links that point at an unknown lesson)
  - broken quiz data (missing question, bad options, answer out of range,
    or a quiz id that is not defined in quizzes.json)

Usage:
  python scripts/validate_curriculum.py
  python scripts/validate_curriculum.py --content-dir path/to/content

Exit code is 1 when any problem is found, 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CONTENT_DIR = (
    Path(__file__).resolve().parent.parent / "frontend" / "public" / "content"
)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FRONT_MATTER_LINE_RE = re.compile(r"^(?:[A-Za-z0-9_-]+\s*:.*|\s+.*|-\s+.*|#.*|)$")
LESSON_URL_RE = re.compile(r"^/lessons/([^/#?]+)")

Problem = Tuple[str, str]  # (file, message)


def _load_json(path: Path, problems: List[Problem]) -> Optional[Any]:
    if not path.is_file():
        problems.append((path.name, "file not found"))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append((path.name, f"invalid JSON: {exc}"))
        return None


def check_front_matter(text: str) -> Optional[str]:
    """Return a problem description, or None when front matter is fine/absent."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return None
        if not FRONT_MATTER_LINE_RE.match(line):
            return f"malformed front matter on line {index}: {line.strip()!r}"
    return "front matter is not closed (missing second '---')"


def _strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links(text: str, md_path: Path, slugs: set) -> List[str]:
    problems: List[str] = []
    for target in LINK_RE.findall(_strip_code(text)):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
            continue  # external (http, mailto, ...)
        lesson = LESSON_URL_RE.match(target)
        if lesson:
            if lesson.group(1) not in slugs:
                problems.append(f"broken internal link: {target} (unknown lesson)")
            continue
        if target.startswith(("#", "/")):
            continue  # anchors and app routes cannot be checked against files
        rel = re.split(r"[#?]", target)[0]
        if rel and not (md_path.parent / rel).resolve().exists():
            problems.append(f"broken internal link: {target} (file not found)")
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


def validate(content_dir: Path) -> List[Problem]:
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

    lessons: List[Tuple[str, Dict[str, Any]]] = []
    for m_index, module in enumerate(modules):
        for l_index, lesson in enumerate((module or {}).get("lessons") or []):
            lessons.append((f"modules[{m_index}].lessons[{l_index}]", lesson))

    slugs = set()
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
        for msg in check_links(text, md_path, slugs):
            problems.append((file_path, msg))
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate curriculum content.")
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=DEFAULT_CONTENT_DIR,
        help="Directory containing curriculum.json (default: frontend/public/content)",
    )
    args = parser.parse_args(argv)
    problems = validate(args.content_dir)
    for file, message in problems:
        print(f"{file}: {message}")
    if problems:
        print(f"\n{len(problems)} problem(s) found.")
        return 1
    print("Curriculum content is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
