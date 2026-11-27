"""Tests for AdaptiveCompressionMiddleware (issue #3515)."""

import asyncio
import gzip
import hashlib
import io
import json
import os
from typing import Any
from unittest import mock

import brotli
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path

from apps.core.middleware.compression import (
    DEFAULT_MIN_SIZE,
    AdaptiveCompressionMiddleware,
    choose_encoding,
    compress_bytes,
    parse_accept_encoding,
)

# Roughly what a lesson list looks like on the wire, well over the 1024 byte threshold.
LESSONS = [
    {
        "slug": f"lesson-{i}",
        "title": "Rebasing a feature branch onto main",
        "module": f"module-{i % 6 + 1}",
        "completed": i % 3 == 0,
    }
    for i in range(120)
]
BODY = json.dumps({"count": len(LESSONS), "results": LESSONS}).encode()
BROWSER = "gzip, deflate, br, zstd"


def run(
    accept=BROWSER, response=None, body=BODY, content_type="application/json"
) -> Any:
    """Send one GET through the middleware and return the response."""
    factory = RequestFactory()
    url = "/api/content/published-lessons/"
    if accept is None:
        request = factory.get(url)
    else:
        request = factory.get(url, HTTP_ACCEPT_ENCODING=accept)
    if response is None:
        response = HttpResponse(body, content_type=content_type)
    return AdaptiveCompressionMiddleware(lambda request: response)(request)


def decode(data, coding):
    if coding == "br":
        return brotli.decompress(data)
    if coding == "gzip":
        return gzip.decompress(data)
    return data


def vary(response):
    return [v.strip().lower() for v in response.get("Vary", "").split(",") if v]


class AcceptEncodingTests(SimpleTestCase):
    def test_brotli_wins_a_tie(self):
        self.assertEqual(choose_encoding(BROWSER), "br")
        self.assertEqual(choose_encoding("br, gzip"), "br")
        self.assertEqual(choose_encoding("gzip, br"), "br")

    def test_single_codings(self):
        self.assertEqual(choose_encoding("gzip"), "gzip")
        self.assertEqual(choose_encoding("br"), "br")
        self.assertEqual(choose_encoding("x-gzip"), "gzip")
        self.assertEqual(choose_encoding("GZip"), "gzip")

    def test_higher_q_value_wins(self):
        self.assertEqual(choose_encoding("gzip;q=1.0, br;q=0.5"), "gzip")
        self.assertEqual(choose_encoding("br;q=0.8, gzip;q=0.9"), "gzip")
        self.assertEqual(choose_encoding("br;q=0.9, gzip;q=0.8"), "br")
        self.assertEqual(choose_encoding(" br ; q=0.7 , gzip ; Q=0.6 "), "br")

    def test_q_zero_means_not_acceptable(self):
        self.assertEqual(choose_encoding("br;q=0, gzip"), "gzip")
        self.assertEqual(choose_encoding("gzip;q=0, br"), "br")
        self.assertIsNone(choose_encoding("br;q=0, gzip;q=0.000"))

    def test_identity_when_nothing_usable(self):
        for header in ["", None, "identity", "deflate", "zstd", "compress;q=0.5"]:
            self.assertIsNone(choose_encoding(header), header)

    def test_wildcard(self):
        self.assertEqual(choose_encoding("*"), "br")
        self.assertEqual(choose_encoding("*;q=0.5, br;q=0"), "gzip")
        self.assertEqual(choose_encoding("gzip;q=0.4, *;q=0.5"), "br")
        self.assertIsNone(choose_encoding("*;q=0"))

    def test_broken_q_values_count_as_zero(self):
        self.assertEqual(choose_encoding("br;q=abc, gzip"), "gzip")
        self.assertEqual(choose_encoding("br;q=2, gzip;q=0.1"), "gzip")
        self.assertEqual(choose_encoding("br;q=-1, gzip;q=0.1"), "gzip")
        self.assertIsNone(choose_encoding("br;q=nan, gzip;q=inf"))

    def test_parse_keeps_first_entry(self):
        self.assertEqual(
            parse_accept_encoding("gzip;q=0.2, br, gzip;q=0.9"),
            {"gzip": 0.2, "br": 1.0},
        )

    def test_only_gzip_without_brotli_module(self):
        self.assertEqual(choose_encoding("br, gzip", available=("gzip",)), "gzip")
        self.assertIsNone(choose_encoding("br", available=("gzip",)))
        with mock.patch("apps.core.middleware.compression.brotli", None):
            response = run(accept="br, gzip")
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(response.content), BODY)


