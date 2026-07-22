from prometheus_client import Counter, Gauge, Histogram, start_http_server
import time
from celery import Celery
import os
import redis

app = Celery("config")

# Metrics
task_counter = Counter(
    "celery_tasks_total", "Total tasks processed", ["task_name", "status"]
)
task_duration = Histogram(
    "celery_task_duration_seconds", "Task duration in seconds", ["task_name"]
)
queue_size = Gauge("celery_queue_size", "Size of Celery queues", ["queue_name"])
active_workers = Gauge("celery_active_workers", "Number of active workers")
failed_tasks = Counter(
    "celery_failed_tasks_total", "Total failed tasks", ["task_name", "reason"]
)


class CeleryMonitor:
    def __init__(self):
        self.queues = ["default", "high_priority", "low_priority"]
        self.workers = 0
        self.redis_client = redis.Redis.from_url(
            os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        )

    def update_metrics(self):
        """Update all metrics"""
        self.update_queue_sizes()
        self.update_worker_count()
        self._check_alert_thresholds()

    def _check_alert_thresholds(self):
        """Log a warning if queue backlog or worker count crosses configured thresholds."""
        queue_threshold = int(os.getenv("CELERY_QUEUE_ALERT_THRESHOLD", 1000))

        for queue in self.queues:
            current = queue_size.labels(queue_name=queue)._value.get()
            if current is not None and current > queue_threshold:
                print(
                    f"🚨 Queue backlog alert: '{queue}' has {current} pending tasks (threshold: {queue_threshold})"
                )

        if self.workers == 0:
            print("🚨 No active Celery workers detected")

    def update_queue_sizes(self):
        """Update queue size metrics using the true per-queue Redis list length"""
        for queue in self.queues:
            try:
                count = self.redis_client.llen(queue)
                queue_size.labels(queue_name=queue).set(count)
            except Exception as e:
                print(f"Failed to get queue size for {queue}: {e}")

    def update_worker_count(self):
        """Update active worker count"""
        try:
            from celery import current_app

            inspect = current_app.control.inspect()
            stats = inspect.stats()
            if stats:
                self.workers = len(stats)
                active_workers.set(self.workers)
            else:
                active_workers.set(0)
        except Exception as e:
            print(f"Failed to get worker count: {e}")

    def track_task(self, task_name, duration, status, error=None):
        """Track task execution"""
        task_counter.labels(task_name=task_name, status=status).inc()
        task_duration.labels(task_name=task_name).observe(duration)

        if status == "failed":
            failed_tasks.labels(task_name=task_name, reason=error or "Unknown").inc()


monitor = CeleryMonitor()


# Start monitoring server (port 9090)
def start_monitoring():
    start_http_server(9090)
    print("Celery monitoring started on port 9090")


if __name__ == "__main__":
    start_monitoring()
