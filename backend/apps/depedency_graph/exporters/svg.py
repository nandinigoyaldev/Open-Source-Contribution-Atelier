"""
Export dependency graph as SVG using graphviz.
"""

import subprocess
import tempfile
import os
from typing import Dict, Any
from .graphviz import GraphvizExporter


class SVGExporter:
    """
    Export dependency graph as SVG using Graphviz.
    """

    def export(self, graph_data: Dict[str, Any]) -> str:
        """Generate SVG diagram using Graphviz."""
        dot_content = GraphvizExporter().export(graph_data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
            f.write(dot_content)
            dot_file = f.name

        svg_file = dot_file.replace(".dot", ".svg")

        try:
            subprocess.run(
                ["dot", "-Tsvg", dot_file, "-o", svg_file],
                check=True,
                capture_output=True,
            )

            with open(svg_file, "r") as f:
                svg_content = f.read()

            os.unlink(dot_file)
            os.unlink(svg_file)

            return svg_content
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Graphviz not available, return error message
            return f"<!-- Graphviz not available. DOT content: -->\n{dot_content}"
