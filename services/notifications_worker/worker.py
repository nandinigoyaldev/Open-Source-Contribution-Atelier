import os
import time
import logging
from celery import Celery

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Fetch Redis URL from environment or use default for local testing
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Initialize standalone Celery app
app = Celery("notifications_worker", broker=REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@app.task(name="tasks.send_bulk_email")
def send_bulk_email(payload: dict):
    """
    Simulates sending a bulk email based on a payload from the monolith.
    """
    template_id = payload.get("template_id")
    recipients = payload.get("recipients", [])
    data = payload.get("data", {})

    logger.info(
        f"Received request to send '{template_id}' email to {len(recipients)} recipients."
    )

    # Simulate an expensive operation (e.g. SMTP sending)
    time.sleep(2)

    for recipient in recipients:
        logger.info(f"Email successfully dispatched to {recipient} with data: {data}")

    return {"status": "success", "recipients_count": len(recipients)}
