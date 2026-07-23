import os
import django
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.notifications.signals import create_and_push_notification

User = get_user_model()
user = User.objects.first()
if user:
    create_and_push_notification(
        recipient=user,
        notif_type="alert",
        title="Edge Case Test Notification",
        message="This is a test message to verify the real-time websocket delivery.",
        meta={"test_id": "123"}
    )
    print(f"Sent notification to {user.username}")
else:
    print("No user found")
