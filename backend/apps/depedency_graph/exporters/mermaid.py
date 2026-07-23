"""
Export dependency graph as Mermaid diagram.
"""

from typing import Dict, Any


class MermaidExporter:
    """
    Export dependency graph as Mermaid format.
    """

    def export(self, graph_data: Dict[str, Any]) -> str:
        """Generate Mermaid diagram code."""
        lines = ["graph TD"]

        # Add nodes with labels
        for node in graph_data["nodes"]:
            label = node["label"]
            lines.append(f'    {node["id"]}["{label}"]')

        # Add edges
        for edge in graph_data["edges"]:
            lines.append(f'    {edge["source"]} --> {edge["target"]}')

        return "\n".join(lines)
