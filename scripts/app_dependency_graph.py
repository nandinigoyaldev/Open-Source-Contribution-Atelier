"""Builds the backend app dependency tables and Mermaid diagram used in docs/ARCHITECTURE.md.

An edge A -> B means a non-test module of app A imports from ``apps.B`` (or names ``B.Model`` in a
relation string). External services are detected from imports and well-known hostnames.

    python scripts/app_dependency_graph.py            # print the generated section
    python scripts/app_dependency_graph.py --write    # update docs/ARCHITECTURE.md in place
    python scripts/app_dependency_graph.py --check    # exit 1 if docs/ARCHITECTURE.md is out of date

Add a new app to DOMAINS below, then run with --write.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parent.parent
APPS_DIR = REPO / "backend" / "apps"
SETTINGS = REPO / "backend" / "config" / "settings.py"
DOC = REPO / "docs" / "ARCHITECTURE.md"

START, END = "<!-- app-graph:start -->", "<!-- app-graph:end -->"

# Domain -> apps. Every directory in backend/apps that is an app must be listed exactly once.
DOMAINS: Dict[str, List[str]] = {
    "Identity and access": [
        "accounts",
        "oauth",
        "rbac",
        "security",
        "organizations",
        "audit",
    ],
    "Learning content and progress": [
        "content",
        "progress",
        "challenges",
        "sandbox",
        "flashcards",
        "notes",
        "learning_journal",
        "learning_analytics",
        "ai_tutor",
        "accessibility",
        "localization",
        "recommendations",
    ],
    "Gamification and engagement": [
        "gamification",
        "dashboard",
        "notifications",
        "events",
        "predictions",
        "onboarding",
        "portfolio",
        "feed",
    ],
    "Social and collaboration": [
        "chat",
        "mentorship",
        "study_groups",
        "moderation",
        "feature_requests",
    ],
    "Open-source issue intelligence": [
        "issues",
        "issue_quality",
        "issue_quality_ci",
        "issue_categorization",
        "issue_routing",
        "deduplication",
        "ml_triage",
        "pr_review_bot",
        "skills_matching",
        "project_health",
        "burnout_detection",
        "dependency_graph",
    ],
    "Platform and operations": [
        "core",
        "cache",
        "errors",
        "monitoring",
        "health",
        "profiler",
        "benchmark",
        "feature_flags",
        "experiments",
        "webhooks",
        "uploads",
        "plugins",
        "dx_analytics",
        "dx_testing",
        "graphql_gateway",
        "billing",
        "admin",
        "search",
        "advanced_search",
    ],
}

# Directories under backend/apps that are not Django apps.
NOT_APPS = {"migrations"}

IMPORT_SERVICES = {
    "redis": "Redis",
    "django_redis": "Redis",
    "celery": "Celery",
    "channels": "WebSockets (Channels)",
    "stripe": "Stripe",
    "boto3": "S3 (boto3)",
    "sentry_sdk": "Sentry",
    "openai": "LLM API",
    "anthropic": "LLM API",
    "sentence_transformers": "Embeddings model",
    "pywebpush": "Web Push",
    "meilisearch": "Meilisearch",
}
TEXT_SERVICES = {
    "GitHub API": re.compile(r"api\.github\.com|GITHUB_TOKEN|GITHUB_API"),
    "Meilisearch": re.compile(r"MEILI_|meilisearch", re.I),
    "Email (SMTP)": re.compile(
        r"\bsend_mail\(|EmailMessage\(|EmailMultiAlternatives\("
    ),
    "Google OAuth": re.compile(r"google\.oauth2|google\.auth"),
}


def app_names(apps_dir: Path = APPS_DIR) -> List[str]:
    return sorted(
        d.name
        for d in apps_dir.iterdir()
        if d.is_dir() and not d.name.startswith(("_", ".")) and d.name not in NOT_APPS
    )


def source_files(app_dir: Path):
    for path in sorted(app_dir.rglob("*.py")):
        parts = set(path.relative_to(app_dir).parts)
        if parts & {"migrations", "tests", "__pycache__"}:
            continue
        if (
            path.name.startswith("test_")
            or path.name.endswith("_tests.py")
            or path.name == "tests.py"
        ):
            continue
        yield path


def scan(apps_dir: Path = APPS_DIR) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """(edges: app -> apps it imports, services: app -> external services)."""
    apps = set(app_names(apps_dir))
    edges: Dict[str, Set[str]] = {a: set() for a in apps}
    services: Dict[str, Set[str]] = {a: set() for a in apps}
    relation = re.compile(r"['\"]([a-z_]+)\.[A-Z][A-Za-z0-9]+['\"]")
    for app in apps:
        for path in source_files(apps_dir / app):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in TEXT_SERVICES.items():
                if pattern.search(text):
                    services[app].add(label)
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                modules: List[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                    if node.level == 0 and node.module == "apps":
                        modules += [f"apps.{alias.name}" for alias in node.names]
                elif isinstance(node, ast.Import):
                    modules += [alias.name for alias in node.names]
                for module in modules:
                    parts = module.split(".")
                    if parts[0] in IMPORT_SERVICES:
                        services[app].add(IMPORT_SERVICES[parts[0]])
                    if (
                        len(parts) >= 2
                        and parts[0] == "apps"
                        and parts[1] in apps
                        and parts[1] != app
                    ):
                        edges[app].add(parts[1])
            if re.search(r"ForeignKey|ManyToManyField|OneToOneField", text):
                for match in relation.finditer(text):
                    other = match.group(1)
                    if other in apps and other != app:
                        edges[app].add(other)
    return edges, services


def installed_apps(settings: Path = SETTINGS) -> Set[str]:
    return set(re.findall(r'"apps\.([a-z_]+)', settings.read_text(encoding="utf-8")))


def tier(inbound: int) -> str:
    if inbound >= 3:
        return "Core"
    if inbound >= 1:
        return "Supporting"
    return "Optional"


def domain_of(app: str) -> str:
    for domain, members in DOMAINS.items():
        if app in members:
            return domain
    return "Unclassified"


def render(apps_dir: Path = APPS_DIR, settings: Path = SETTINGS) -> str:
    edges, services = scan(apps_dir)
    installed = installed_apps(settings)
    inbound: Dict[str, Set[str]] = defaultdict(set)
    for source, targets in edges.items():
        for target in targets:
            inbound[target].add(source)

    lines: List[str] = []
    lines.append("```mermaid")
    lines.append("flowchart LR")
    for index, (domain, members) in enumerate(DOMAINS.items()):
        lines.append(f'  subgraph D{index}["{domain}"]')
        for app in members:
            lines.append(f"    {app}")
        lines.append("  end")
    for source in sorted(edges):
        for target in sorted(edges[source]):
            lines.append(f"  {source} --> {target}")
    lines.append("```")
    lines.append("")
    lines.append(
        "| App | Domain | Tier | Imports | Imported by | Installed | External services |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for app in sorted(edges):
        imports = ", ".join(f"`{x}`" for x in sorted(edges[app])) or "-"
        used_by = ", ".join(f"`{x}`" for x in sorted(inbound[app])) or "-"
        external = ", ".join(sorted(services[app])) or "-"
        lines.append(
            f"| `{app}` | {domain_of(app)} | {tier(len(inbound[app]))} | {imports} | {used_by} | "
            f"{'yes' if app in installed else 'no'} | {external} |"
        )
    return "\n".join(lines)


def section(apps_dir: Path = APPS_DIR, settings: Path = SETTINGS) -> str:
    return f"{START}\n{render(apps_dir, settings)}\n{END}"


def replace_section(document: str, new_section: str) -> str:
    start, end = document.find(START), document.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"{START} / {END} markers not found")
    return document[:start] + new_section + document[end + len(END) :]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--write", action="store_true", help="update docs/ARCHITECTURE.md"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if docs/ARCHITECTURE.md is out of date",
    )
    args = parser.parse_args(argv)
    generated = section()
    if not (args.write or args.check):
        print(generated)
        return 0
    current = DOC.read_text(encoding="utf-8")
    updated = replace_section(current, generated)
    if args.check:
        if updated != current:
            print(
                "docs/ARCHITECTURE.md is out of date. Run: python scripts/app_dependency_graph.py --write"
            )
            return 1
        print("docs/ARCHITECTURE.md is up to date.")
        return 0
    DOC.write_text(updated, encoding="utf-8")
    print("Updated docs/ARCHITECTURE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
