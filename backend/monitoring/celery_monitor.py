from prometheus_client import Counter, Gauge, Histogram, start_http_server
import time
from celery import Celery
import os

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

    def update_metrics(self):
        """Update all metrics"""
        self.update_queue_sizes()
        self.update_worker_count()

    def update_queue_sizes(self):
        """Update queue size metrics"""
        for queue in self.queues:
            try:
                from celery import current_app
                from celery.utils import term

                inspect = current_app.control.inspect()
                reserved = inspect.reserved()
                if reserved:
                    count = sum(1 for v in reserved.values() if v)
                    queue_size.labels(queue_name=queue).set(count)
                else:
                    queue_size.labels(queue_name=queue).set(0)
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
