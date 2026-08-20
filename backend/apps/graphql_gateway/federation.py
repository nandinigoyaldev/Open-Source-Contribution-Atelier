from graphql.language.visitor import Visitor, visit

class PreserveDirectivesVisitor(Visitor):
    def leave_field(self, node, key, parent, path, ancestors):
        """Retain field directives explicitly in the transformed AST node."""
        if hasattr(node, "directives") and node.directives:
            return node
        return node

def transform_query_ast(document_ast):
    """Transforms the incoming query AST while preserving custom field directive metadata."""
    return visit(document_ast, PreserveDirectivesVisitor())
