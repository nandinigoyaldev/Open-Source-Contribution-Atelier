"""
CPU cost vs bytes saved for AdaptiveCompressionMiddleware (issue #3515).

Run from backend/:

    python scripts/benchmark_compression.py
    python scripts/benchmark_compression.py --repeat 200 --qualities 1,4,5,6,11

The payloads come from the curriculum files in frontend/public/content and are shaped
like the API answers that carry them (roadmap, lesson detail, the full lesson list with
bodies, glossary, quizzes), plus a 100-row leaderboard page with made-up users. Every
payload goes through AdaptiveCompressionMiddleware.process_response like a real
request, so the time includes the header work and the random padding, not only the
codec. The script configures a bare Django settings object, so it needs no database,
Redis or .env.
"""

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CONTENT = BACKEND.parent / "frontend" / "public" / "content"
sys.path.insert(0, str(BACKEND))

import django  # noqa: E402
from django.conf import settings  # noqa: E402

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8")
    django.setup()

import brotli  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory, override_settings  # noqa: E402

from apps.core.middleware.compression import (  # noqa: E402
    AdaptiveCompressionMiddleware,
)


def lesson_records():
    records = []
    for path in sorted(CONTENT.glob("module-*/*.md")):
        text = path.read_text(encoding="utf-8")
        title = next(
            (line.lstrip("# ").strip() for line in text.splitlines() if line.strip()),
            path.stem,
        )
        records.append(
            {
                "slug": path.stem,
                "module": path.parent.name,
                "title": title,
                "content": text,
            }
        )
    return records


def leaderboard_page(rows=100):
    page = []
    for i in range(rows):
        digest = hashlib.sha256(str(i).encode()).digest()
        page.append(
            {
                "id": 1000 + i,
                "username": f"contributor-{digest.hex()[:8]}",
                "prs_merged": digest[0] % 60,
                "issues_solved": digest[1] % 40,
                "xp": 50_000 - i * 37,
            }
        )
    return {"count": 4213, "next": "/api/leaderboard/?page=2", "results": page}


def as_json(data):
    return json.dumps(data).encode()


def payloads():
    lessons = lesson_records()
    biggest = max(lessons, key=lambda lesson: len(lesson["content"]))
    everything = {"count": len(lessons), "results": lessons}
    return [
        ("401 error body", as_json({"detail": "Authentication credentials missing."})),
        ("quizzes.json", (CONTENT / "quizzes.json").read_bytes()),
        ("glossary.json", (CONTENT / "glossary.json").read_bytes()),
        ("leaderboard page (100 rows)", as_json(leaderboard_page())),
        ("lesson detail (largest)", as_json(biggest)),
        ("curriculum.json (roadmap)", (CONTENT / "curriculum.json").read_bytes()),
        ("all lessons with bodies", as_json(everything)),
    ]


def measure(body, accept, repeat, quality):
    """
    Median seconds per process_response call, median bytes sent and the coding.

    The size is a median because of the 0-99 random padding bytes per response.
    """
    request = RequestFactory().get("/api/", HTTP_ACCEPT_ENCODING=accept)
    middleware = AdaptiveCompressionMiddleware(lambda request: None)
    timings, sizes, coding = [], [], "identity"
    with override_settings(COMPRESSION_BROTLI_QUALITY=quality):
        for _ in range(repeat):
            response = HttpResponse(body, content_type="application/json")
            start = time.perf_counter()
            response = middleware.process_response(request, response)
            timings.append(time.perf_counter() - start)
            sizes.append(len(response.content))
            coding = response.get("Content-Encoding", "identity")
    return statistics.median(timings), int(statistics.median(sizes)), coding


def main():
    parser = argparse.ArgumentParser(
        description="CPU cost vs bytes saved for AdaptiveCompressionMiddleware."
    )
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument(
        "--qualities",
        default="4,5,6,11",
        help="Brotli qualities to compare (comma separated)",
    )
    args = parser.parse_args()
    qualities = [int(q) for q in args.qualities.split(",") if q.strip()]

    print(
        f"python {platform.python_version()}, brotli {brotli.version}, "
        f"{platform.machine()}, {os.cpu_count()} cpus, median of {args.repeat} runs"
    )
    print()
    print("| payload | raw bytes | coding | sent bytes | saved | CPU per response |")
    print("|---|---:|---|---:|---:|---:|")
    for name, body in payloads():
        rows = [("gzip", "gzip", 5)] + [("br", f"br q{q}", q) for q in qualities]
        for accept, label, quality in rows:
            repeat = max(5, args.repeat // 20) if quality >= 10 else args.repeat
            seconds, size, coding = measure(body, accept, repeat, quality)
            if coding == "identity":
                label = "identity (under COMPRESSION_MIN_SIZE)"
            saved = 100 * (1 - size / len(body))
            print(
                f"| {name} | {len(body):,} | {label} | {size:,} | {saved:.1f}% "
                f"| {seconds * 1000:.3f} ms |"
            )
            if coding == "identity":
                break  # the same skip for every coding


if __name__ == "__main__":
    main()
