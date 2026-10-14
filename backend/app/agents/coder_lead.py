from typing import Dict, List, Any
from app.core.logging import logger
from app.integrations.git.diff_parser import UnifiedDiffParser

class CoderLead:
    """
    Coder Lead Agent.
    Orchestrates coding tasks, enforces file ownership boundaries, and validates unified diff integrity.
    """

    @staticmethod
    def prepare_coding_prompt(
        subtask: Dict[str, Any],
        ticket: Dict[str, Any],
        file_content: str,
        failure_hint: str = ""
    ) -> str:
        target_file = subtask.get("target_file", "unknown")
        clean_file = target_file.replace("\\", "/")

        prompt = f"""Task: {subtask.get('description')}
Target File: {clean_file}
Ticket Acceptance Criteria:
{ticket.get('acceptance_criteria')}

Existing File Content:
```python
{file_content[:3000]}
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
