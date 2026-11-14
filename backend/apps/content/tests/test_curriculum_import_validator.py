import io
import zipfile

import pytest

from apps.content.services import curriculum_import as ci

from .curriculum_import_helpers import (
    make_zip,
    sample_manifest,
    sample_zip,
    zip_with_manifest,
)

BRANCHES = "module-2/branches.md"


def check(data: bytes):
    """Run the full validator (manifest + every lesson) over ``data``."""
    with ci.open_archive(io.BytesIO(data)) as zf:
        result = ci.check_manifest(zf)
        problems = list(result.problems)
        slugs = [e.slug for e in result.lessons if e.slug]
        for entry in result.lessons:
            problems.extend(ci.validate_lesson_file(zf, entry, slugs))
    return problems


def codes(problems):
    return {p["code"] for p in problems}


def test_sample_archive_is_valid():
    assert check(sample_zip()) == []


def test_duplicate_slug_and_module_id():
    manifest = sample_manifest()
    manifest["modules"][1]["id"] = "module-1"
    manifest["modules"][1]["lessons"][0]["slug"] = "sample-what-is-git"
    found = codes(check(zip_with_manifest(manifest)))
    assert {"duplicate_id", "duplicate_slug"} <= found


def test_malformed_and_missing_slug():
    manifest = sample_manifest()
    manifest["modules"][0]["lessons"][0]["slug"] = "Not A Slug"
    del manifest["modules"][0]["lessons"][1]["slug"]
    found = codes(check(zip_with_manifest(manifest)))
    assert {"malformed_slug", "missing_slug"} <= found


def test_missing_references():
    manifest = sample_manifest()
    lessons = manifest["modules"][0]["lessons"]
    lessons[1]["prerequisites"] = ["no-such-lesson"]
    lessons[1]["quizzes"] = ["no-such-quiz"]
    manifest["modules"][1]["lessons"][0]["filePath"] = "module-2/gone.md"
    problems = [
        p
        for p in check(zip_with_manifest(manifest))
        if p["code"] == "missing_reference"
    ]
    messages = " ".join(p["message"] for p in problems)
    assert "no-such-lesson" in messages
    assert "no-such-quiz" in messages
    assert "module-2/gone.md" in messages


def test_prerequisite_can_point_forward():
    manifest = sample_manifest()
    manifest["modules"][0]["lessons"][0]["prerequisites"] = ["sample-branches"]
    assert check(zip_with_manifest(manifest)) == []


def test_self_prerequisite():
    manifest = sample_manifest()
    manifest["modules"][0]["lessons"][0]["prerequisites"] = ["sample-what-is-git"]
    assert "self_prerequisite" in codes(check(zip_with_manifest(manifest)))


def test_unsafe_file_path_is_rejected_not_read():
    manifest = sample_manifest()
    manifest["modules"][0]["lessons"][0]["filePath"] = "../../etc/passwd"
    manifest["modules"][0]["lessons"][1]["filePath"] = "/abs/path.md"
    problems = check(zip_with_manifest(manifest))
    assert [p["code"] for p in problems].count("unsafe_path") == 2


def test_duplicate_file_path():
    manifest = sample_manifest()
    manifest["modules"][0]["lessons"][1]["filePath"] = "module-1/what-is-git.md"
    assert "duplicate_file" in codes(check(zip_with_manifest(manifest)))


def test_bad_inline_quiz_difficulty_and_minutes():
    manifest = sample_manifest()
    lesson = manifest["modules"][0]["lessons"][0]
    lesson["quizzes"] = [{"question": "q", "options": ["a", "b"], "answer": 5}]
    lesson["difficulty"] = "godlike"
    lesson["estimatedMinutes"] = 500
    found = codes(check(zip_with_manifest(manifest)))
    assert {"bad_quiz", "bad_difficulty", "bad_minutes"} <= found


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox",
        "file:///etc/passwd",
    ],
)
def test_unsafe_urls_in_links_images_and_html(url):
    for body in (f"[x]({url})", f"![x]({url})", f'<a href="{url}">x</a>'):
        found = [
            p for p in check(sample_zip({BRANCHES: body})) if p["code"] == "unsafe_url"
        ]
        assert found, body


