"""
Project Ouroboros - Canonical Failure Context & Diagnostic Normalization Engine
Provides typed, bounded, sanitized failure context schemas for multi-agent repair loops.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import re
from typing import Dict, List, Any, Optional

from app.core.security import mask_secret

class FailureClass(str, Enum):
    TEST_ASSERTION = "test_assertion"
    COLLECTION_ERROR = "collection_error"
    SYNTAX_ERROR = "syntax_error"
    PATCH_APPLY_ERROR = "patch_apply_error"
    STATIC_POLICY_VIOLATION = "static_policy_violation"
    TIMEOUT = "timeout"
    INFRASTRUCTURE_ERROR = "infrastructure_error"

# Sensitive pattern definitions
SECRET_PATTERNS = [
    (re.compile(r"gsk_[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"((?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?)([^'\";\s]{4,})", re.IGNORECASE), r"\1[REDACTED]"),
]

def sanitize_diagnostic_text(text: Optional[str], max_len: Optional[int] = None) -> str:
    """Sanitizes text by masking sensitive credentials, tokens, and bounding length."""
    if not text:
        return ""
    clean = str(text)
    for pat, repl in SECRET_PATTERNS:
        clean = pat.sub(repl, clean)
    if max_len and len(clean) > max_len:
        return clean[:max_len] + "... [TRUNCATED]"
    return clean

@dataclass
class FailureContext:
    failure_class: FailureClass
    failed_test_nodes: List[str] = field(default_factory=list)
    assertion_message: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    traceback_tail: Optional[str] = None
    source_location: Optional[str] = None
    policy_rule_id: Optional[str] = None
    policy_reason: Optional[str] = None
    policy_requirement: Optional[str] = None
    failure_signature: str = ""
    is_repeated: bool = False
    repetition_count: int = 0
    raw_output_length: int = 0
    is_truncated: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes failure context to a clean, JSON-compatible dictionary."""
        d = asdict(self)
        d["failure_class"] = self.failure_class.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureContext":
        """Deserializes dictionary back into FailureContext."""
        f_class_val = data.get("failure_class", FailureClass.TEST_ASSERTION.value)
        try:
            f_class = FailureClass(f_class_val)
        except ValueError:
            f_class = FailureClass.TEST_ASSERTION

        return cls(
            failure_class=f_class,
            failed_test_nodes=data.get("failed_test_nodes", []),
            assertion_message=data.get("assertion_message"),
            expected_value=data.get("expected_value"),
            actual_value=data.get("actual_value"),
            traceback_tail=data.get("traceback_tail"),
            source_location=data.get("source_location"),
            policy_rule_id=data.get("policy_rule_id"),
            policy_reason=data.get("policy_reason"),
            policy_requirement=data.get("policy_requirement"),
            failure_signature=data.get("failure_signature", ""),
            is_repeated=data.get("is_repeated", False),
            repetition_count=data.get("repetition_count", 0),
            raw_output_length=data.get("raw_output_length", 0),
            is_truncated=data.get("is_truncated", False),
            details=data.get("details", {})
        )

    def compute_signature(self) -> str:
        """Computes a stable, semantic failure signature independent of transient memory addresses."""
        norm_nodes = ",".join(sorted(self.failed_test_nodes))
        norm_assertion = (self.assertion_message or "").split("\n")[0].strip()
        # Strip transient diff details or addresses from assertion line
        norm_assertion = re.sub(r"0x[0-9a-fA-F]+", "0x...", norm_assertion)
        norm_assertion = re.sub(r"line \d+", "line N", norm_assertion)
        norm_rule = self.policy_rule_id or ""
        norm_loc = self.source_location or ""

        sig_content = f"{self.failure_class.value}|{norm_nodes}|{norm_assertion}|{norm_rule}|{norm_loc}"
        self.failure_signature = hashlib.sha256(sig_content.encode("utf-8")).hexdigest()[:16]
        return self.failure_signature

    def format_for_repair_prompt(self) -> str:
        """Formats the structured failure diagnostic cleanly for RepairAgent or Planner prompts."""
        lines = [f"Failure Class: {self.failure_class.value}"]
        if self.failed_test_nodes:
            lines.append(f"Failed Tests: {', '.join(self.failed_test_nodes)}")
        if self.source_location:
            lines.append(f"Source Location: {self.source_location}")
        if self.assertion_message:
            lines.append(f"Assertion Failure:\n{self.assertion_message}")
        if self.expected_value or self.actual_value:
            lines.append(f"Expected: {self.expected_value or 'N/A'}")
            lines.append(f"Actual:   {self.actual_value or 'N/A'}")
        if self.policy_rule_id:
            lines.append(f"Policy Rule Violation: [{self.policy_rule_id}]")
            if self.policy_reason:
                lines.append(f"Policy Reason: {self.policy_reason}")
            if self.policy_requirement:
                lines.append(f"Allowed Alternative: {self.policy_requirement}")
        if self.traceback_tail:
            lines.append(f"Relevant Traceback:\n{self.traceback_tail}")
        if self.is_repeated:
            lines.append(f"WARNING: This failure pattern has been repeated {self.repetition_count} time(s).")
            lines.append("Do NOT repeat the previous approach. Change implementation assumptions.")
        return "\n".join(lines)


