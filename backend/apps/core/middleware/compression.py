"""
Response compression that picks Brotli or gzip per request (issue #3515).

``AdaptiveCompressionMiddleware`` takes the place of
``django.middleware.gzip.GZipMiddleware`` in ``settings.MIDDLEWARE``:

* it reads ``Accept-Encoding`` with its q-values and answers with ``br`` or ``gzip``
  (on a tie the server prefers ``br``). A coding with ``q=0``, or one the header does
  not list (and no ``*`` covers), is not acceptable; when nothing is, the body is sent
  as is (identity). No header at all also means identity, like ``GZipMiddleware``.
* bodies under ``settings.COMPRESSION_MIN_SIZE`` bytes (default 1024) are left alone.
* responses that already have a ``Content-Encoding``, partial content (206 or a
  ``Content-Range`` header), server-sent events and types that are already compressed
  (audio, video, raster images, archives, ``application/octet-stream`` downloads) are
  skipped. So are responses that offer byte ranges (``Accept-Ranges: bytes``, like
  the export downloads in apps/data_exports): a resumed download gets a range of the
  identity file, so the first response must be identity too, with its Content-Length
  and strong ETag intact.
* streaming responses (sync and async) are compressed chunk by chunk as they are sent,
  so the body is never buffered in memory. Left alone, Brotli holds back several MB
  of input before its first output, so streams use a 256 KB window and a flush every
  64 KB of input (gzip already sends output as it goes). Their ``Content-Length`` is
  dropped because the compressed size is not known up front. Buffered responses get a
  new ``Content-Length`` and keep the original body when compressing would not shrink
  it.
* a strong ``ETag`` becomes weak once the body is compressed (RFC 9110 section 8.8.1),
  the same thing ``GZipMiddleware`` does.
* ``Vary: Accept-Encoding`` is added to every response that could have been compressed,
  also when this request got identity, so shared caches keep the variants apart.

BREACH: since Django 4.2 ``GZipMiddleware`` adds 0-99 random bytes to every gzip body
("Heal The BREACH", a random length FNAME field) so the compressed length says less
about secrets in the page. The gzip path here keeps that exact trick. Brotli has no
file name field, so the br path puts the same 0-99 random bytes in a metadata
meta-block (RFC 7932 section 9.2) at the start of the stream; decoders skip metadata,
so the decoded body is unchanged. This is a mitigation, not a fix: CSRF token masking
and not mixing secrets with user input in one response still matter.
"""

import secrets
from gzip import GzipFile

from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.text import StreamingBuffer

try:  # installed through whitenoise[brotli]; without it only gzip is offered
    import brotli
except ImportError:  # pragma: no cover
    brotli = None

DEFAULT_MIN_SIZE = 1024
DEFAULT_BROTLI_QUALITY = 5
GZIP_LEVEL = 6  # same level as django.utils.text.compress_string
MAX_RANDOM_BYTES = 100  # same as GZipMiddleware.max_random_bytes
STREAM_BROTLI_LGWIN = 18  # 256 KB window for streams instead of the 4 MB default
STREAM_FLUSH_BYTES = 64 * 1024

# Media types that are already compressed, or must reach the client unbuffered.
SKIPPED_CONTENT_TYPES = frozenset(
    {
        "application/octet-stream",  # opaque downloads (apps/uploads falls back to it)
        "application/zip",
        "application/gzip",
        "application/x-gzip",
        "application/x-brotli",
        "application/zstd",
        "application/x-bzip2",
        "application/x-xz",
        "application/x-7z-compressed",
        "application/x-rar-compressed",
        "application/vnd.rar",
        "font/woff",
        "font/woff2",
        # Compressors hold data back until they have enough of it, which would stall
        # the AI tutor's event stream (apps/ai_tutor/views.py).
        "text/event-stream",
    }
)
SKIPPED_CONTENT_TYPE_PREFIXES = ("audio/", "video/", "image/")
COMPRESSIBLE_IMAGE_TYPES = frozenset({"image/svg+xml"})


