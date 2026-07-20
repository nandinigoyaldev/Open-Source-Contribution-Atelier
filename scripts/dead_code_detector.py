#!/usr/bin/env python
"""
Dead code detection for Django and React projects.
"""

import os
import re
import ast
import json
import glob
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import importlib


class DeadCodeDetector:
    """
    Detect dead/unused code in Django and React projects.
    """

    def __init__(self, project_root: str = '.'):
        self.project_root = Path(project_root)
        self.results = {
            'unused_views': [],
            'unused_serializers': [],
            'unused_models': [],
            'unused_signals': [],
            'unused_tasks': [],
            'unused_utils': [],
            'unused_react_components': [],
            'unused_css_classes': [],
            'summary': {},
        }

    def detect_unused_django_views(self):
        """Detect unused Django views."""
        views = {}
        urls = []

        # Find all views
        for app_dir in self.project_root.glob('backend/apps/*/'):
            views_file = app_dir / 'views.py'
            if views_file.exists():
                with open(views_file, 'r') as f:
                    content = f.read()
                    # Find class-based views
                    class_pattern = r'class\s+(\w+View)\s*\('
                    for match in re.finditer(class_pattern, content):
                        view_name = match.group(1)
                        views[view_name] = str(views_file)
                    
                    # Find function-based views
                    func_pattern = r'def\s+(\w+)\s*\(.*request'
                    for match in re.finditer(func_pattern, content):
                        view_name = match.group(1)
                        views[view_name] = str(views_file)

        # Find all URL patterns
        for url_file in self.project_root.glob('backend/apps/*/urls.py'):
            with open(url_file, 'r') as f:
                content = f.read()
                # Find view references in URLs
                pattern = r"views\.(\w+)"
                for match in re.finditer(pattern, content):
                    urls.append(match.group(1))

        # Find unused views
        for view_name, file_path in views.items():
            if view_name not in urls:
                self.results['unused_views'].append({
                    'name': view_name,
                    'file': file_path,
                })

    def detect_unused_serializers(self):
        """Detect unused Django serializers."""
        serializers = {}
        references = []

        # Find all serializers
        for app_dir in self.project_root.glob('backend/apps/*/'):
            serializers_file = app_dir / 'serializers.py'
            if serializers_file.exists():
                with open(serializers_file, 'r') as f:
                    content = f.read()
                    pattern = r'class\s+(\w+Serializer)\s*\('
                    for match in re.finditer(pattern, content):
                        serializer_name = match.group(1)
                        serializers[serializer_name] = str(serializers_file)

        # Find references to serializers
        for py_file in self.project_root.glob('backend/**/*.py'):
            with open(py_file, 'r') as f:
                content = f.read()
                for serializer_name in serializers.keys():
                    if serializer_name in content:
                        references.append(serializer_name)

        # Find unused serializers
        for serializer_name, file_path in serializers.items():
            if serializer_name not in references:
                self.results['unused_serializers'].append({
                    'name': serializer_name,
                    'file': file_path,
                })

    def detect_unused_react_components(self):
        """Detect unused React components."""
        components = {}
        imports = []

        # Find all React components
        for js_file in self.project_root.glob('frontend/src/**/*.{js,jsx,ts,tsx}'):
            with open(js_file, 'r') as f:
                content = f.read()
                # Find component definitions
                pattern = r'(?:export\s+)?(?:const|function|class)\s+(\w+)\s*(?:=|\()'
                for match in re.finditer(pattern, content):
                    component_name = match.group(1)
                    if component_name not in ['React', 'useState', 'useEffect', 'useRef']:
                        components[component_name] = str(js_file)

        # Find imports
        for js_file in self.project_root.glob('frontend/src/**/*.{js,jsx,ts,tsx}'):
            with open(js_file, 'r') as f:
                content = f.read()
                pattern = r'import\s+\{([^}]+)\}\s+from'
                for match in re.finditer(pattern, content):
                    imported = [name.strip() for name in match.group(1).split(',')]
                    imports.extend(imported)

        # Also find default imports
        pattern = r"import\s+(\w+)\s+from"
        for js_file in self.project_root.glob('frontend/src/**/*.{js,jsx,ts,tsx}'):
            with open(js_file, 'r') as f:
                content = f.read()
                for match in re.finditer(pattern, content):
                    imports.append(match.group(1))

        # Find unused components (excluding common ones)
        common_components = {'React', 'useState', 'useEffect', 'useRef', 'useCallback', 
                           'useMemo', 'useContext', 'useReducer', 'useLayoutEffect',
                           'useImperativeHandle', 'useDebugValue', 'useDeferredValue',
                           'useTransition', 'useId', 'createContext', 'Fragment',
                           'Suspense', 'lazy', 'memo', 'forwardRef', 'useRef'}

        for comp_name, file_path in components.items():
            if comp_name not in imports and comp_name not in common_components:
                self.results['unused_react_components'].append({
                    'name': comp_name,
                    'file': file_path,
                })

    def detect_unused_utils(self):
        """Detect unused utility functions."""
        utils = {}
        references = []

        # Find all utils
        for py_file in self.project_root.glob('backend/**/utils.py'):
            with open(py_file, 'r') as f:
                content = f.read()
                pattern = r'def\s+(\w+)\s*\('
                for match in re.finditer(pattern, content):
                    utils[match.group(1)] = str(py_file)

        # Find references
        for py_file in self.project_root.glob('backend/**/*.py'):
            with open(py_file, 'r') as f:
                content = f.read()
                for util_name in utils.keys():
                    if util_name in content:
                        references.append(util_name)

        # Find unused utils
        for util_name, file_path in utils.items():
            if util_name not in references:
                self.results['unused_utils'].append({
                    'name': util_name,
                    'file': file_path,
                })

    def detect_unused_tasks(self):
        """Detect unused Celery tasks."""
        tasks = {}
        references = []

        # Find all tasks
        for app_dir in self.project_root.glob('backend/apps/*/'):
            tasks_file = app_dir / 'tasks.py'
            if tasks_file.exists():
                with open(tasks_file, 'r') as f:
                    content = f.read()
                    pattern = r'@shared_task\s*def\s+(\w+)'
                    for match in re.finditer(pattern, content):
                        tasks[match.group(1)] = str(tasks_file)

        # Find references (delay, apply_async)
        for py_file in self.project_root.glob('backend/**/*.py'):
            with open(py_file, 'r') as f:
                content = f.read()
                for task_name in tasks.keys():
                    if f"{task_name}.delay" in content or f"{task_name}.apply_async" in content:
                        references.append(task_name)

        # Find unused tasks
        for task_name, file_path in tasks.items():
            if task_name not in references:
                self.results['unused_tasks'].append({
                    'name': task_name,
                    'file': file_path,
                })

    def detect_unused_signals(self):
        """Detect unused Django signals."""
        signals = {}
        references = []

        # Find all signals
        for app_dir in self.project_root.glob('backend/apps/*/'):
            signals_file = app_dir / 'signals.py'
            if signals_file.exists():
                with open(signals_file, 'r') as f:
                    content = f.read()
                    # Find signal receivers
                    pattern = r'@receiver\s*\([^)]+\)\s*def\s+(\w+)'
                    for match in re.finditer(pattern, content):
                        signals[match.group(1)] = str(signals_file)

        # Find references to signals
        for py_file in self.project_root.glob('backend/**/*.py'):
            with open(py_file, 'r') as f:
                content = f.read()
                for signal_name in signals.keys():
                    if signal_name in content:
                        references.append(signal_name)

        # Find unused signals
        for signal_name, file_path in signals.items():
            if signal_name not in references:
                self.results['unused_signals'].append({
                    'name': signal_name,
                    'file': file_path,
                })

    def detect_unused_css_classes(self):
        """Detect unused CSS classes (basic)."""
        css_classes = {}
        references = []

        # Find all CSS classes
        for css_file in self.project_root.glob('frontend/src/**/*.css'):
            with open(css_file, 'r') as f:
                content = f.read()
                pattern = r'\.([a-zA-Z_][a-zA-Z0-9_-]+)\s*\{'
                for match in re.finditer(pattern, content):
                    class_name = match.group(1)
                    if class_name not in css_classes:
                        css_classes[class_name] = []
                    css_classes[class_name].append(str(css_file))

        # Find references in JS/TS files
        for js_file in self.project_root.glob('frontend/src/**/*.{js,jsx,ts,tsx}'):
            with open(js_file, 'r') as f:
                content = f.read()
                for class_name in css_classes.keys():
                    if f'"{class_name}"' in content or f"'{class_name}'" in content:
                        references.append(class_name)

        # Also check className usage
        for js_file in self.project_root.glob('frontend/src/**/*.{js,jsx,ts,tsx}'):
            with open(js_file, 'r') as f:
                content = f.read()
                # Find className="..."
                pattern = r'className=[\'"]([^\'"]+)[\'"]'
                for match in re.finditer(pattern, content):
                    classes = match.group(1).split()
                    for cls in classes:
                        if cls in css_classes:
                            references.append(cls)

        # Find unused CSS classes
        for class_name, file_paths in css_classes.items():
            if class_name not in references:
                self.results['unused_css_classes'].append({
                    'name': class_name,
                    'files': file_paths,
                })

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive dead code report."""
        # Run all detectors
        self.detect_unused_django_views()
        self.detect_unused_serializers()
        self.detect_unused_react_components()
        self.detect_unused_utils()
        self.detect_unused_tasks()
        self.detect_unused_signals()
        self.detect_unused_css_classes()

        # Generate summary
        self.results['summary'] = {
            'total_unused_views': len(self.results['unused_views']),
            'total_unused_serializers': len(self.results['unused_serializers']),
            'total_unused_react_components': len(self.results['unused_react_components']),
            'total_unused_utils': len(self.results['unused_utils']),
            'total_unused_tasks': len(self.results['unused_tasks']),
            'total_unused_signals': len(self.results['unused_signals']),
            'total_unused_css_classes': len(self.results['unused_css_classes']),
            'total_dead_code': (
                len(self.results['unused_views']) +
                len(self.results['unused_serializers']) +
                len(self.results['unused_react_components']) +
                len(self.results['unused_utils']) +
                len(self.results['unused_tasks']) +
                len(self.results['unused_signals']) +
                len(self.results['unused_css_classes'])
            ),
        }

        return self.results

    def generate_markdown_report(self) -> str:
        """Generate a markdown report."""
        report = self.generate_report()
        
        lines = [
            "# 🧹 Dead Code Detection Report",
            "",
            "## 📊 Summary",
            "",
            f"| Category | Count |",
            f"|----------|-------|",
            f"| Unused Views | {report['summary']['total_unused_views']} |",
            f"| Unused Serializers | {report['summary']['total_unused_serializers']} |",
            f"| Unused React Components | {report['summary']['total_unused_react_components']} |",
            f"| Unused Utility Functions | {report['summary']['total_unused_utils']} |",
            f"| Unused Celery Tasks | {report['summary']['total_unused_tasks']} |",
            f"| Unused Django Signals | {report['summary']['total_unused_signals']} |",
            f"| Unused CSS Classes | {report['summary']['total_unused_css_classes']} |",
            f"| **Total** | **{report['summary']['total_dead_code']}** |",
            "",
        ]

        # Add details for each category
        categories = [
            ('unused_views', 'Unused Views'),
            ('unused_serializers', 'Unused Serializers'),
            ('unused_react_components', 'Unused React Components'),
            ('unused_utils', 'Unused Utility Functions'),
            ('unused_tasks', 'Unused Celery Tasks'),
            ('unused_signals', 'Unused Django Signals'),
            ('unused_css_classes', 'Unused CSS Classes'),
        ]

        for key, title in categories:
            items = report.get(key, [])
            if items:
                lines.append(f"## {title}")
                lines.append("")
                lines.append("| Name | Location |")
                lines.append("|------|----------|")
                for item in items[:20]:  # Show top 20
                    name = item.get('name', '')
                    location = item.get('file', item.get('files', ['unknown']))
                    if isinstance(location, list):
                        location = ', '.join(location[:3])
                    lines.append(f"| `{name}` | `{location}` |")
                if len(items) > 20:
                    lines.append(f"| ... and {len(items) - 20} more | |")
                lines.append("")

        return "\n".join(lines)

    def generate_json_report(self) -> str:
        """Generate a JSON report."""
        report = self.generate_report()
        return json.dumps(report, indent=2, default=str)


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', choices=['md', 'json'], default='md')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--project-root', default='.')
    args = parser.parse_args()

    detector = DeadCodeDetector(args.project_root)
    
    if args.format == 'json':
        content = detector.generate_json_report()
        ext = 'json'
    else:
        content = detector.generate_markdown_report()
        ext = 'md'

    if args.output:
        with open(args.output, 'w') as f:
            f.write(content)
        print(f"✅ Report saved to {args.output}")
    else:
        print(content)


if __name__ == '__main__':
    main()