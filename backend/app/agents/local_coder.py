import re
from typing import Dict, Any, Optional
from app.agents.runtime import agent_runtime
from app.core.logging import logger

LOCAL_CODER_SYSTEM_PROMPT = """You are a senior Python software engineer.
Generate a concise, valid Unified Diff patch implementing the user's subtask.
Rules:
1. Provide standard diff headers:
   --- a/<filepath>
   +++ b/<filepath>
   @@ ... @@
2. Keep edits focused and minimal. Do not touch unrelated code.
3. Wrap your diff inside ```diff ... ``` code blocks.
"""

class LocalCoderAgent:
    """
    Local Coder Worker.
    Runs on CPU-quantized local model (qwen2.5-coder:1.5b) with fallback to Groq or Mock.
    Synthesizes focused Unified Diff patches.
    """

    @staticmethod
    async def generate_patch(
        prompt: str,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        res = await agent_runtime.execute_task(
            role="LocalCoder",
            prompt=prompt,
            system_instruction=LOCAL_CODER_SYSTEM_PROMPT,
            force_mock=force_mock
        )

        content = res.get("content", "")
        diff_text = LocalCoderAgent.extract_diff(content)
        return {
            "diff_text": diff_text,
            "explanation": content.replace(diff_text, "").strip()[:500],
            "provider": res.get("provider"),
            "model": res.get("model"),
            "input_tokens": res.get("input_tokens"),
            "output_tokens": res.get("output_tokens"),
            "is_error": res.get("is_error", False),
            "error_message": res.get("error_message"),
            "is_fallback": res.get("is_fallback", False)
        }

    @staticmethod
    def extract_diff(text: str) -> str:
        clean = text.strip()
        if "```diff" in clean:
            part = clean.split("```diff", 1)[1]
            if "```" in part:
                return part.split("```", 1)[0].strip()
            return part.strip()
        elif "--- a/" in clean and "+++ b/" in clean:
            start = clean.find("--- a/")
            end = clean.find("```", start)
            if end != -1:
                return clean[start:end].strip()
            return clean[start:].strip()
        return clean

local_coder_agent = LocalCoderAgent()
