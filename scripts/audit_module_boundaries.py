#!/usr/bin/env python3
"""
Architectural module boundary and circular import auditor.

Uses AST parsing to analyze Python imports across project packages, builds an
internal dependency graph, identifies circular import chains, and verifies
boundary layering constraints.

Usage:
    python scripts/audit_module_boundaries.py [--root DIR] [--fail-on-cycle] [--strict]
"""

import argparse
import ast
import os
import sys
from typing import Dict, List, Optional, Set, Tuple


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract imported module names from a Python source file."""

    def __init__(self, current_module: str):
        self.current_module = current_module
        self.imported_modules: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imported_modules.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level and node.level > 0:
            # Handle relative imports (e.g., from . import models or from ..utils import helper)
            base_parts = self.current_module.split(".")
            if len(base_parts) >= node.level:
                target_base = ".".join(base_parts[: len(base_parts) - (node.level - 1)])
                if node.module:
                    full_target = f"{target_base}.{node.module}"
                else:
                    full_target = target_base
                self.imported_modules.add(full_target)
        elif node.module:
            self.imported_modules.add(node.module)
        self.generic_visit(node)


def file_to_module_name(file_path: str, base_dir: str) -> str:
    """Convert relative file path to Python dot-separated module path."""
    rel = os.path.relpath(file_path, base_dir)
    without_ext = os.path.splitext(rel)[0]
    parts = without_ext.replace("\\", "/").split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_module_imports(file_path: str, module_name: str) -> Set[str]:
    """Parse a single Python file and extract referenced module names."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=file_path)
        visitor = ImportVisitor(module_name)
        visitor.visit(tree)
        return visitor.imported_modules
    except Exception:
        return set()


def build_dependency_graph(root_dir: str) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Scan python files in root_dir, building a dependency graph of internal modules.
    Returns:
        graph: mapping module -> set of internal modules it imports
        internal_modules: set of all internal module names discovered
    """
    internal_modules: Set[str] = set()
    file_map: Dict[str, str] = {}  # module_name -> file_path

    for dirpath, dirs, files in os.walk(root_dir):
        # Skip cache and virtual environment directories
        dirs[:] = [
            d
            for d in dirs
            if d not in ("node_modules", ".venv", "venv", ".git", "__pycache__", "dist", "build")
        ]
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(dirpath, f)
                mod_name = file_to_module_name(full_path, root_dir)
                if mod_name:
                    internal_modules.add(mod_name)
                    file_map[mod_name] = full_path

    graph: Dict[str, Set[str]] = {mod: set() for mod in internal_modules}

    for mod_name, fpath in file_map.items():
        raw_imports = parse_module_imports(fpath, mod_name)
        for imp in raw_imports:
            # Check if this import matches an internal module or internal sub-module
            matched = None
            for candidate in internal_modules:
                if imp == candidate or imp.startswith(candidate + "."):
                    matched = candidate
                    break
            if matched and matched != mod_name:
                graph[mod_name].add(matched)

    return graph, internal_modules


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Detect circular dependency cycles in directed graph using DFS."""
    cycles: List[List[str]] = []
    visited: Set[str] = set()
    rec_stack: List[str] = []

    def dfs(node: str):
        visited.add(node)
        rec_stack.append(node)

        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                cycle_start_index = rec_stack.index(neighbor)
                cycle = rec_stack[cycle_start_index:] + [neighbor]
                # Normalize cycle representation to avoid duplicate permutations
                normalized = min(
                    cycle[i:-1] + cycle[:i] + [cycle[i]] for i in range(len(cycle) - 1)
                )
                if normalized not in cycles:
                    cycles.append(normalized)

        rec_stack.pop()

    for node in sorted(graph.keys()):
        if node not in visited:
            dfs(node)

    return cycles


def check_boundary_violations(
    graph: Dict[str, Set[str]],
    forbidden_rules: Optional[List[Tuple[str, str]]] = None,
) -> List[str]:
    """
    Check if any dependencies violate architectural boundary layering rules.
    Default rule: 'utils' / 'common' packages should not import 'apps' / 'views' / 'controllers'.
    """
    if forbidden_rules is None:
        forbidden_rules = [
            ("utils", "apps"),
            ("common", "apps"),
            ("models", "views"),
        ]

    violations: List[str] = []
    for source, targets in graph.items():
        for target in targets:
            for from_prefix, to_prefix in forbidden_rules:
                if from_prefix in source.split(".") and to_prefix in target.split("."):
                    violations.append(
                        f"Boundary violation: '{source}' is not permitted to import '{target}' "
                        f"({from_prefix} -> {to_prefix})"
                    )

    return violations


def audit_modules(
    root_dir: str,
    forbidden_rules: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[List[List[str]], List[str]]:
    """Audit project root directory for circular imports and boundary violations."""
    graph, _ = build_dependency_graph(root_dir)
    cycles = find_cycles(graph)
    violations = check_boundary_violations(graph, forbidden_rules)
    return cycles, violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Root directory to scan (default: current)")
    parser.add_argument("--fail-on-cycle", action="store_true", help="Fail if cycles detected")
    parser.add_argument(
        "--strict", action="store_true", help="Fail on cycles or boundary violations"
    )
    args = parser.parse_args()

    cycles, violations = audit_modules(args.root)

    print(f"📊 Module Boundary & Circular Import Audit: scanning '{args.root}'")
    has_issues = False

    if cycles:
        has_issues = True
        print(f"\n⚠️  Found {len(cycles)} circular dependency cycle(s):")
        for idx, cycle in enumerate(cycles, 1):
            print(f"  {idx}. {' -> '.join(cycle)}")
    else:
        print("✅ No circular import cycles detected.")

    if violations:
        has_issues = True
        print(f"\n⚠️  Found {len(violations)} architectural boundary violation(s):")
        for v in violations:
            print(f"  - {v}")
    else:
        print("✅ No architectural boundary violations detected.")

    if has_issues and (args.strict or (cycles and args.fail_on_cycle)):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
