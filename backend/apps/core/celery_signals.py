import logging

from celery.signals import (
    before_task_publish,
    task_postrun,
    task_prerun,
    worker_init,
    worker_process_init,
)

from apps.core.middleware.request_id import (
    _thread_locals,
    get_correlation_id,
    get_request_id,
)

logger = logging.getLogger(__name__)


@before_task_publish.connect
def add_request_id_to_task(headers=None, **kwargs):
    req_id = get_correlation_id() or get_request_id()
    if req_id and headers is not None:
        headers["x-request-id"] = req_id
        headers["x-correlation-id"] = req_id
        headers["correlation_id"] = req_id
    if headers is not None:
        try:
            from opentelemetry import propagate

            propagate.inject(headers)
        except Exception:
            pass


@worker_init.connect
@worker_process_init.connect
def setup_tracing_in_worker(**kwargs):
    # Workers do not load wsgi.py/asgi.py; this is a no-op unless OTEL_ENABLED is true.
    # worker_process_init covers prefork children when Django is set up after worker_init.
    from config.opentelemetry import setup_opentelemetry

    setup_opentelemetry()


@task_prerun.connect
def set_request_id_in_task(task_id, task, *args, **kwargs):
    # task.request holds the headers passed to the task
    req_id = (
        getattr(task.request, "correlation_id", None)
        or getattr(task.request, "x-correlation-id", None)
        or getattr(task.request, "x-request-id", None)
    )
    if not req_id and hasattr(task.request, "headers") and task.request.headers:
        req_id = (
            task.request.headers.get("correlation_id")
            or task.request.headers.get("x-correlation-id")
            or task.request.headers.get("x-request-id")
        )

    if req_id:
        _thread_locals.request_id = req_id
        _thread_locals.correlation_id = req_id
        logger.info(
            f"[Celery] Task {getattr(task, 'name', 'unknown')}[{task_id}] running with Correlation-ID: {req_id}"
        )
    else:
        # If no request_id, generate one for the background task
        import uuid

        gen_id = f"celery-{uuid.uuid4()}"
        _thread_locals.request_id = gen_id
        _thread_locals.correlation_id = gen_id


@task_postrun.connect
def cleanup_request_id_in_task(task_id, task, *args, **kwargs):
    if hasattr(_thread_locals, "request_id"):
        _thread_locals.request_id = None
    if hasattr(_thread_locals, "correlation_id"):
        _thread_locals.correlation_id = None