class FailureContextNormalizer:
    """Normalizes raw subprocess outputs (pytest stdout/stderr) and static rejections into canonical FailureContext."""

    @classmethod
    def from_pytest_output(cls, stdout: str, stderr: str, exit_code: int = 1) -> FailureContext:
        combined = (stdout or "") + "\n" + (stderr or "")
        raw_len = len(combined)
        is_truncated = False

        if exit_code == 0 and "failed" not in combined.lower() and "error" not in combined.lower():
            # Passing run
            ctx = FailureContext(
                failure_class=FailureClass.TEST_ASSERTION,
                raw_output_length=raw_len
            )
            ctx.compute_signature()
            return ctx

        # 1. Check for Syntax or Collection Errors
        if "SyntaxError" in combined:
            m_syntax = re.search(r"SyntaxError:\s*(.*)", combined)
            syntax_msg = m_syntax.group(1).strip() if m_syntax else "Syntax error in candidate code."
            loc_m = re.search(r'File "([^"]+)", line (\d+)', combined)
            src_loc = f"{loc_m.group(1)}:{loc_m.group(2)}" if loc_m else None
            ctx = FailureContext(
                failure_class=FailureClass.SYNTAX_ERROR,
                assertion_message=sanitize_diagnostic_text(syntax_msg, max_len=300),
                source_location=src_loc,
                traceback_tail=sanitize_diagnostic_text(combined[-1200:], max_len=1200),
                raw_output_length=raw_len,
                is_truncated=raw_len > 1200
            )
            ctx.compute_signature()
            return ctx

        if "ERROR collecting" in combined or "ModuleNotFoundError" in combined or "ImportError" in combined:
            m_imp = re.search(r"(?:ModuleNotFoundError|ImportError):\s*(.*)", combined)
            imp_msg = m_imp.group(0).strip() if m_imp else "Failed to import or collect test module."
            ctx = FailureContext(
                failure_class=FailureClass.COLLECTION_ERROR,
                assertion_message=sanitize_diagnostic_text(imp_msg, max_len=300),
                traceback_tail=sanitize_diagnostic_text(combined[-1200:], max_len=1200),
                raw_output_length=raw_len,
                is_truncated=raw_len > 1200
            )
            ctx.compute_signature()
            return ctx

        # 2. Extract Failed Test Node IDs from 'short test summary info'
        failed_nodes: List[str] = []
        summary_assertions: List[str] = []
        summary_match = re.search(r"=+ short test summary info =+\n(.*?)(?=\n=+|$)", combined, re.DOTALL)
        if summary_match:
            for line in summary_match.group(1).splitlines():
                line = line.strip()
                # e.g.: FAILED test_paginator.py::test_paginate_boundaries_and_validation - AssertionError: assert [0, 1] == [0, 1, 2]
                m = re.match(r"^(?:FAILED|ERROR)\s+([^\s:]+(?:::[^\s]+)?)(?:\s+-\s+(.*))?$", line)
                if m:
                    node_id = m.group(1).strip()
                    # Exclude progress percentage artifacts like [100%]
                    if not re.match(r"^\[\s*\d+%\s*\]$", node_id):
                        if node_id not in failed_nodes:
                            failed_nodes.append(node_id)
                        if m.group(2):
                            summary_assertions.append(m.group(2).strip())

        # Fallback for failed nodes if summary section was absent
        if not failed_nodes:
            node_matches = re.findall(r"([a-zA-Z0-9_\-\./\\]+\.py::[a-zA-Z0-9_]+)\s+FAILED", combined)
            for n in node_matches:
                if n not in failed_nodes:
                    failed_nodes.append(n)

        # 3. Extract Assertion & Traceback from FAILURES block
        assertion_msg: Optional[str] = None
        source_loc: Optional[str] = None
        traceback_tail: Optional[str] = None
        expected_val: Optional[str] = None
        actual_val: Optional[str] = None

        failures_block = re.search(r"=+ FAILURES =+\n(.*?)(?=\n=+ (?:short test summary info|warnings summary|summary) =+|\n=+ [0-9]+ failed|$)", combined, re.DOTALL)
        if failures_block:
            raw_failures = "\n" + failures_block.group(1)
            # Find assertion lines starting with E
            e_lines = [line[4:].strip() for line in raw_failures.splitlines() if line.startswith("E   ") or line.startswith("E ")]
            if e_lines:
                assertion_msg = "\n".join(e_lines[:15])  # Cap at 15 lines

            # Extract source location e.g. test_paginator.py:25: in test_paginate_boundaries_and_validation
            loc_match = re.search(r"([a-zA-Z0-9_\-\./\\]+\.py:\d+)", raw_failures)
            if loc_match:
                source_loc = loc_match.group(1)

            # Capture bounded traceback tail
            traceback_tail = raw_failures[-1500:].strip()
        elif summary_assertions:
            assertion_msg = "\n".join(summary_assertions[:5])
            traceback_tail = combined[-1200:].strip()
        else:
            traceback_tail = combined[-1200:].strip() if combined.strip() else None

        # 4. Extract Expected vs Actual values where pattern allows
        if assertion_msg:
            # Pattern: assert <actual> == <expected>
            eq_match = re.search(r"assert\s+(.+?)\s*==\s*(.+)", assertion_msg)
            if eq_match:
                actual_val = sanitize_diagnostic_text(eq_match.group(1).strip(), max_len=300)
                expected_val = sanitize_diagnostic_text(eq_match.group(2).strip(), max_len=300)

        ctx = FailureContext(
            failure_class=FailureClass.TEST_ASSERTION,
            failed_test_nodes=failed_nodes or ["UnknownTestNode"],
            assertion_message=sanitize_diagnostic_text(assertion_msg, max_len=600) if assertion_msg else None,
            expected_value=expected_val,
            actual_value=actual_val,
            traceback_tail=sanitize_diagnostic_text(traceback_tail, max_len=1500) if traceback_tail else None,
            source_location=source_loc,
            raw_output_length=raw_len,
            is_truncated=raw_len > 1500
        )
        ctx.compute_signature()
        return ctx

    @classmethod
    def from_static_policy(cls, rule_id: str, reason: str, prohibited_item: Optional[str] = None, allowed_requirement: Optional[str] = None, target_file: Optional[str] = None) -> FailureContext:
        clean_reason = sanitize_diagnostic_text(reason, max_len=300)
        clean_req = sanitize_diagnostic_text(allowed_requirement, max_len=300) if allowed_requirement else None
        ctx = FailureContext(
            failure_class=FailureClass.STATIC_POLICY_VIOLATION,
            policy_rule_id=rule_id,
            policy_reason=clean_reason,
            policy_requirement=clean_req,
            source_location=target_file,
            raw_output_length=len(reason or "")
        )
        ctx.compute_signature()
        return ctx

    @classmethod
    def from_patch_error(cls, error_msg: str, target_file: Optional[str] = None) -> FailureContext:
        clean_err = sanitize_diagnostic_text(error_msg, max_len=500)
        ctx = FailureContext(
            failure_class=FailureClass.PATCH_APPLY_ERROR,
            assertion_message=clean_err,
            source_location=target_file,
            raw_output_length=len(error_msg or "")
        )
        ctx.compute_signature()
        return ctx

    @classmethod
    def from_infrastructure_error(cls, error_msg: str) -> FailureContext:
        clean_err = sanitize_diagnostic_text(error_msg, max_len=500)
        ctx = FailureContext(
            failure_class=FailureClass.INFRASTRUCTURE_ERROR,
            assertion_message=clean_err,
            raw_output_length=len(error_msg or "")
        )
        ctx.compute_signature()
        return ctx