class BufferedResponseTests(SimpleTestCase):
    def test_brotli_when_requested(self):
        response = run()
        self.assertEqual(response["Content-Encoding"], "br")
        self.assertEqual(brotli.decompress(response.content), BODY)
        self.assertEqual(response["Content-Length"], str(len(response.content)))
        self.assertLess(len(response.content), len(BODY))
        self.assertIn("accept-encoding", vary(response))

    def test_gzip_fallback(self):
        response = run(accept="gzip, deflate")
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(response.content), BODY)
        self.assertEqual(response["Content-Length"], str(len(response.content)))

    def test_q_values_pick_gzip_over_brotli(self):
        response = run(accept="br;q=0.1, gzip;q=0.9")
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(response.content), BODY)

    def test_identity(self):
        for accept in [None, "", "identity", "br;q=0, gzip;q=0", "deflate"]:
            response = run(accept=accept)
            self.assertFalse(response.has_header("Content-Encoding"), accept)
            self.assertEqual(response.content, BODY)
            # The next client may accept br, so caches must still key on it.
            self.assertIn("accept-encoding", vary(response), accept)

    def test_round_trip_for_text_types(self):
        text = ("<li>git rebase -i main</li>\n" * 200).encode()
        for content_type in ["text/html", "text/csv", "image/svg+xml", "text/plain"]:
            for coding in ["br", "gzip"]:
                response = run(accept=coding, body=text, content_type=content_type)
                self.assertEqual(response["Content-Encoding"], coding, content_type)
                self.assertEqual(decode(response.content, coding), text)

    def test_min_size_threshold(self):
        self.assertEqual(DEFAULT_MIN_SIZE, 1024)
        small = b"a" * 1023
        response = run(body=small)
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response.content, small)
        self.assertNotIn("accept-encoding", vary(response))

        response = run(body=b"a" * 1024)
        self.assertEqual(response["Content-Encoding"], "br")
        self.assertEqual(brotli.decompress(response.content), b"a" * 1024)

    @override_settings(COMPRESSION_MIN_SIZE=len(BODY) + 1)
    def test_min_size_comes_from_settings(self):
        response = run()
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response.content, BODY)

    def test_settings_default_is_1024(self):
        self.assertEqual(settings.COMPRESSION_MIN_SIZE, 1024)

    def test_already_encoded_response_is_left_alone(self):
        payload = gzip.compress(BODY)
        response = HttpResponse(payload, content_type="application/json")
        response["Content-Encoding"] = "gzip"
        response = run(response=response)
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertEqual(response.content, payload)
        self.assertFalse(response.has_header("Vary"))

    def test_binary_types_are_skipped(self):
        for content_type in [
            "audio/mpeg",
            "audio/wav",
            "video/mp4",
            "image/png",
            "image/jpeg",
            "image/webp",
            "application/zip",
            "application/gzip",
            "application/x-gzip",
            "application/octet-stream",
            "font/woff2",
            "Application/ZIP; charset=binary",
        ]:
            response = run(body=b"\0" * 5000, content_type=content_type)
            self.assertFalse(response.has_header("Content-Encoding"), content_type)
            self.assertEqual(response.content, b"\0" * 5000)
            self.assertNotIn("accept-encoding", vary(response), content_type)

    def test_partial_content_is_skipped(self):
        response = HttpResponse(BODY, content_type="text/csv", status=206)
        response["Content-Range"] = f"bytes 0-{len(BODY) - 1}/{len(BODY) * 2}"
        response = run(response=response)
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response.content, BODY)

    def test_range_capable_download_is_skipped(self):
        # Shaped like ExportDownloadView: a resumed download gets identity ranges.
        response = StreamingHttpResponse(iter([BODY]), content_type="text/csv")
        response["Accept-Ranges"] = "bytes"
        response["ETag"] = '"sha256-of-the-file"'
        response["Content-Length"] = str(len(BODY))
        response = run(response=response)
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response["ETag"], '"sha256-of-the-file"')
        self.assertEqual(response["Content-Length"], str(len(BODY)))
        self.assertEqual(b"".join(response.streaming_content), BODY)

    def test_body_that_does_not_shrink_is_sent_as_is(self):
        noise = os.urandom(4096)
        response = run(body=noise, content_type="application/json")
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response.content, noise)
        self.assertIn("accept-encoding", vary(response))

    def test_strong_etag_becomes_weak(self):
        response = HttpResponse(BODY, content_type="application/json")
        response["ETag"] = '"v1-lessons"'
        self.assertEqual(run(response=response)["ETag"], 'W/"v1-lessons"')

        response = HttpResponse(BODY, content_type="application/json")
        response["ETag"] = 'W/"v1-lessons"'
        self.assertEqual(run(response=response)["ETag"], 'W/"v1-lessons"')

        response = HttpResponse(BODY, content_type="application/json")
        response["ETag"] = '"v1-lessons"'
        self.assertEqual(
            run(accept="identity", response=response)["ETag"], '"v1-lessons"'
        )

    def test_existing_vary_is_kept(self):
        response = HttpResponse(BODY, content_type="application/json")
        response["Vary"] = "Cookie"
        self.assertEqual(vary(run(response=response)), ["cookie", "accept-encoding"])

    def test_json_response(self):
        response = run(response=JsonResponse({"results": LESSONS}))
        self.assertEqual(response["Content-Encoding"], "br")
        self.assertEqual(
            json.loads(brotli.decompress(response.content)), {"results": LESSONS}
        )


