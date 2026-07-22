from django.utils import timezone

def utc_now():
    return timezone.now()

def today():
    return timezone.localdate()
