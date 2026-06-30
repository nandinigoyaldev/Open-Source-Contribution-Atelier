FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY worker.py .

# Run celery worker
CMD ["celery", "-A", "worker.app", "worker", "--loglevel=info"]