class RandomPaddingTests(SimpleTestCase):
    """The BREACH padding GZipMiddleware has, for both codings."""

    def test_length_changes_between_responses(self):
        for coding in ["br", "gzip"]:
            outputs = [compress_bytes(BODY, coding) for _ in range(30)]
            self.assertGreater(len({len(out) for out in outputs}), 1, coding)
            for out in outputs:
                self.assertEqual(decode(out, coding), BODY)

    def test_no_padding_is_stable(self):
        for coding in ["br", "gzip"]:
            outputs = {
                compress_bytes(BODY, coding, max_random_bytes=0) for _ in range(5)
            }
            self.assertEqual(len(outputs), 1, coding)

    def test_brotli_metadata_block_edges(self):
        plain = compress_bytes(BODY, "br", max_random_bytes=0)
        for padding, extra in [(1, 3), (99, 101), (256, 258), (400, 258)]:
            with mock.patch(
                "apps.core.middleware.compression.secrets.randbelow",
                return_value=padding,
            ):
                out = compress_bytes(BODY, "br", max_random_bytes=500)
            self.assertEqual(brotli.decompress(out), BODY, padding)
            self.assertEqual(len(out), len(plain) + extra, padding)

    def test_gzip_padding_matches_django(self):
        with mock.patch(
            "apps.core.middleware.compression.secrets.randbelow", return_value=42
        ):
            out = compress_bytes(BODY, "gzip")
        self.assertEqual(out[3] & gzip.FNAME, gzip.FNAME)
        self.assertEqual(out[10:53], b"a" * 42 + b"\0")
        self.assertEqual(gzip.decompress(out), BODY)


def csv_rows(count, consumed):
    yield b"id,lesson,digest\n"
    for i in range(count):
        consumed.append(i)
        # About 1 KB of hex digests per row: barely compressible, so the encoder has
        # to send output along the way instead of sitting on it.
        noise = "".join(
            hashlib.sha256(f"{i}-{j}".encode()).hexdigest() for j in range(16)
        )
        yield f"{i},lesson-{i % 31},{noise}\n".encode()


