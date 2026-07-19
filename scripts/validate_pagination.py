#!/usr/bin/env python
"""
Script to validate pagination consistency.
Run: python scripts/validate_pagination.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests.test_pagination_consistency import PaginationValidator
from rest_framework.test import APIClient
from django.contrib.auth.models import User


def main():
    print("🔍 Validating pagination consistency...")
    print("="*80)
    
    # Create test user
    user, _ = User.objects.get_or_create(
        username='testuser',
        defaults={'password': 'testpass123'}
    )
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    validator = PaginationValidator()
    issues = validator.run_checks(client, user)
    
    if not issues:
        print("✅ All endpoints have consistent pagination!")
        return 0
    
    print(f"\n⚠️  Found {len(issues)} pagination issues:\n")
    
    for issue in issues:
        print(f"  📍 {issue['url']}")
        print(f"     Type: {issue['type']}")
        print(f"     Severity: {issue['severity']}")
        print(f"     {issue['description']}")
        print()
    
    print("="*80)
    print(f"Total issues: {len(issues)}")
    
    critical = len([i for i in issues if i.get('severity') == 'high'])
    if critical > 0:
        print(f"❌ Found {critical} critical issues that need to be fixed!")
        return 1
    
    print("⚠️  Found issues that should be reviewed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())