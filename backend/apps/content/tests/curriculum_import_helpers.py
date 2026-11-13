"""Helpers for building curriculum import archives in tests."""

import io
import json
import zipfile
from pathlib import Path
from typing import Dict, Union

SAMPLE_DIR = Path(__file__).parent / "fixtures" / "curriculum_import" / "sample"

Files = Dict[str, Union[str, bytes]]


def sample_files() -> Files:
    """The files of the on-disk sample archive, keyed by archive path."""
    return {
        path.relative_to(SAMPLE_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(SAMPLE_DIR.rglob("*"))
        if path.is_file()
    }


def make_zip(files: Files) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def sample_zip(changes: Dict[str, Union[str, bytes, None]] = None) -> bytes:
    """The sample archive with ``changes`` applied (path -> data, None drops it)."""
    files = sample_files()
    for name, data in (changes or {}).items():
        if data is None:
            files.pop(name, None)
        else:
            files[name] = data
    return make_zip(files)


def sample_manifest() -> dict:
    return json.loads(sample_files()["manifest.json"])


def zip_with_manifest(manifest: dict, extra: Files = None) -> bytes:
    files = sample_files()
    files["manifest.json"] = json.dumps(manifest)
    files.update(extra or {})
    return make_zip(files)
