import ast
import difflib

def extract_ast_nodes(code: str) -> list[str]:
    """
    Parses Python code and extracts a sequence of AST node types.
    This strips out variable names, comments, and literal values,
    leaving only the pure structural flow of the program.
    """
    try:
        tree = ast.parse(code)
        # We traverse the AST in a deterministic order (DFS)
        return [type(node).__name__ for node in ast.walk(tree)]
    except SyntaxError:
        # If it's not valid Python code, fallback to empty list
        return []

def calculate_structural_similarity(code1: str, code2: str) -> float:
    """
    Calculates the structural similarity between two pieces of Python code
    using their AST node sequences.
    Returns a score between 0.0 and 1.0.
    """
    nodes1 = extract_ast_nodes(code1)
    nodes2 = extract_ast_nodes(code2)

    # If both are empty (e.g., empty string or both invalid syntax), they are identical
    if not nodes1 and not nodes2:
        return 1.0
        
    # If one is empty and the other is not, they are completely different
    if not nodes1 or not nodes2:
        return 0.0

    # difflib.SequenceMatcher compares sequences and returns a ratio 
    # of the longest contiguous matching blocks.
    matcher = difflib.SequenceMatcher(None, nodes1, nodes2)
    return matcher.ratio()
