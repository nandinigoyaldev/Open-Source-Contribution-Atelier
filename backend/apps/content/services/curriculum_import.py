"""
Streaming validator for curriculum import archives.

An archive is a zip file holding ``manifest.json`` plus one markdown file per
lesson (see ``docs/CURRICULUM_IMPORT.md``). Nothing in this module writes to
the database: it only reads the archive and reports problems, so it is safe to
run before anything is published.

Validation is split in two so it can be resumed:

* :func:`check_manifest` reads the (small) manifest and checks everything that
  can be decided without opening lesson files: shape, duplicate module ids and
  lesson slugs, missing references (prerequisites, quiz ids, lesson files) and
  inline quiz data.
* :func:`validate_lesson_file` opens one lesson member of the zip, reads it with
  a hard size cap and checks front matter, empty bodies, links and URLs. The
  caller walks the lessons in chunks and stores a cursor, so a crashed worker
  can pick up at the first lesson it had not finished.

The front matter, link and quiz checks mirror ``scripts/validate_curriculum.py``
(which works on a content directory on disk instead of a zip).
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from posixpath import normpath
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

MANIFEST_NAME = "manifest.json"
QUIZ_BANK_NAME = "quizzes.json"
FORMAT_VERSION = 1

# Hard limits so a hostile archive cannot exhaust memory or disk.
MAX_MEMBERS = 5000
MAX_LESSON_BYTES = 1024 * 1024  # 1 MiB of markdown per lesson
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_URL_RE = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
FRONT_MATTER_LINE_RE = re.compile(r"^(?:[A-Za-z0-9_-]+\s*:.*|\s+.*|-\s+.*|#.*|)$")
LESSON_URL_RE = re.compile(r"^/lessons/([^/#?]+)")
SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
SAFE_SCHEMES = {"http", "https", "mailto"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}

Problem = Dict[str, str]  # {"code", "file", "message"}


class ArchiveError(Exception):
    """The archive cannot be read at all (not a zip, too big, no manifest...)."""


def problem(code: str, file: str, message: str) -> Problem:
    return {"code": code, "file": file, "message": message}


@dataclass(frozen=True)
class LessonEntry:
    """One lesson from the manifest, in manifest order."""

    index: int
    module_id: str
    module_title: str
    slug: str
    title: str
    summary: str
    difficulty: str
    estimated_minutes: int
    file_path: str
    prerequisites: Tuple[str, ...]
    quiz_count: int


@dataclass
class ManifestResult:
    manifest: Dict[str, Any]
    lessons: List[LessonEntry]
    problems: List[Problem]


# ---------------------------------------------------------------------------
# Archive access
# ---------------------------------------------------------------------------


def open_archive(file) -> zipfile.ZipFile:
    """Open ``file`` (path or file object) as a zip and apply the safety caps."""
    try:
        zf = zipfile.ZipFile(file)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchiveError(f"not a readable zip archive: {exc}") from exc
    infos = zf.infolist()
    if len(infos) > MAX_MEMBERS:
        zf.close()
        raise ArchiveError(f"archive has {len(infos)} entries (limit {MAX_MEMBERS})")
    total = sum(info.file_size for info in infos)
    if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
        zf.close()
        raise ArchiveError(
            f"archive expands to {total} bytes "
            f"(limit {MAX_TOTAL_UNCOMPRESSED_BYTES})"
        )
    return zf


def is_safe_member_path(path: str) -> bool:
    """True for relative, forward-slash paths that stay inside the archive."""
    if not path or "\\" in path or "\x00" in path or path.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", path):
        return False
    return not any(part == ".." for part in path.split("/"))


def read_member(zf: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """Read a member, refusing to go past ``limit`` bytes (zip-bomb guard)."""
    info = zf.getinfo(name)
    if info.file_size > limit:
        raise ArchiveError(f"{name} is {info.file_size} bytes (limit {limit})")
    with zf.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ArchiveError(f"{name} is larger than {limit} bytes")
    return data


# ---------------------------------------------------------------------------
# Individual checks (shared by manifest and lesson validation)
# ---------------------------------------------------------------------------


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


def strip_front_matter(text: str) -> str:
    """Return the markdown body without a leading, well-formed front matter block."""
    text = text.lstrip("﻿")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[index + 1 :]).lstrip("\n")
    return text


def _strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def unsafe_url_reason(url: str) -> Optional[str]:
    """Why ``url`` must not be imported, or None when it is acceptable."""
    cleaned = re.sub(r"[\x00-\x20]+", "", url)  # browsers ignore these in schemes
    match = SCHEME_RE.match(cleaned)
    if match and match.group(1).lower() not in SAFE_SCHEMES:
        return f"unsafe URL scheme {match.group(1).lower()!r}"
    return None


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


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def _load_json_member(
    zf: zipfile.ZipFile, name: str, problems: List[Problem], required: bool
) -> Any:
    if name not in zf.namelist():
        if required:
            raise ArchiveError(f"{name} not found in archive")
        return None
    try:
        return json.loads(read_member(zf, name, MAX_MANIFEST_BYTES).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if required:
            raise ArchiveError(f"{name} is not valid JSON: {exc}") from exc
        problems.append(problem("invalid_json", name, f"invalid JSON: {exc}"))
        return None


def check_manifest(zf: zipfile.ZipFile) -> ManifestResult:
    """Validate everything that is decidable from ``manifest.json`` alone."""
    problems: List[Problem] = []
    manifest = _load_json_member(zf, MANIFEST_NAME, problems, required=True)
    if not isinstance(manifest, dict):
        raise ArchiveError("manifest.json must contain a JSON object")

    version = manifest.get("format_version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        problems.append(
            problem(
                "unsupported_version",
                MANIFEST_NAME,
                f"unsupported format_version {version!r} (expected {FORMAT_VERSION})",
            )
        )

    quiz_bank = _load_json_member(zf, QUIZ_BANK_NAME, problems, required=False)
    if not isinstance(quiz_bank, dict):
        quiz_bank = {}
    for quiz_id, quiz in quiz_bank.items():
        for msg in check_quiz(quiz, f"quiz '{quiz_id}'"):
            problems.append(problem("bad_quiz", QUIZ_BANK_NAME, msg))

    modules = manifest.get("modules")
    if not isinstance(modules, list):
        problems.append(
            problem("bad_manifest", MANIFEST_NAME, "missing 'modules' list")
        )
        return ManifestResult(manifest, [], problems)

    members = set(zf.namelist())
    raw: List[Tuple[str, str, Dict[str, Any], str]] = []
    module_ids = set()
    for m_index, module in enumerate(modules):
        where_m = f"modules[{m_index}]"
        if not isinstance(module, dict):
            problems.append(
                problem("bad_manifest", MANIFEST_NAME, f"{where_m}: must be an object")
            )
            continue
        module_id = str(module.get("id") or "").strip()
        if not module_id:
            problems.append(
                problem("missing_id", MANIFEST_NAME, f"{where_m}: missing module id")
            )
        elif module_id in module_ids:
            problems.append(
                problem(
                    "duplicate_id",
                    MANIFEST_NAME,
                    f"{where_m}: duplicate module id {module_id!r}",
                )
            )
        module_ids.add(module_id)
        if not str(module.get("title") or "").strip():
            problems.append(
                problem("missing_title", MANIFEST_NAME, f"{where_m}: missing title")
            )
        lessons = module.get("lessons")
        if lessons is None:
            lessons = []
        if not isinstance(lessons, list):
            problems.append(
                problem(
                    "bad_manifest",
                    MANIFEST_NAME,
                    f"{where_m}: 'lessons' must be a list",
                )
            )
            continue
        for l_index, lesson in enumerate(lessons):
            where = f"{where_m}.lessons[{l_index}]"
            if not isinstance(lesson, dict):
                problems.append(
                    problem(
                        "bad_manifest", MANIFEST_NAME, f"{where}: must be an object"
                    )
                )
                continue
            raw.append((module_id, str(module.get("title") or ""), lesson, where))

    # Pass 1: slugs (so references can point forward as well as back).
    slugs = set()
    for _module_id, _module_title, lesson, where in raw:
        slug = str(lesson.get("slug") or "").strip()
        if not slug:
            problems.append(
                problem("missing_slug", MANIFEST_NAME, f"{where}: missing slug")
            )
            continue
        if not SLUG_RE.match(slug):
            problems.append(
                problem(
                    "malformed_slug", MANIFEST_NAME, f"{where}: malformed slug {slug!r}"
                )
            )
        elif slug in slugs:
            problems.append(
                problem(
                    "duplicate_slug", MANIFEST_NAME, f"{where}: duplicate slug {slug!r}"
                )
            )
        slugs.add(slug)

    # Pass 2: everything else, producing the LessonEntry list.
    entries: List[LessonEntry] = []
    seen_files: Dict[str, str] = {}
    for module_id, module_title, lesson, where in raw:
        slug = str(lesson.get("slug") or "").strip()
        label = slug or where
        title = str(lesson.get("title") or "").strip()
        if not title:
            problems.append(
                problem("missing_title", MANIFEST_NAME, f"{label}: missing title")
            )
        difficulty = str(lesson.get("difficulty") or "beginner").strip().lower()
        if difficulty not in VALID_DIFFICULTIES:
            problems.append(
                problem(
                    "bad_difficulty",
                    MANIFEST_NAME,
                    f"{label}: difficulty {difficulty!r} is not one of "
                    f"{sorted(VALID_DIFFICULTIES)}",
                )
            )
        minutes = lesson.get("estimatedMinutes", 15)
        if isinstance(minutes, bool) or not isinstance(minutes, int):
            problems.append(
                problem(
                    "bad_minutes",
                    MANIFEST_NAME,
                    f"{label}: estimatedMinutes must be an integer",
                )
            )
            minutes = 15
        elif not 1 <= minutes <= 120:
            problems.append(
                problem(
                    "bad_minutes",
                    MANIFEST_NAME,
                    f"{label}: estimatedMinutes {minutes} must be between 1 and 120",
                )
            )

        prereqs = lesson.get("prerequisites") or []
        clean_prereqs: List[str] = []
        if not isinstance(prereqs, list):
            problems.append(
                problem(
                    "bad_manifest",
                    MANIFEST_NAME,
                    f"{label}: 'prerequisites' must be a list of slugs",
                )
            )
        else:
            for ref in prereqs:
                ref = str(ref)
                if ref == slug:
                    problems.append(
                        problem(
                            "self_prerequisite",
                            MANIFEST_NAME,
                            f"{label}: lesson lists itself as a prerequisite",
                        )
                    )
                elif ref not in slugs:
                    problems.append(
                        problem(
                            "missing_reference",
                            MANIFEST_NAME,
                            f"{label}: prerequisite {ref!r} is not a lesson in this archive",
                        )
                    )
                else:
                    clean_prereqs.append(ref)

        quizzes = lesson.get("quizzes") or []
        if not isinstance(quizzes, list):
            problems.append(
                problem("bad_quiz", MANIFEST_NAME, f"{label}: 'quizzes' must be a list")
            )
            quizzes = []
        for q_index, quiz in enumerate(quizzes):
            qlabel = f"{label} quiz #{q_index + 1}"
            if isinstance(quiz, str):
                if quiz not in quiz_bank:
                    problems.append(
                        problem(
                            "missing_reference",
                            MANIFEST_NAME,
                            f"{qlabel}: unknown quiz id {quiz!r}",
                        )
                    )
                continue
            for msg in check_quiz(quiz, qlabel):
                problems.append(problem("bad_quiz", MANIFEST_NAME, msg))

        file_path = str(lesson.get("filePath") or "").strip()
        if not file_path:
            problems.append(
                problem(
                    "missing_file_path", MANIFEST_NAME, f"{label}: missing filePath"
                )
            )
        elif not is_safe_member_path(file_path):
            problems.append(
                problem(
                    "unsafe_path",
                    MANIFEST_NAME,
                    f"{label}: unsafe filePath {file_path!r}",
                )
            )
            file_path = ""
        elif file_path not in members:
            problems.append(
                problem(
                    "missing_reference",
                    MANIFEST_NAME,
                    f"{label}: lesson file not found in archive: {file_path}",
                )
            )
        elif file_path in seen_files:
            problems.append(
                problem(
                    "duplicate_file",
                    MANIFEST_NAME,
                    f"{label}: filePath {file_path!r} already used by {seen_files[file_path]!r}",
                )
            )
        else:
            seen_files[file_path] = label

        entries.append(
            LessonEntry(
                index=len(entries),
                module_id=module_id,
                module_title=module_title,
                slug=slug,
                title=title,
                summary=str(lesson.get("description") or "").strip(),
                difficulty=difficulty,
                estimated_minutes=minutes if isinstance(minutes, int) else 15,
                file_path=file_path,
                prerequisites=tuple(clean_prereqs),
                quiz_count=len(quizzes),
            )
        )
    return ManifestResult(manifest, entries, problems)


# ---------------------------------------------------------------------------
# Lesson file validation
# ---------------------------------------------------------------------------


def decode_lesson(zf: zipfile.ZipFile, entry: LessonEntry) -> str:
    return read_member(zf, entry.file_path, MAX_LESSON_BYTES).decode("utf-8")


def validate_lesson_file(
    zf: zipfile.ZipFile, entry: LessonEntry, slugs: Sequence[str]
) -> List[Problem]:
    """Validate one lesson's markdown. Never raises for content problems."""
    if not entry.file_path:
        return []  # already reported by check_manifest
    file = entry.file_path
    try:
        text = decode_lesson(zf, entry)
    except UnicodeDecodeError:
        return [problem("bad_encoding", file, "lesson file is not valid UTF-8")]
    except (ArchiveError, KeyError) as exc:
        return [problem("unreadable", file, str(exc))]

    found: List[Problem] = []
    if not text.strip():
        found.append(problem("empty_lesson", file, "lesson file is empty"))
    fm = check_front_matter(text)
    if fm:
        found.append(problem("malformed_front_matter", file, fm))

    body = _strip_code(text)
    members = None
    slug_set = set(slugs)
    targets = LINK_RE.findall(body) + IMAGE_RE.findall(body) + HTML_URL_RE.findall(body)
    for target in targets:
        reason = unsafe_url_reason(target)
        if reason:
            found.append(problem("unsafe_url", file, f"{reason}: {target}"))
            continue
        if SCHEME_RE.match(target) or target.startswith("//"):
            continue  # external http(s)/mailto
        lesson_link = LESSON_URL_RE.match(target)
        if lesson_link:
            if lesson_link.group(1) not in slug_set:
                found.append(
                    problem(
                        "missing_reference",
                        file,
                        f"broken internal link: {target} (unknown lesson)",
                    )
                )
            continue
        if target.startswith(("#", "/")):
            continue  # anchors and app routes cannot be checked against files
        rel = re.split(r"[#?]", target)[0]
        if not rel:
            continue
        if members is None:
            members = set(zf.namelist())
        base = file.rsplit("/", 1)[0] if "/" in file else ""
        resolved = normpath(f"{base}/{rel}" if base else rel)
        if resolved.startswith("..") or resolved not in members:
            found.append(
                problem(
                    "missing_reference",
                    file,
                    f"broken internal link: {target} (file not found in archive)",
                )
            )
    return found


def chunked(items: Sequence[LessonEntry], size: int) -> Iterator[Sequence[LessonEntry]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
