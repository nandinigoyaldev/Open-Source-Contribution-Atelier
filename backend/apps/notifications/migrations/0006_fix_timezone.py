# Generated manually to fix naive timezone offsets

from django.db import migrations
from django.utils import timezone
from datetime import timedelta

def fix_notification_created_at(apps, schema_editor):
    Notification = apps.get_model('notifications', 'Notification')
    
    # We want to convert the created_at to proper UTC by assuming it was recorded
    # as naive local time. However, timezone.now() vs datetime.now() gives us
    # the offset if it was recorded wrongly.
    # Actually, in PostgreSQL with USE_TZ=True, Django stores timestamp with time zone.
    # If datetime.now() was used (naive), Django's ORM assumes it is in the current
    # default time zone (UTC) and saves it as is, which means the time saved is shifted
    # by the server's local UTC offset.
    # Wait, if USE_TZ=True and TIME_ZONE='UTC', and datetime.now() is called, 
    # datetime.now() returns the local time. If the server is in Oregon (UTC-7), 
    # it returns UTC-7 time. Django then assumes it's UTC because TIME_ZONE='UTC',
    # and stores it as UTC. So the stored time is 7 hours behind actual UTC.
    # Example: actual UTC time is 15:00. datetime.now() gives 08:00. 
    # Django stores 08:00 UTC. It's shifted by exactly the server's offset.
    # We can calculate the server's offset by comparing datetime.now() and datetime.utcnow()
    # at the time of migration, but this only works if the offset hasn't changed.
    # Let's write a data migration that just notes this, or does a safe migration.
    
    import datetime
    now_naive = datetime.datetime.now()
    now_utc = datetime.datetime.utcnow()
    offset_seconds = (now_utc - now_naive).total_seconds()
    
    if abs(offset_seconds) > 60:
        offset = timedelta(seconds=offset_seconds)
        
        # Add offset to created_at to fix it
        from django.db.models import F
        Notification.objects.update(created_at=F('created_at') + offset)

def reverse_fix(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0005_notificationpreference'),
    ]

    operations = [
        migrations.RunPython(fix_notification_created_at, reverse_fix),
    ]
