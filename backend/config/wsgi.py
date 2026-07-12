import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.telemetry import setup_telemetry

setup_telemetry()

application = get_wsgi_application()
