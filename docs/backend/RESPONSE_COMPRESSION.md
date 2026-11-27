# Response Compression

API responses are compressed by `AdaptiveCompressionMiddleware`
(`backend/apps/core/middleware/compression.py`, issue #3515). It sits where
Django's `GZipMiddleware` used to be in `MIDDLEWARE`, right after WhiteNoise, so
static files still come pre-compressed from WhiteNoise and never reach it.

## What it does

- Picks `br` or `gzip` from `Accept-Encoding`, honouring q-values. `q=0` means
  "not acceptable", the highest q wins and a tie goes to `br`. When neither is
  acceptable (or the header is missing) the body is sent as is.
- Leaves bodies under `COMPRESSION_MIN_SIZE` bytes alone (default 1024).
- Skips responses that already have a `Content-Encoding`, partial content (206,
  `Content-Range`), responses that offer byte ranges (`Accept-Ranges: bytes`, the
  export downloads, so resuming keeps working), `text/event-stream` (the AI tutor
  stream would stall in the compressor's buffer) and types that are already
  compressed: `audio/*`, `video/*`, `image/*` except SVG, zip/gzip/brotli/xz/7z/rar
  archives, `font/woff*` and `application/octet-stream`.
- Streams `StreamingHttpResponse` bodies (sync and async) chunk by chunk instead of
  buffering them. Brotli streams use a 256 KB window and flush every 64 KB of
  input, so output starts right away and each stream holds a few MB at most.
- Updates `Content-Length` (dropped for streams), turns a strong `ETag` weak and adds
  `Vary: Accept-Encoding` to every response that could have been compressed.

## BREACH

Django 4.2 added "Heal The BREACH" padding to `GZipMiddleware`: every gzip body gets
0-99 random bytes in its file name field, so the compressed size leaks less. The
gzip path keeps exactly that. Brotli has no file name field, so the br path writes
the same 0-99 random bytes as a metadata block (RFC 7932 section 9.2) that decoders
skip. It is a mitigation, not a fix.

## Settings

| Setting / env var            | Default | Meaning                                  |
| ---------------------------- | ------- | ---------------------------------------- |
| `COMPRESSION_MIN_SIZE`       | 1024    | smallest body (bytes) that is compressed |
| `COMPRESSION_BROTLI_QUALITY` | 5       | Brotli quality, 0-11                     |

gzip always uses level 6, the same as Django.

## Benchmark

`cd backend && python scripts/benchmark_compression.py` runs payloads built from
`frontend/public/content` through the middleware and prints size and CPU time per
response. A run on an 8 CPU x86_64 box (Python 3.12, brotli 1.2.1, shared and busy,
so read the times as rough):

| payload                       | raw     | gzip            | br q5           | br q11           |
| ----------------------------- | ------- | --------------- | --------------- | ---------------- |
| leaderboard page (100 rows)   | 10,210  | 1,902 / 0.08 ms | 1,589 / 0.13 ms | 1,325 / 9.3 ms   |
| curriculum.json (roadmap)     | 26,374  | 6,630 / 0.51 ms | 6,309 / 0.48 ms | 5,324 / 28 ms    |
| all lessons with their bodies | 98,805  | 32,939 / 3.4 ms | 31,609 / 2.1 ms | 27,565 / 109 ms  |

Bytes sent / CPU per response. A body under the threshold costs about 3 µs. On the
curriculum payloads quality 5 is 4-5% smaller than gzip and no slower; on small
bodies it costs a few hundredths of a millisecond more. The 20-30% gain often quoted
for Brotli only shows up at quality 11 (16-30% here), which takes about 50 times
the CPU of quality 5 and is not worth it per request.