def parse_accept_encoding(header):
    """
    Return ``{coding: q}`` for an ``Accept-Encoding`` value.

    Codings are lower-cased and ``x-gzip`` counts as ``gzip`` (RFC 9110 section
    8.4.1.3). A q-value that is not a number between 0 and 1 counts as 0, so a broken
    header never turns compression on. When a coding is listed twice the first one wins.
    """
    preferences = {}
    for item in (header or "").split(","):
        coding, _, params = item.partition(";")
        coding = coding.strip().lower()
        if not coding:
            continue
        if coding == "x-gzip":
            coding = "gzip"
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
                break
        if not 0.0 <= quality <= 1.0:  # also catches nan
            quality = 0.0
        preferences.setdefault(coding, quality)
    return preferences


def available_encodings():
    """Codings this server can produce, in its own order of preference."""
    return ("br", "gzip") if brotli is not None else ("gzip",)


def choose_encoding(header, available=None):
    """
    Pick the content coding for a response, or ``None`` for identity.

    The acceptable coding with the highest q-value wins; on a tie the order of
    ``available`` decides, so ``br`` beats ``gzip``. ``*`` gives its q-value to every
    coding the header does not name.
    """
    if not header:
        return None
    preferences = parse_accept_encoding(header)
    wildcard = preferences.get("*", 0.0)
    best, best_quality = None, 0.0
    for coding in available or available_encodings():
        quality = preferences.get(coding, wildcard)
        if quality > best_quality:
            best, best_quality = coding, quality
    return best


class _GzipEncoder:
    """Incremental gzip with Django's random length FNAME padding."""

    def __init__(self, max_random_bytes):
        self._buffer = StreamingBuffer()
        filename = (
            b"a" * secrets.randbelow(max_random_bytes) if max_random_bytes else None
        )
        self._file = GzipFile(
            filename=filename,
            mode="wb",
            compresslevel=GZIP_LEVEL,
            fileobj=self._buffer,
            mtime=0,
        )

    def start(self):
        return self._buffer.read()  # the gzip header, FNAME padding included

    def compress(self, chunk):
        self._file.write(chunk)
        return self._buffer.read()

    def finish(self):
        self._file.close()
        return self._buffer.read()


class _BrotliEncoder:
    """Incremental Brotli with random length metadata padding."""

    def __init__(self, max_random_bytes, quality, streaming=False):
        if brotli is None:  # choose_encoding never offers br without the package
            raise RuntimeError("the brotli package is not installed")
        if streaming:
            self._compressor = brotli.Compressor(
                quality=quality, lgwin=STREAM_BROTLI_LGWIN
            )
        else:
            self._compressor = brotli.Compressor(quality=quality)
        self._flush_every = STREAM_FLUSH_BYTES if streaming else 0
        self._unflushed = 0
        self._padding = secrets.randbelow(max_random_bytes) if max_random_bytes else 0

    def start(self):
        # Flushing before any input writes the stream header and byte-aligns it, so a
        # metadata meta-block can follow. Its header (RFC 7932 section 9.2) is
        # ISLAST=0, MNIBBLES=0 (stored as 3), a reserved 0 bit, MSKIPBYTES=1 and
        # MSKIPLEN-1 in 8 bits, padded with zero bits to two bytes.
        head = self._compressor.flush()
        if not self._padding:
            return head
        size = min(self._padding, 256)  # one MSKIPBYTES byte holds up to 256
        meta = (3 << 1) | (1 << 4) | ((size - 1) << 6)
        return head + meta.to_bytes(2, "little") + b"\0" * size

    def compress(self, chunk):
        data = self._compressor.process(chunk)
        if self._flush_every:
            self._unflushed += len(chunk)
            if self._unflushed >= self._flush_every:
                data += self._compressor.flush()
                self._unflushed = 0
        return data

    def finish(self):
        return self._compressor.finish()


def make_encoder(
    coding, max_random_bytes=MAX_RANDOM_BYTES, brotli_quality=None, streaming=False
):
    if coding == "br":
        if brotli_quality is None:
            brotli_quality = DEFAULT_BROTLI_QUALITY
        return _BrotliEncoder(max_random_bytes, brotli_quality, streaming)
    if coding == "gzip":
        return _GzipEncoder(max_random_bytes)
    raise ValueError(f"unsupported content coding: {coding!r}")


