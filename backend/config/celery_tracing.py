"""
Celery integration for distributed tracing.
Propagates correlation IDs to Celery tasks.
"""

from celery import Task
from celery.signals import task_prerun, task_postrun, task_failure
from config.middleware import get_current_correlation_id
import logging

logger = logging.getLogger(__name__)

class TracingTask(Task):
    """Base task class with tracing support."""
    
    def __call__(self, *args, **kwargs):
        """Execute task with correlation ID propagation."""
        correlation_id = kwargs.pop('correlation_id', None)
        
        # If no correlation ID, generate one
        if not correlation_id:
            correlation_id = get_current_correlation_id() or str(uuid.uuid4())
        
        # Store in thread-local for logging
        from config.middleware import set_current_correlation_id, clear_current_context
        set_current_correlation_id(correlation_id)
        
        try:
            result = super().__call__(*args, **kwargs)
            return result
        finally:
            clear_current_context()


@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extra):
    """Handle task pre-run - add correlation ID to logs."""
    correlation_id = kwargs.get('correlation_id')
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    # Add to task context
    from config.middleware import set_current_correlation_id
    set_current_correlation_id(correlation_id)
    
    logger.info(
        f"Celery task started: {task.name}",
        extra={'correlation_id': correlation_id, 'task_id': task_id}
    )


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, state, **extra):
    """Handle task post-run."""
    from config.middleware import get_current_correlation_id
    correlation_id = get_current_correlation_id()
    
    logger.info(
        f"Celery task completed: {task.name}",
        extra={
            'correlation_id': correlation_id,
            'task_id': task_id,
            'state': state
        }
    )


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **extra):
    """Handle task failure."""
    from config.middleware import get_current_correlation_id
    correlation_id = get_current_correlation_id()
    
    logger.error(
        f"Celery task failed: {exception}",
        extra={
            'correlation_id': correlation_id,
            'task_id': task_id,
            'exception_type': type(exception).__name__,
            'traceback': traceback
        }
    )