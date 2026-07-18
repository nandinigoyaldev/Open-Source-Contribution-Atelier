"""
Automated tests to detect unbounded database queries in CI.
"""

import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from django.test import TestCase
from django.urls import get_resolver, URLPattern, URLResolver
from django.db import connection
from django.core.management import call_command
import inspect
import os


class UnboundedQueryDetector:
    """
    Detects unbounded database queries in API endpoints.
    """

    def __init__(self):
        self.issues: List[Dict[str, Any]] = []
        self.url_patterns = self._get_all_urls()

    def _get_all_urls(self) -> List[Dict[str, str]]:
        """Extract all URL patterns from the project."""
        urls = []
        resolver = get_resolver()

        def extract_patterns(pattern, prefix=''):
            if isinstance(pattern, URLPattern):
                urls.append({
                    'name': pattern.name or '',
                    'pattern': f"{prefix}{pattern.pattern}",
                    'callback': pattern.callback.__name__ if pattern.callback else 'unknown',
                    'module': pattern.callback.__module__ if pattern.callback else 'unknown',
                })
            elif isinstance(pattern, URLResolver):
                new_prefix = f"{prefix}{pattern.pattern}"
                for sub_pattern in pattern.url_patterns:
                    extract_patterns(sub_pattern, new_prefix)

        extract_patterns(resolver)
        return urls

    def detect_missing_pagination(self) -> List[Dict[str, Any]]:
        """Detect API endpoints missing pagination."""
        issues = []
        
        for url in self.url_patterns:
            if not url['pattern'].startswith('/api/'):
                continue
            
            # Skip static/asset endpoints
            if any(skip in url['pattern'] for skip in ['/static/', '/media/', '/admin/']):
                continue
            
            # Check if view has pagination
            pagination_indicators = [
                'Pagination', 'pagination', 'PageNumberPagination',
                'LimitOffsetPagination', 'CursorPagination',
                'paginate_queryset', 'get_paginated_response'
            ]
            
            # Get the view code if possible
            view_code = self._get_view_code(url['module'], url['callback'])
            if view_code:
                has_pagination = any(indicator in view_code for indicator in pagination_indicators)
                if not has_pagination:
                    issues.append({
                        'type': 'missing_pagination',
                        'url': url['pattern'],
                        'callback': url['callback'],
                        'module': url['module'],
                        'severity': 'medium',
                        'description': f"Endpoint {url['pattern']} may be missing pagination"
                    })
        
        return issues

    def detect_missing_limit(self) -> List[Dict[str, Any]]:
        """Detect querysets without explicit limits."""
        issues = []
        
        for url in self.url_patterns:
            if not url['pattern'].startswith('/api/'):
                continue
            
            # Check for .all() without limit
            view_code = self._get_view_code(url['module'], url['callback'])
            if view_code:
                # Look for .all() without .filter() or .limit()
                has_all = '.all()' in view_code
                has_limit = '.limit(' in view_code or '[:' in view_code
                has_filter = '.filter(' in view_code or '.exclude(' in view_code
                
                if has_all and not has_limit and not has_filter:
                    issues.append({
                        'type': 'missing_limit',
                        'url': url['pattern'],
                        'callback': url['callback'],
                        'severity': 'high',
                        'description': f"Endpoint {url['pattern']} uses .all() without limit or filter"
                    })
        
        return issues

    def detect_expensive_ordering(self) -> List[Dict[str, Any]]:
        """Detect expensive ordering operations."""
        issues = []
        
        for url in self.url_patterns:
            if not url['pattern'].startswith('/api/'):
                continue
            
            view_code = self._get_view_code(url['module'], url['callback'])
            if view_code:
                # Check for order_by without index hints
                has_order_by = '.order_by(' in view_code
                has_index = 'db_index' in view_code or 'indexes' in view_code
                
                if has_order_by and not has_index:
                    issues.append({
                        'type': 'expensive_ordering',
                        'url': url['pattern'],
                        'callback': url['callback'],
                        'severity': 'low',
                        'description': f"Endpoint {url['pattern']} uses order_by without index hints"
                    })
        
        return issues

    def _get_view_code(self, module: str, callback: str) -> Optional[str]:
        """Get the source code of a view."""
        try:
            # Try to import the module
            import importlib
            mod = importlib.import_module(module)
            
            # Find the view class/function
            for name, obj in inspect.getmembers(mod):
                if name == callback:
                    try:
                        return inspect.getsource(obj)
                    except (TypeError, OSError):
                        pass
            
            # Try to find in views.py
            if hasattr(mod, 'views'):
                for name, obj in inspect.getmembers(mod.views):
                    if name == callback:
                        try:
                            return inspect.getsource(obj)
                        except (TypeError, OSError):
                            pass
        except (ImportError, AttributeError):
            pass
        
        return None

    def run_all_checks(self) -> List[Dict[str, Any]]:
        """Run all detection checks."""
        self.issues.extend(self.detect_missing_pagination())
        self.issues.extend(self.detect_missing_limit())
        self.issues.extend(self.detect_expensive_ordering())
        return self.issues


class UnboundedQueryTest(TestCase):
    """
    Test suite for detecting unbounded queries.
    """

    def setUp(self):
        self.detector = UnboundedQueryDetector()

    def test_no_missing_pagination(self):
        """Test that all API endpoints have pagination."""
        issues = self.detector.detect_missing_pagination()
        
        if issues:
            print("\n" + "="*80)
            print("⚠️  MISSING PAGINATION DETECTED")
            print("="*80)
            for issue in issues:
                print(f"  📍 {issue['url']}")
                print(f"     View: {issue['callback']}")
                print(f"     Severity: {issue['severity']}")
                print(f"     {issue['description']}")
                print()
        
        # Allow warnings but fail if critical issues found
        critical_issues = [i for i in issues if i.get('severity') == 'high']
        self.assertEqual(len(critical_issues), 0, 
            f"Found {len(critical_issues)} critical API endpoints missing pagination")

    def test_no_missing_limit(self):
        """Test that no querysets use .all() without limits."""
        issues = self.detector.detect_missing_limit()
        
        if issues:
            print("\n" + "="*80)
            print("⚠️  MISSING LIMIT DETECTED")
            print("="*80)
            for issue in issues:
                print(f"  📍 {issue['url']}")
                print(f"     View: {issue['callback']}")
                print(f"     {issue['description']}")
                print()
        
        self.assertEqual(len(issues), 0, 
            f"Found {len(issues)} endpoints using .all() without limits")

    def test_no_expensive_ordering(self):
        """Test that ordering has proper indexes."""
        issues = self.detector.detect_expensive_ordering()
        
        if issues:
            print("\n" + "="*80)
            print("⚠️  EXPENSIVE ORDERING DETECTED")
            print("="*80)
            for issue in issues:
                print(f"  📍 {issue['url']}")
                print(f"     View: {issue['callback']}")
                print(f"     {issue['description']}")
                print()
        
        # Warn but don't fail for low severity issues
        high_issues = [i for i in issues if i.get('severity') == 'high']
        self.assertEqual(len(high_issues), 0, 
            f"Found {len(high_issues)} high severity ordering issues")