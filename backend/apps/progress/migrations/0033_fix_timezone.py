# Generated manually to fix naive timezone offsets

from django.db import migrations
from django.utils import timezone
from datetime import timedelta
import datetime

def fix_progress_dailyactivity_date(apps, schema_editor):
    DailyActivity = apps.get_model('progress', 'DailyActivity')
    
    # Calculate offset
    now_naive = datetime.datetime.now()
    now_utc = datetime.datetime.utcnow()
    offset_seconds = (now_utc - now_naive).total_seconds()
    
    if abs(offset_seconds) > 60:
        offset = timedelta(seconds=offset_seconds)
        
        # We need to update date by checking if shifting the created_at by offset 
        # changes the local date.
        for activity in DailyActivity.objects.all():
            # assuming created_at is naive-stored-as-UTC
            actual_utc_created_at = activity.created_at + offset
            actual_local_date = actual_utc_created_at.astimezone(timezone.get_current_timezone()).date()
            if activity.date != actual_local_date:
                activity.date = actual_local_date
                activity.save(update_fields=['date'])

def reverse_fix(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('progress', '0032_season_alter_xpevent_source_type_trackmilestone_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_progress_dailyactivity_date, reverse_fix),
    ]
