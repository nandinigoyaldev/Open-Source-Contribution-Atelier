# ├─────────────────────────────────────────────────────┤
# │  Stage 1 — builder                                  │
# │  Install production dependencies into /install      │
# ├─────────────────────────────────────────────────────┤
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt \
    && rm -rf /root/.cache/pip

# ├─────────────────────────────────────────────────────┤
# │  Stage 2 — production                               │
# │  Minimal runtime image with non-root user           │
# ├─────────────────────────────────────────────────────┤
FROM python:3.11-slim AS production

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appgroup manage.py ./
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup apps/ ./apps/

EXPOSE 8000
USER appuser

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
