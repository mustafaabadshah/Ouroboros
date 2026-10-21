"""
Unit tests for the Deterministic Diagnostic-Sensitivity Control.

Validates the 4-condition sensitivity contract:
1. Condition 1 (Correct Diagnostics):
   Authentic failure trace tokens matching the task failure trigger repair_patch.
2. Condition 2 (Corrupted Diagnostics):
   Perturbed or inverted failure assertions fail to trigger repair_patch (returns flawed_patch).
3. Condition 3 (Marker-Only / Empty Diagnostics):
   The presence of 'STRUCTURED FAILURE DIAGNOSTICS:' header alone without diagnostic content
   fails to trigger repair_patch (returns flawed_patch).
4. Condition 4 (Absent Diagnostics):
   Unassisted prompt with zero failure history produces flawed_patch.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional
from app.providers.base import BaseLLMProvider
from app.evaluation.benchmark import BenchmarkHarness


class SensitivityAwareMockProvider(BaseLLMProvider):
    """
    Deterministic mock provider that inspects the truth-value and substance
    of failure diagnostics rather than relying solely on header marker presence.
    """

    async def check_health(self) -> Dict[str, Any]:
        return {"available": True, "provider": "sensitivity-mock", "message": "Sensitivity mock provider active."}

    @staticmethod
    def extract_diagnostic_body(prompt: str) -> str:
        marker = "structured failure diagnostics:"
        idx = prompt.lower().find(marker)
        if idx == -1:
            return ""
        return prompt[idx + len(marker):].strip()

    def evaluate_diagnostic_condition(self, task_def: Dict[str, Any], prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "structured failure diagnostics" not in prompt_lower:
            return "ABSENT"

        body = self.extract_diagnostic_body(prompt)
        # Empty or generic placeholder
        if not body or len(body) < 15 or body.lower() in ["none", "<no trace>", "no diagnostics recorded."]:
            return "MARKER_ONLY"

        # Check for deliberate corruption markers
        if "corrupted_trace" in body.lower() or "inverted_assertion" in body.lower():
            return "CORRUPTED"

        # Check if authentic failure signature tokens for the task exist in body
        # For BENCH-04, the failing assertion contains "assert -5 == 0" or "clamp_boundaries"
        target_file = task_def["target_file"]
        if target_file.lower() in body.lower() or "assertionerror" in body.lower() or "assert" in body.lower():
            return "CORRECT"

        return "CORRUPTED"

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        matched_task = BenchmarkHarness.get_task_by_id("BENCH-04")
        assert matched_task is not None

        condition = self.evaluate_diagnostic_condition(matched_task, prompt)

        if condition == "CORRECT":
            # Only genuine, non-corrupted diagnostics earn the verified repair patch
            patch_diff = matched_task["repair_patch"]
            explanation = "Applied failure-informed repair patch addressing authentic diagnostics."
        else:
            # Corrupted, marker-only, or absent diagnostics all fail to trigger repair
            patch_diff = matched_task["flawed_patch"]
            explanation = f"Generated baseline flawed patch (Diagnostic condition: {condition})."

        return {
            "content": f"```diff\n{patch_diff}\n```\nExplanation: {explanation}",
            "provider": "sensitivity-mock",
            "model": "sensitivity-mock-v1",
            "input_tokens": 150,
            "output_tokens": 250,
            "latency_ms": 10,
            "is_error": False,
            "diagnostic_condition": condition
        }


@pytest.fixture
def sensitivity_provider():
    return SensitivityAwareMockProvider()


@pytest.fixture
def bench04_task():
    task = BenchmarkHarness.get_task_by_id("BENCH-04")
    assert task is not None
    return task


def test_condition_1_correct_diagnostics_triggers_repair(sensitivity_provider, bench04_task):
    """Condition 1: Authentic failure trace generates repair_patch."""
    prompt = (
        f"Ticket: {bench04_task['name']}\n"
        f"Target File: {bench04_task['target_file']}\n\n"
        "STRUCTURED FAILURE DIAGNOSTICS:\n"
        f"AssertionError: assert clamp(-5, 0, 10) == 0 in {bench04_task['target_file']}\n"
        "Traceback:\n"
        "  test_bounds.py:25: in test_clamp_boundaries_and_invalid_range\n"
        "    assert clamp(-5, 0, 10) == 0\n"
    )
    res = asyncio.run(sensitivity_provider.generate(prompt))
    assert res["diagnostic_condition"] == "CORRECT"
    assert bench04_task["repair_patch"].strip() in res["content"]


def test_condition_2_corrupted_diagnostics_triggers_flawed_patch(sensitivity_provider, bench04_task):
    """Condition 2: Corrupted/inverted failure trace fails to trigger repair_patch."""
    prompt = (
        f"Ticket: {bench04_task['name']}\n"
        f"Target File: {bench04_task['target_file']}\n\n"
        "STRUCTURED FAILURE DIAGNOSTICS:\n"
        "INVERTED_ASSERTION: Expected high < low to succeed without error in math_utils/other.py\n"
        "CORRUPTED_TRACE: completely invalid line references\n"
    )
    res = asyncio.run(sensitivity_provider.generate(prompt))
    assert res["diagnostic_condition"] == "CORRUPTED"
    assert bench04_task["flawed_patch"].strip() in res["content"]
    assert bench04_task["repair_patch"].strip() not in res["content"]


def test_condition_3_marker_only_diagnostics_triggers_flawed_patch(sensitivity_provider, bench04_task):
    """Condition 3: Header marker alone without diagnostic body fails to trigger repair_patch."""
    prompt = (
        f"Ticket: {bench04_task['name']}\n"
        f"Target File: {bench04_task['target_file']}\n\n"
        "STRUCTURED FAILURE DIAGNOSTICS:\n"
        "   \n"  # Empty whitespace body
    )
    res = asyncio.run(sensitivity_provider.generate(prompt))
    assert res["diagnostic_condition"] == "MARKER_ONLY"
    assert bench04_task["flawed_patch"].strip() in res["content"]
    assert bench04_task["repair_patch"].strip() not in res["content"]


def test_condition_4_absent_diagnostics_triggers_flawed_patch(sensitivity_provider, bench04_task):
    """Condition 4: Unassisted prompt produces flawed_patch."""
    prompt = (
        f"Ticket: {bench04_task['name']}\n"
        f"Target File: {bench04_task['target_file']}\n"
        f"Problem Statement: {bench04_task['problem_statement']}\n"
        "Generate a unified diff to repair the code."
    )
    res = asyncio.run(sensitivity_provider.generate(prompt))
    assert res["diagnostic_condition"] == "ABSENT"
    assert bench04_task["flawed_patch"].strip() in res["content"]
    assert bench04_task["repair_patch"].strip() not in res["content"]
