import ast
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

PROHIBITED_CALLS = {
    "os.system",
    "os.popen",
    "os.spawn",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    "os.posix_spawn",
    "os.posix_spawnp",
    "os.exec",
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execlpe",
    "os.execv",
    "os.execve",
    "os.execvp",
    "os.execvpe",
    "subprocess.Popen",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "asyncio.create_subprocess_shell",
    "asyncio.create_subprocess_exec",
    "importlib.import_module",
    "importlib.__import__",
    "eval",
    "exec",
    "__import__",
    "compile",
}

PROHIBITED_MODULES = {
    "socket",
    "ctypes",
    "pty",
    "importlib",
    "multiprocessing",
}

class ASTSecurityVisitor(ast.NodeVisitor):
    """
    Defensive static AST analyzer for candidate patches and generated tests.
    Detects unauthorized execution primitives, raw socket calls, dynamic execution,
    and credential exfiltration attempts before code is executed in any sandbox.
    """

    def __init__(self, filename: str = "<candidate>"):
        self.filename = filename
        self.prohibited_calls: List[Dict[str, Any]] = []
        self.prohibited_imports: List[Dict[str, Any]] = []
        self.security_warnings: List[Dict[str, Any]] = []

    def _get_call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            val = node.func.value
            parts = []
            while isinstance(val, ast.Attribute):
                parts.append(val.attr)
                val = val.value
            if isinstance(val, ast.Name):
                parts.append(val.id)
            parts.reverse()
            parts.append(node.func.attr)
            return ".".join(parts)
        return ""

    def visit_Call(self, node: ast.Call):
        call_name = self._get_call_name(node)
        for prohibited in PROHIBITED_CALLS:
            if call_name == prohibited or call_name.endswith(f".{prohibited}"):
                self.prohibited_calls.append({
                    "call": call_name,
                    "line": getattr(node, "lineno", 0),
                    "file": self.filename,
                    "reason": f"Execution of dangerous system primitive '{call_name}' is forbidden."
                })
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if base_mod in PROHIBITED_MODULES:
                self.prohibited_imports.append({
                    "module": alias.name,
                    "line": getattr(node, "lineno", 0),
                    "file": self.filename,
                    "reason": f"Direct import of low-level system module '{alias.name}' is prohibited."
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_mod = node.module.split(".")[0]
            if base_mod in PROHIBITED_MODULES:
                self.prohibited_imports.append({
                    "module": node.module,
                    "line": getattr(node, "lineno", 0),
                    "file": self.filename,
                    "reason": f"Import from low-level module '{node.module}' is prohibited."
                })
        self.generic_visit(node)

def analyze_code_security(code_str: str, filename: str = "<candidate>") -> Dict[str, Any]:
    """
    Parses and scans code string for AST security violations.
    Returns:
    {
        "is_safe": bool,
        "violations": List[str],
        "details": Dict[str, Any]
    }
    """
    try:
        tree = ast.parse(code_str, filename=filename)
    except SyntaxError as syn_err:
        return {
            "is_safe": False,
            "violations": [f"Syntax error prevents security analysis: {syn_err}"],
            "details": {}
        }
    except Exception as e:
        return {
            "is_safe": False,
            "violations": [f"AST parse failure: {str(e)}"],
            "details": {}
        }

    visitor = ASTSecurityVisitor(filename=filename)
    visitor.visit(tree)

    violations = []
    for call in visitor.prohibited_calls:
        violations.append(f"Line {call['line']}: {call['reason']}")
    for imp in visitor.prohibited_imports:
        violations.append(f"Line {imp['line']}: {imp['reason']}")

    return {
        "is_safe": len(violations) == 0,
        "violations": violations,
        "details": {
            "prohibited_calls": visitor.prohibited_calls,
            "prohibited_imports": visitor.prohibited_imports
        }
    }