def test_safe_urls_pass():
    body = (
        "[a](https://example.com) [b](http://example.com/x) "
        "[c](mailto:a@b.co) [d](#anchor)"
    )
    assert check(sample_zip({BRANCHES: body})) == []


def test_urls_inside_code_are_ignored():
    body = "Use `[x](javascript:alert(1))`.\n\n```\n[x](javascript:alert(1))\n```\n"
    assert check(sample_zip({BRANCHES: body})) == []


def test_malformed_front_matter():
    bad_line = "---\ntitle: ok\nthis line is not a key\n---\nBody"
    unclosed = "---\ntitle: ok\nBody without end"
    assert "malformed_front_matter" in codes(check(sample_zip({BRANCHES: bad_line})))
    assert "malformed_front_matter" in codes(check(sample_zip({BRANCHES: unclosed})))


def test_empty_lesson():
    assert "empty_lesson" in codes(check(sample_zip({BRANCHES: "  \n"})))


def test_broken_internal_links():
    body = "[a](/lessons/ghost) [b](./missing.md) [c](../module-1/first-commit.md)"
    problems = [
        p
        for p in check(sample_zip({BRANCHES: body}))
        if p["code"] == "missing_reference"
    ]
    messages = " ".join(p["message"] for p in problems)
    assert "/lessons/ghost" in messages
    assert "./missing.md" in messages
    assert "first-commit.md" not in messages


def test_link_cannot_escape_archive():
    body = "[a](../../outside.md)"
    assert "missing_reference" in codes(check(sample_zip({BRANCHES: body})))


def test_invalid_utf8_lesson():
    manifest = (
        '{"modules":[{"id":"m","title":"M","lessons":'
        '[{"slug":"a","title":"A","filePath":"a.md"}]}]}'
    )
    data = make_zip({"manifest.json": manifest, "a.md": b"\xff\xfe\x00bad"})
    assert "bad_encoding" in codes(check(data))


def test_oversized_lesson_is_reported(monkeypatch):
    monkeypatch.setattr(ci, "MAX_LESSON_BYTES", 10)
    assert "unreadable" in codes(check(sample_zip()))


def test_archive_level_errors():
    with pytest.raises(ci.ArchiveError):
        ci.open_archive(io.BytesIO(b"this is not a zip"))
    with pytest.raises(ci.ArchiveError, match="manifest.json not found"):
        with ci.open_archive(io.BytesIO(make_zip({"a.md": "x"}))) as zf:
            ci.check_manifest(zf)
    with pytest.raises(ci.ArchiveError, match="not valid JSON"):
        with ci.open_archive(io.BytesIO(make_zip({"manifest.json": "{nope"}))) as zf:
            ci.check_manifest(zf)
    with pytest.raises(ci.ArchiveError, match="JSON object"):
        with ci.open_archive(io.BytesIO(make_zip({"manifest.json": "[]"}))) as zf:
            ci.check_manifest(zf)


def test_member_count_and_size_caps(monkeypatch):
    monkeypatch.setattr(ci, "MAX_MEMBERS", 2)
    with pytest.raises(ci.ArchiveError, match="entries"):
        ci.open_archive(io.BytesIO(sample_zip()))
    monkeypatch.setattr(ci, "MAX_MEMBERS", 5000)
    monkeypatch.setattr(ci, "MAX_TOTAL_UNCOMPRESSED_BYTES", 100)
    with pytest.raises(ci.ArchiveError, match="expands"):
        ci.open_archive(io.BytesIO(sample_zip()))


def test_unsupported_format_version():
    manifest = sample_manifest()
    manifest["format_version"] = 99
    assert "unsupported_version" in codes(check(zip_with_manifest(manifest)))


def test_archive_is_read_in_place_from_a_path(tmp_path):
    path = tmp_path / "c.zip"
    path.write_bytes(sample_zip())
    with ci.open_archive(str(path)) as zf:
        assert isinstance(zf, zipfile.ZipFile)
        assert ci.check_manifest(zf).problems == []
    assert [p.name for p in tmp_path.iterdir()] == ["c.zip"]
