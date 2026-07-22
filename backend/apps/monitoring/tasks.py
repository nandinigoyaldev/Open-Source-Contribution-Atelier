from celery import shared_task
from django.core.management import call_command


@shared_task
def verify_latest_backup():
    """
    Weekly celery task to verify the latest database backup.
    """
    call_command("verify_backup")
