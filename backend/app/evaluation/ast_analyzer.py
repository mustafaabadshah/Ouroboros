import ast
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from app.core.logging import logger

PROTECTED_SYMBOLS = {
    "validate_move",
    "validate_fen",
    "StockfishEvaluator",
    "BoardManager",
    "_select_emergency_move",
}

class ASTChangeAnalyzer:
    """
    Analyzes Python AST structures across baseline and candidate files.
    Identifies added/removed/modified functions, classes, imports, and protected symbol violations.
    """

    @staticmethod
    def parse_python_ast(code_str: str, filename: str = "<unknown>") -> Tuple[Optional[ast.AST], Optional[str]]:
        try:
            tree = ast.parse(code_str, filename=filename)
            return tree, None
        except SyntaxError as e:
            return None, f"Syntax Error at line {e.lineno}, col {e.offset}: {e.msg}"
        except Exception as e:
            return None, f"AST parse error: {str(e)}"

    @staticmethod
    def extract_symbols(tree: ast.AST) -> Dict[str, Dict[str, Any]]:
        """Extracts top-level and class-level functions and classes."""
        symbols = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                params = [arg.arg for arg in node.args.args]
                symbols[node.name] = {
                    "type": "function",
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "parameters": params,
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno
                }
            elif isinstance(node, ast.ClassDef):
                methods = {}
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods[item.name] = [arg.arg for arg in item.args.args]
                symbols[node.name] = {
                    "type": "class",
                    "bases": [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else [],
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno
                }
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols[f"import:{alias.name}"] = {"type": "import"}
                else:
                    mod = node.module or ""
                    for alias in node.names:
                        symbols[f"import:{mod}.{alias.name}"] = {"type": "import_from"}

        return symbols

    @staticmethod
    def compare_files_ast(before_code: str, after_code: str, filepath: str) -> Dict[str, Any]:
        """
        Compares baseline and candidate AST representations.
        Returns: added symbols, removed symbols, modified symbols, protected violations.
        """
        tree_before, err_before = ASTChangeAnalyzer.parse_python_ast(before_code, filepath)
        tree_after, err_after = ASTChangeAnalyzer.parse_python_ast(after_code, filepath)

        if err_after:
            return {
                "filepath": filepath,
                "syntax_valid": False,
                "error": err_after,
                "added_symbols": [],
                "removed_symbols": [],
                "modified_symbols": [],
                "protected_violations": []
            }

        syms_before = ASTChangeAnalyzer.extract_symbols(tree_before) if tree_before else {}
        syms_after = ASTChangeAnalyzer.extract_symbols(tree_after)

        added = [name for name in syms_after if name not in syms_before]
        removed = [name for name in syms_before if name not in syms_after]
        modified = []

        for name in syms_after:
            if name in syms_before:
                if syms_after[name] != syms_before[name]:
                    modified.append(name)

        # Check protected symbol violations
        violations = []
        for name in removed + modified:
            clean_name = name.split(":")[-1]
            if clean_name in PROTECTED_SYMBOLS:
                violations.append(f"Modification or removal of protected symbol '{clean_name}' in {filepath}")

        return {
            "filepath": filepath,
            "syntax_valid": True,
            "error": None,
            "added_symbols": added,
            "removed_symbols": removed,
            "modified_symbols": modified,
            "protected_violations": violations
        }
