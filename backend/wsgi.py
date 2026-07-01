import os
import sys

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Vercel requires the WSGI application to be named 'app'
app = get_wsgi_application()
