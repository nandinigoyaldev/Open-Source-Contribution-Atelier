from celery import Task
from celery import shared_task
import time
from monitoring.celery_monitor import monitor  # type: ignore


class MonitoredTask(Task):
    def __call__(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start_time
            monitor.track_task(self.name, duration, "success")
            return result
        except Exception as e:
            duration = time.time() - start_time
            monitor.track_task(self.name, duration, "failed", str(e))
            raise


@shared_task(base=MonitoredTask)
def example_task(data):
    return {"status": "completed"}