def compress_bytes(content, coding, max_random_bytes=MAX_RANDOM_BYTES, **options):
    """Compress a whole body in one go with the given coding."""
    encoder = make_encoder(coding, max_random_bytes, **options)
    return encoder.start() + encoder.compress(content) + encoder.finish()


def _compress_iterator(chunks, new_encoder):
    encoder = new_encoder()
    yield encoder.start()
    for chunk in chunks:
        data = encoder.compress(chunk)
        if data:
            yield data
    yield encoder.finish()


async def _compress_async_iterator(chunks, new_encoder):
    encoder = new_encoder()
    yield encoder.start()
    async for chunk in chunks:
        data = encoder.compress(chunk)
        if data:
            yield data
    yield encoder.finish()


def _media_type(response):
    return response.get("Content-Type", "").split(";", 1)[0].strip().lower()


def is_skipped_content_type(media_type):
    if media_type in SKIPPED_CONTENT_TYPES:
        return True
    return media_type.startswith(SKIPPED_CONTENT_TYPE_PREFIXES) and (
        media_type not in COMPRESSIBLE_IMAGE_TYPES
    )


class AdaptiveCompressionMiddleware(MiddlewareMixin):
    """
    Compress responses with Brotli or gzip, whichever the client prefers.

    See the module docstring for the rules. Settings:
    ``COMPRESSION_MIN_SIZE`` (bytes, default 1024) and ``COMPRESSION_BROTLI_QUALITY``
    (0-11, default 5).
    """

    max_random_bytes = MAX_RANDOM_BYTES

    def process_response(self, request, response):
        if not self._can_compress(response):
            return response

        # From here the body depends on Accept-Encoding, whatever this client sent.
        patch_vary_headers(response, ("Accept-Encoding",))

        coding = choose_encoding(request.META.get("HTTP_ACCEPT_ENCODING", ""))
        if coding is None:
            return response

        options = {}
        if coding == "br":
            options["brotli_quality"] = getattr(
                settings, "COMPRESSION_BROTLI_QUALITY", DEFAULT_BROTLI_QUALITY
            )

        if response.streaming:

            def new_encoder():
                return make_encoder(
                    coding, self.max_random_bytes, streaming=True, **options
                )

            # Take the iterator now: the wrapper only runs when the body is sent, and
            # by then streaming_content is the wrapper itself.
            chunks = response.streaming_content
            if response.is_async:
                response.streaming_content = _compress_async_iterator(
                    chunks, new_encoder
                )
            else:
                response.streaming_content = _compress_iterator(chunks, new_encoder)
            # The compressed size is only known once the last chunk is out.
            del response.headers["Content-Length"]
        else:
            compressed = compress_bytes(
                response.content, coding, self.max_random_bytes, **options
            )
            if len(compressed) >= len(response.content):
                return response
            response.content = compressed
            response.headers["Content-Length"] = str(len(compressed))

        # Same as GZipMiddleware: a strong ETag names exact bytes, which changed.
        etag = response.get("ETag")
        if etag and etag.startswith('"'):
            response.headers["ETag"] = "W/" + etag
        response.headers["Content-Encoding"] = coding
        return response

    def _can_compress(self, response):
        if response.has_header("Content-Encoding"):
            return False
        # Byte ranges are cut from the identity body, so neither a range nor the full
        # response of a resource that offers ranges can be re-encoded.
        if response.status_code == 206 or response.has_header("Content-Range"):
            return False
        if "bytes" in response.get("Accept-Ranges", "").lower():
            return False
        if is_skipped_content_type(_media_type(response)):
            return False

        min_size = getattr(settings, "COMPRESSION_MIN_SIZE", DEFAULT_MIN_SIZE)
        if response.streaming:
            # Only a declared length (FileResponse sets one) tells us the size.
            length = response.get("Content-Length", "")
            return not (length.isdigit() and int(length) < min_size)
        return len(response.content) >= min_size
