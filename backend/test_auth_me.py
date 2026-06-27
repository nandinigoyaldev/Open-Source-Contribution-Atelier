import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
c = Client()
try:
    response = c.get('/api/auth/me/')
    print(response.status_code)
    print(response.content)
except Exception as e:
    import traceback
    traceback.print_exc()