class StreamingResponseTests(SimpleTestCase):
    def test_stream_is_compressed_lazily(self):
        for coding in ["br", "gzip"]:
            consumed = []
            response = run(
                accept=coding,
                response=StreamingHttpResponse(
                    csv_rows(400, consumed), content_type="text/csv"
                ),
            )
            self.assertEqual(response["Content-Encoding"], coding)
            self.assertFalse(response.has_header("Content-Length"))
            self.assertIn("accept-encoding", vary(response))
            # Nothing is read from the source until the server starts sending.
            self.assertEqual(consumed, [], coding)

            pieces, seen_at = [], []
            for piece in response.streaming_content:
                pieces.append(piece)
                if piece:
                    seen_at.append(len(consumed))
            # Output went out while rows were still being produced, so the body
            # was never held in memory as a whole.
            self.assertLess(seen_at[1], 100, coding)
            self.assertGreater(len(seen_at), 4, coding)

            expected = b"".join(csv_rows(400, []))
            self.assertEqual(decode(b"".join(pieces), coding), expected)

    def test_stream_round_trip(self):
        chunks = [
            line.encode() for line in (f"{i},git-rebase,{i * 7}\n" for i in range(3000))
        ]
        for coding in ["br", "gzip"]:
            response = run(
                accept=coding,
                response=StreamingHttpResponse(iter(chunks), content_type="text/csv"),
            )
            body = b"".join(response.streaming_content)
            self.assertEqual(decode(body, coding), b"".join(chunks))

    def test_async_stream_round_trip(self):
        chunks = [f"{i},git-rebase,{i * 7}\n".encode() for i in range(3000)]

        async def rows():
            for chunk in chunks:
                yield chunk

        async def collect(response):
            return b"".join([piece async for piece in response.streaming_content])

        for coding in ["br", "gzip"]:
            response = run(
                accept=coding,
                response=StreamingHttpResponse(rows(), content_type="text/csv"),
            )
            self.assertTrue(response.is_async)
            self.assertEqual(response["Content-Encoding"], coding)
            body = asyncio.run(collect(response))
            self.assertEqual(decode(body, coding), b"".join(chunks))

    def test_declared_small_stream_is_skipped(self):
        response = StreamingHttpResponse(iter([b"a" * 100]), content_type="text/csv")
        response["Content-Length"] = "100"
        response = run(response=response)
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response["Content-Length"], "100")
        self.assertEqual(b"".join(response.streaming_content), b"a" * 100)

    def test_declared_large_stream_drops_content_length(self):
        response = StreamingHttpResponse(iter([BODY]), content_type="application/json")
        response["Content-Length"] = str(len(BODY))
        response = run(response=response)
        self.assertEqual(response["Content-Encoding"], "br")
        self.assertFalse(response.has_header("Content-Length"))
        self.assertEqual(brotli.decompress(b"".join(response.streaming_content)), BODY)

    def test_file_response_is_compressed_not_sent_raw(self):
        response = FileResponse(io.BytesIO(BODY), content_type="application/json")
        self.assertEqual(response["Content-Length"], str(len(BODY)))
        response = run(accept="gzip", response=response)
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertFalse(response.has_header("Content-Length"))
        # With file_to_stream set the WSGI server would send the raw file instead.
        self.assertIsNone(response.file_to_stream)
        self.assertEqual(gzip.decompress(b"".join(response.streaming_content)), BODY)

    def test_event_stream_is_not_buffered(self):
        events = [f"data: token {i}\n\n".encode() for i in range(500)]
        response = run(
            response=StreamingHttpResponse(
                iter(events), content_type="text/event-stream"
            )
        )
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertNotIn("accept-encoding", vary(response))
        self.assertEqual(list(response.streaming_content), events)

    def test_binary_stream_is_skipped(self):
        response = StreamingHttpResponse(
            iter([b"PK\x03\x04" * 2000]), content_type="application/zip"
        )
        response = run(response=response)
        self.assertFalse(response.has_header("Content-Encoding"))


def lessons_view(request):
    return JsonResponse({"results": LESSONS})


class ProbeUrls:
    urlpatterns = (path("compression-probe/", lessons_view),)


class SettingsWiringTests(SimpleTestCase):
    def test_replaces_gzip_middleware_in_the_same_spot(self):
        middleware = list(settings.MIDDLEWARE)
        name = "apps.core.middleware.compression.AdaptiveCompressionMiddleware"
        self.assertNotIn("django.middleware.gzip.GZipMiddleware", middleware)
        self.assertEqual(middleware.count(name), 1)
        index = middleware.index(name)
        self.assertEqual(
            middleware[index - 1], "whitenoise.middleware.WhiteNoiseMiddleware"
        )
        self.assertEqual(
            middleware[index + 1],
            "django.contrib.sessions.middleware.SessionMiddleware",
        )

    def test_importable_from_the_middleware_package(self):
        from apps.core.middleware import AdaptiveCompressionMiddleware as exported

        self.assertIs(exported, AdaptiveCompressionMiddleware)


@override_settings(ROOT_URLCONF=ProbeUrls)
class FullStackTests(TestCase):
    """A request through the real MIDDLEWARE list from settings."""

    def get(self, **headers) -> Any:
        return self.client.get("/compression-probe/", **headers)

    def test_brotli_through_the_stack(self):
        response = self.get(HTTP_ACCEPT_ENCODING=BROWSER)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Encoding"], "br")
        self.assertIn("accept-encoding", vary(response))
        self.assertEqual(
            json.loads(brotli.decompress(response.content)), {"results": LESSONS}
        )

    def test_gzip_and_identity_through_the_stack(self):
        response = self.get(HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(response["Content-Encoding"], "gzip")
        self.assertEqual(
            json.loads(gzip.decompress(response.content)), {"results": LESSONS}
        )

        response = self.get()
        self.assertFalse(response.has_header("Content-Encoding"))
        self.assertEqual(response.json(), {"results": LESSONS})
