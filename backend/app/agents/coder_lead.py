import ast
from typing import Dict, List, Any, Optional, Set
from app.core.logging import logger
from app.integrations.git.diff_parser import UnifiedDiffParser

class CoderLead:
    """
    Coder Lead Agent.
    Orchestrates coding tasks, enforces file ownership boundaries,
    compresses source context via AST pruning, and validates unified diff integrity.
    """

    @staticmethod
    def compress_context(
        file_content: str,
        target_symbols: Optional[List[str]] = None,
        max_chars: int = 2800
    ) -> str:
        """
        Adaptive AST Context Compression:
        Prunes unchanged class methods and unrelated functions into concise stubs
        to fit maximal AST caller context within local LLM token limits (2048 tokens).
        """
        if not file_content or len(file_content) <= max_chars:
            return file_content

        norm_symbols: Set[str] = set()
        if target_symbols:
            for s in target_symbols:
                clean_s = str(s).strip()
                norm_symbols.add(clean_s.lower())
                if "." in clean_s:
                    norm_symbols.add(clean_s.split(".")[-1].lower())
                if "::" in clean_s:
                    norm_symbols.add(clean_s.split("::")[-1].lower())

        try:
            tree = ast.parse(file_content)
        except Exception:
            return file_content[:max_chars] + "\n# ... [content truncated to fit token budget] ...\n"

        lines = file_content.splitlines(keepends=True)
        prune_ranges = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = item.name.lower()
                        is_targeted = (
                            method_name == "__init__" or
                            method_name in norm_symbols or
                            any(sym in method_name for sym in norm_symbols) or
                            not norm_symbols
                        )
                        if not is_targeted and hasattr(item, "lineno") and hasattr(item, "end_lineno"):
                            def_line = lines[item.lineno - 1]
                            indent = " " * (len(def_line) - len(def_line.lstrip()))
                            omitted_count = item.end_lineno - item.lineno
                            if omitted_count > 3:
                                stub = f"{indent}def {item.name}(*args, **kwargs): ...  # [AST Compressed: {omitted_count} lines pruned]\n"
                                prune_ranges.append((item.lineno, item.end_lineno, stub))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name.lower()
                is_targeted = (
                    func_name in norm_symbols or
                    any(sym in func_name for sym in norm_symbols) or
                    not norm_symbols
                )
                if not is_targeted and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    def_line = lines[node.lineno - 1]
                    indent = " " * (len(def_line) - len(def_line.lstrip()))
                    omitted_count = node.end_lineno - node.lineno
                    if omitted_count > 4:
                        stub = f"{indent}def {node.name}(*args, **kwargs): ...  # [AST Compressed: {omitted_count} lines pruned]\n"
                        prune_ranges.append((node.lineno, node.end_lineno, stub))

        if not prune_ranges:
            return file_content[:max_chars]

        prune_ranges.sort(key=lambda x: x[0], reverse=True)
        modified_lines = list(lines)
        for start_l, end_l, stub in prune_ranges:
            modified_lines[start_l - 1:end_l] = [stub]

        compressed = "".join(modified_lines)
        if len(compressed) > max_chars:
            return compressed[:max_chars] + "\n# ... [content pruned to fit token budget] ...\n"
        return compressed

    @staticmethod
    def prepare_coding_prompt(
        subtask: Dict[str, Any],
        ticket: Dict[str, Any],
        file_content: str,
        failure_hint: str = ""
    ) -> str:
        target_file = subtask.get("target_file", "unknown")
        clean_file = target_file.replace("\\", "/")

        relevant_symbols = subtask.get("relevant_symbols") or ticket.get("relevant_graph_entities") or []
        compressed_content = CoderLead.compress_context(file_content, target_symbols=relevant_symbols)

        ast_callers = subtask.get("caller_context") or subtask.get("callers") or []
        caller_section = ""
        if ast_callers:
            caller_section = (
                "\nAST Caller Context (Upstream dependencies calling this module):\n"
                + "\n".join(f"- {c}" for c in ast_callers[:5])
                + "\n"
            )

        prompt = f"""Task: {subtask.get('description')}
Target File: {clean_file}
Target Symbols: {', '.join(relevant_symbols) if relevant_symbols else 'N/A'}
Ticket Acceptance Criteria:
{ticket.get('acceptance_criteria')}
{caller_section}
Existing File Content (Adaptive AST Compressed):
```python
{compressed_content}
```

{failure_hint}

Generate a concise Unified Diff (patch) that implements the requested changes.
Rules:
1. Output MUST include standard unified diff headers:
   --- a/{clean_file}
   +++ b/{clean_file}
2. Keep the patch compact: include only 2 to 3 lines of context before and after modified lines.
3. Every hunk must begin with @@ and contain matching context.
4. Do not reproduce the entire file. Wrap the final diff cleanly inside ```diff ... ```.
5. Only modify code inside {clean_file}. Do not touch unrelated functions or comments.
"""
        return prompt

    @staticmethod
    def validate_patch(diff_text: str, allowed_files: List[str]) -> Dict[str, Any]:
        """Validates patch boundaries before sending it to the Judge."""
        meta = UnifiedDiffParser.parse_patch(diff_text)
        is_safe, error = UnifiedDiffParser.validate_patch_boundaries(diff_text, allowed_files)
        return {
            "is_valid": meta["is_valid"] and is_safe,
            "error": error or meta.get("error"),
            "changed_files": meta["changed_files"],
            "additions": meta["additions"],
            "deletions": meta["deletions"]
        }

coder_lead = CoderLead()
