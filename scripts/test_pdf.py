import os
import django
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.progress.services.pdf_report_service import PDFReportGenerator

User = get_user_model()
user = User.objects.first()

if user:
    generator = PDFReportGenerator(user)
    pdf_bytes = generator.generate()
    
    with open("sample_progress_report.pdf", "wb") as f:
        f.write(pdf_bytes)
        
    print(f"Generated PDF for {user.username} at sample_progress_report.pdf")
else:
    print("No user found")
