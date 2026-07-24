"""
Management command to generate dependency graph.
"""

import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.dependency_graph.graph_generator import DependencyGraphGenerator
from apps.dependency_graph.exporters.mermaid import MermaidExporter
from apps.dependency_graph.exporters.graphviz import GraphvizExporter
from apps.dependency_graph.exporters.svg import SVGExporter


class Command(BaseCommand):
    """
    Generate dependency graph for Django apps.

    Usage:
        python manage.py generate_graph --format mermaid
        python manage.py generate_graph --format graphviz
        python manage.py generate_graph --format svg
        python manage.py generate_graph --format json
    """

    help = "Generate dependency graph for Django apps"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            type=str,
            default="mermaid",
            choices=["mermaid", "graphviz", "svg", "json"],
            help="Output format for the graph",
        )
        parser.add_argument(
            "--output", type=str, help="Output file path (default: graph.{format})"
        )

    def handle(self, *args, **options):
        format_type = options["format"]
        output_file = options.get("output")

        self.stdout.write("🔍 Scanning Django apps...")
        generator = DependencyGraphGenerator()
        graph_data = generator.build_graph()

        self.stdout.write(
            f"✅ Found {graph_data['total_apps']} apps with {graph_data['total_edges']} dependencies"
        )

        # Generate output
        if format_type == "json":
            content = json.dumps(graph_data, indent=2)
            ext = "json"
        elif format_type == "mermaid":
            exporter = MermaidExporter()
            content = exporter.export(graph_data)
            ext = "md"
        elif format_type == "graphviz":
            exporter = GraphvizExporter()
            content = exporter.export(graph_data)
            ext = "dot"
        elif format_type == "svg":
            exporter = SVGExporter()
            content = exporter.export(graph_data)
            ext = "svg"

        # Write output
        if not output_file:
            output_file = f"graph.{ext}"

        with open(output_file, "w") as f:
            f.write(content)

        self.stdout.write(f"✅ Graph saved to: {output_file}")

        if format_type == "mermaid":
            self.stdout.write(
                "\n📝 To view: Copy the Mermaid code to https://mermaid.live/"
            )
