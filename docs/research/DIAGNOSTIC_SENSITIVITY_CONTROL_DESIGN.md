# Diagnostic-Sensitivity Control Protocol & Architecture Specification
**Project:** Project Ouroboros — Phase 4 Research Extension  
**Document Version:** 1.0.0  
**Date:** 2026-10-18  
**Scope:** Specification of a 4-condition deterministic control experiment isolating genuine failure-trace learning from marker-based heuristic triggering.

---

## 1. Problem Formulation: The Marker-Triggering Confound

During the Phase 4 forensic audit of [`backend/app/providers/mock_provider.py`](file:///E:/MM%20Office/Ouroboros/backend/app/providers/mock_provider.py), a critical epistemic confound was established:

```python
# Current mock dispatch logic in mock_provider.py:
elif (
    "structured failure diagnostics" in prompt_lower
    or "prior attempt trajectories" in prompt_lower
    or (system_instruction and "repair specialist" in system_instruction.lower())
):
    patch_diff = matched_task.get("repair_patch") or matched_task.get("flawed_patch", "")
    content = f"```diff\n{patch_diff}\n```\nExplanation: Applied failure-informed repair patch addressing diagnostics."
else:
    patch_diff = matched_task.get("flawed_patch", "")
    content = f"```diff\n{patch_diff}\n```\nExplanation: Applied initial naive patch."
```

### The Confound
The mock provider swaps from `flawed_patch` to `repair_patch` **purely upon detecting the marker string** `"structured failure diagnostics"` or system instruction `"repair specialist"`.

As a consequence:
1. The mock agent never inspects the actual assertion error, stack trace lines, or failure signature.
2. An empty or completely corrupted failure trace (e.g., claiming a syntax error when the bug is an off-by-one boundary) still receives `repair_patch`.
3. The evaluation demonstrates **integration validity** (the pipeline correctly passes headers and data), but does **not** demonstrate **causal learning validity** (the agent adapting its code in response to diagnostic content).

---

## 2. The 4-Condition Diagnostic-Sensitivity Control Design

To isolate whether an agent—mock or neural—is genuinely sensitive to failure diagnostics, we define a controlled 4-condition experimental design:

| Condition | Diagnostic Payload | Agent Expected Behavior | Validated Hypothesis |
| :--- | :--- | :--- | :--- |
| **1. Correct Diagnostics** | Authentic pytest failure trace, failing test node, and assertion mismatch from Attempt 1. | Synthesizes verified `repair_patch`. Verification passes. | Confirms that genuine diagnostic feedback enables defect resolution. |
| **2. Corrupted / Inverted Diagnostics** | Semantically perturbed trace (e.g. inverted bounds `Expected high < low`, wrong file, or conflicting assertion). | Synthesizes an erroneous patch or remains on `flawed_patch`. Verification fails. | Confirms the agent is sensitive to diagnostic fidelity, not just marker presence. |
| **3. Marker-Only / Empty Diagnostics** | Injects `"STRUCTURED FAILURE DIAGNOSTICS:"` header, but trace body is empty, whitespace, or generic `"<no trace>"`. | Cannot resolve bug; falls back to `flawed_patch`. Verification fails. | Confirms the presence of the header alone does not trigger repair success. |
| **4. Absent Diagnostics** (Naive Retry) | Standard unassisted prompt with zero diagnostic markers or prior attempt history. | Generates baseline `flawed_patch`. Verification fails. | Standard unassisted baseline performance. |

---

## 3. Formal Hypotheses for Sensitivity Control

- **$H_{Sens\_1}$ (Marker Invariance Rejection):** Condition 3 (Marker-Only) achieves repair success equivalent to Condition 4 (Absent Diagnostics), proving that header injection does not confer an artificial advantage ($PassRate(C_3) = PassRate(C_4) = 0\%$).
- **$H_{Sens\_2}$ (Diagnostic Fidelity Sensitivity):** Condition 1 (Correct) achieves significantly higher repair success than Condition 2 (Corrupted) ($PassRate(C_1) \gg PassRate(C_2)$), proving that the agent reacts to the truth-value of the feedback.
- **Null Hypothesis ($H_{Sens\_0}$):** All conditions containing the marker string achieve identical pass rates ($PassRate(C_1) = PassRate(C_2) = PassRate(C_3) = 100\%$), which would prove marker-dependent confounding.

---

## 4. Architectural Implementation: `SensitivityAwareMockProvider`

Without altering `MockProvider` while Phase 4 sweeps execute, we design an extended provider subclass `SensitivityAwareMockProvider`:

```python
class SensitivityAwareMockProvider(BaseLLMProvider):
    """
    Diagnostic-sensitive mock provider that evaluates trace truth-value.
    Distinguishes correct, corrupted, marker-only, and absent diagnostics.
    """
    
    @staticmethod
    def extract_diagnostic_body(prompt: str) -> str:
        """Extracts text following 'STRUCTURED FAILURE DIAGNOSTICS:' header."""
        marker = "structured failure diagnostics:"
        idx = prompt.lower().find(marker)
        if idx == -1:
            return ""
        return prompt[idx + len(marker):].strip()

    def evaluate_diagnostic_fidelity(self, task_def: Dict[str, Any], prompt: str) -> str:
        """
        Classifies diagnostic context into:
        - 'CORRECT': Matches expected failure tokens from task acceptance failure.
        - 'CORRUPTED': Contains known perturbation signatures.
        - 'MARKER_ONLY': Header present but body empty or generic.
        - 'ABSENT': Header missing entirely.
        """
        body = self.extract_diagnostic_body(prompt)
        if not body or len(body) < 10 or body.lower() in ["<no trace>", "none", "unknown"]:
            return "MARKER_ONLY" if "structured failure diagnostics" in prompt.lower() else "ABSENT"
            
        if "CORRUPTED_PERTURBATION" in body or "INVERTED_ASSERTION" in body:
            return "CORRUPTED"
            
        # Check for genuine task failure tokens
        expected_failure_tokens = task_def.get("expected_failure_tokens", [])
        if any(token in body for token in expected_failure_tokens):
            return "CORRECT"
            
        return "CORRUPTED"
```

---

## 5. Verification & Test Plan

Before running live frontier models, the diagnostic sensitivity contract is verified via unit tests:
1. `test_correct_diagnostics_produces_repair()`: Verifies valid trace produces `repair_patch`.
2. `test_corrupted_diagnostics_produces_flawed_patch()`: Verifies corrupted trace produces `flawed_patch`.
3. `test_marker_only_produces_flawed_patch()`: Verifies header without trace produces `flawed_patch`.
4. `test_absent_diagnostics_produces_flawed_patch()`: Verifies unassisted prompt produces `flawed_patch`.

This guarantees that future evaluation claims are mathematically defended against marker-based confounding.
