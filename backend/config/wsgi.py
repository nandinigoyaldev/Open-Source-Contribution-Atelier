import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config.opentelemetry import setup_opentelemetry

setup_opentelemetry()

application = get_wsgi_application()
