import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User

username = os.environ.get("DJANGO_ADMIN_USER", "")
email = os.environ.get("DJANGO_ADMIN_EMAIL", "")
password = os.environ.get("DJANGO_ADMIN_PASSWORD", "")

if not all([username, email, password]):
    raise SystemExit(
        "ERROR: Set DJANGO_ADMIN_USER, DJANGO_ADMIN_EMAIL, "
        "and DJANGO_ADMIN_PASSWORD env vars before running this script."
    )

user, created = User.objects.get_or_create(username=username, email=email)
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()
print(f"Admin {'created' if created else 'updated'}: {user.username}")
