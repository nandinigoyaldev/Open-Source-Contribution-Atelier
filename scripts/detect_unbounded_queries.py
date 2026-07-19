#!/usr/bin/env python
"""
Script to detect unbounded database queries.
Run: python scripts/detect_unbounded_queries.py
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tests.test_unbounded_queries import UnboundedQueryDetector


def main():
    print("🔍 Detecting unbounded database queries...")
    print("="*80)
    
    detector = UnboundedQueryDetector()
    issues = detector.run_all_checks()
    
    if not issues:
        print("✅ No unbounded query issues detected!")
        return 0
    
    print(f"\n⚠️  Found {len(issues)} issues:\n")
    
    for issue in issues:
        print(f"  📍 {issue['url']}")
        print(f"     Type: {issue['type']}")
        print(f"     View: {issue['callback']}")
        print(f"     Severity: {issue['severity']}")
        print(f"     {issue['description']}")
        print()
    
    print("="*80)
    print(f"Total issues: {len(issues)}")
    
    # Count by severity
    critical = len([i for i in issues if i.get('severity') == 'high'])
    if critical > 0:
        print(f"❌ Found {critical} critical issues that need to be fixed!")
        return 1
    
    print("⚠️  Found issues that should be reviewed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
    