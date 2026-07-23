"""Security validators and sanitizers for user-uploaded files."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from defusedxml import ElementTree as SafeElementTree
from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class DetectedFileType:
    mime_type: str
    extensions: tuple[str, ...]


FILE_TYPES: dict[str, DetectedFileType] = {
    "jpeg": DetectedFileType("image/jpeg", (".jpg", ".jpeg")),
    "png": DetectedFileType("image/png", (".png",)),
    "webp": DetectedFileType("image/webp", (".webp",)),
    "gif": DetectedFileType("image/gif", (".gif",)),
    "svg": DetectedFileType("image/svg+xml", (".svg",)),
    "pdf": DetectedFileType("application/pdf", (".pdf",)),
    "zip": DetectedFileType("application/zip", (".zip",)),
    "gzip": DetectedFileType("application/gzip", (".gz",)),
    "markdown": DetectedFileType("text/markdown", (".md", ".markdown")),
    "text": DetectedFileType("text/plain", (".txt",)),
}

DEFAULT_ALLOWED_TYPES = tuple(FILE_TYPES)
AVATAR_ALLOWED_TYPES = ("jpeg", "png", "webp", "gif", "svg")

DANGEROUS_TEXT_MARKERS = (
    b"<?php",
    b"<%",
    b"#!/bin/sh",
    b"#!/bin/bash",
    b"#!/usr/bin/env python",
)

SVG_DANGEROUS_TAGS = {"script", "foreignObject"}
SVG_URL_ATTRIBUTES = {"href", "{http://www.w3.org/1999/xlink}href"}
DANGEROUS_URL_RE = re.compile(r"^\s*(?:javascript|data\s*:\s*text/html)", re.I)


def max_size_for(upload_type: str) -> int:
    limits = getattr(
        settings,
        "UPLOAD_MAX_SIZES",
        {
            "avatar": 5 * 1024 * 1024,
            "project": 50 * 1024 * 1024,
            "lesson": 50 * 1024 * 1024,
        },
    )
    return int(limits.get(upload_type, limits.get("project", 50 * 1024 * 1024)))


def validate_declared_size(total_size: int, upload_type: str) -> None:
    if total_size <= 0:
        raise ValidationError("File size must be greater than zero.")
    limit = max_size_for(upload_type)
    if total_size > limit:
        raise ValidationError(
            f"File exceeds the {limit // (1024 * 1024)}MB limit for {upload_type} uploads."
        )


def _looks_like_text(header: bytes) -> bool:
    if b"\x00" in header:
        return False
    try:
        header.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _looks_like_svg(header: bytes) -> bool:
    sample = header.lstrip().lower()
    return sample.startswith(b"<svg") or (
        sample.startswith(b"<?xml") and b"<svg" in sample[:4096]
    )


def detect_file_type(stream: BinaryIO) -> str:
    position = stream.tell()
    try:
        stream.seek(0)
        header = stream.read(8192)
    finally:
        stream.seek(position)

    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "webp"
    if header.startswith(b"%PDF-"):
        return "pdf"
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if header.startswith(b"\x1f\x8b"):
        return "gzip"
    if _looks_like_svg(header):
        return "svg"
    if _looks_like_text(header):
        lowered = header.lower()
        if any(marker in lowered for marker in DANGEROUS_TEXT_MARKERS):
            raise ValidationError(
                "Executable or server-side script content is not allowed."
            )
        return "markdown" if b"#" in header or b"```" in header else "text"

    raise ValidationError("Unsupported or unrecognized file signature.")


def validate_file(
    file_path: str | os.PathLike[str],
    original_filename: str,
    upload_type: str = "project",
) -> tuple[str, str]:
    """Validate size, extension and magic bytes. Returns (kind, MIME type)."""

    path = Path(file_path)
    validate_declared_size(path.stat().st_size, upload_type)

    extension = Path(original_filename).suffix.lower()
    allowed_types = (
        getattr(settings, "UPLOAD_AVATAR_ALLOWED_TYPES", AVATAR_ALLOWED_TYPES)
        if upload_type == "avatar"
        else getattr(settings, "UPLOAD_ALLOWED_TYPES", DEFAULT_ALLOWED_TYPES)
    )

    with path.open("rb") as stream:
        detected = detect_file_type(stream)

    if detected not in allowed_types:
        raise ValidationError(
            f"{FILE_TYPES[detected].mime_type} is not allowed for this upload type."
        )

    if extension not in FILE_TYPES[detected].extensions:
        raise ValidationError(
            f"File extension '{extension or '(none)'}' does not match detected type "
            f"'{FILE_TYPES[detected].mime_type}'."
        )

    return detected, FILE_TYPES[detected].mime_type


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sanitize_svg_bytes(content: bytes) -> bytes:
    """Remove executable SVG elements/attributes while preserving visual nodes."""

    try:
        root = SafeElementTree.fromstring(content)
    except Exception as exc:
        raise ValidationError("Invalid SVG document.") from exc

    def clean(element) -> None:
        for child in list(element):
            if _local_name(child.tag) in SVG_DANGEROUS_TAGS:
                element.remove(child)
            else:
                clean(child)

        for attr_name in list(element.attrib):
            local_attr = _local_name(attr_name).lower()
            value = element.attrib[attr_name]
            if local_attr.startswith("on"):
                del element.attrib[attr_name]
            elif attr_name in SVG_URL_ATTRIBUTES or local_attr == "href":
                if DANGEROUS_URL_RE.match(value):
                    del element.attrib[attr_name]
            elif local_attr == "style" and (
                "javascript:" in value.lower() or "expression(" in value.lower()
            ):
                del element.attrib[attr_name]

    clean(root)
    return SafeElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def sanitize_svg_file(file_path: str | os.PathLike[str]) -> None:
    path = Path(file_path)
    sanitized = sanitize_svg_bytes(path.read_bytes())
    path.write_bytes(sanitized)
