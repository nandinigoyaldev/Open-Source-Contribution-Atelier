FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && rm -rf /root/.cache/pip


FROM python:3.11-slim AS production

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appgroup worker.py .

USER appuser

CMD ["celery", "-A", "worker.app", "worker", "--loglevel=info"]
