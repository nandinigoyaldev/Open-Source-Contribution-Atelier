from celery import shared_task
from django.core.management import call_command


@shared_task
def sync_oss_issues():
    """Celery task to sync OSS issues."""
    call_command("sync_oss_issues")
