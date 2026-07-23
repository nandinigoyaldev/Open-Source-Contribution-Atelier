"""
Export dependency graph as Graphviz DOT format.
"""

from typing import Dict, Any


class GraphvizExporter:
    """
    Export dependency graph as Graphviz DOT format.
    """

    def export(self, graph_data: Dict[str, Any]) -> str:
        """Generate Graphviz DOT code."""
        lines = ["digraph DjangoDependencies {"]
        lines.append("    rankdir=LR;")
        lines.append("    node [shape=box, style=filled, fillcolor=lightblue];")

        # Add nodes
        for node in graph_data["nodes"]:
            label = node["label"]
            models = node.get("models", 0)
            serializers = node.get("serializers", 0)
            views = node.get("views", 0)

            info = f"Models: {models}\\nSerializers: {serializers}\\nViews: {views}"
            lines.append(f'    {node["id"]} [label="{label}\\n{info}"];')

        # Add edges
        for edge in graph_data["edges"]:
            lines.append(f'    {edge["source"]} -> {edge["target"]};')

        lines.append("}")
        return "\n".join(lines)
