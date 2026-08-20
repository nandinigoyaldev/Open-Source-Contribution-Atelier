"""Celery worker health check script for Docker Compose deployments."""

import sys
from celery import Celery

app = Celery('tasks', broker='redis://localhost:6379/0')

def check_celery_worker_health():
    try:
        # Inspect active worker nodes or ping the broker
        inspect = app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            print("Error: No active Celery workers found responding to ping/stats.")
            sys.exit(1)
            
        print("Celery worker health check passed successfully.")
        sys.exit(0)
    except Exception as exc:
        # Acceptance Criteria: Exit with status code 1 on connection failure or ping timeout
        print(f"Health check failed due to broker/worker error: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    check_celery_worker_health()
