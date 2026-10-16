import pytest
import ast
from pathlib import Path

from app.core.security import validate_safe_path, is_protected_path, mask_secret
from app.sandbox.security import ASTSecurityVisitor, analyze_code_security
from app.sandbox.detector import SandboxDetector
from app.evaluation.judge import deterministic_judge
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.core.config import settings

def test_validate_safe_path_boundary_enforcement():
    base_dir = Path("E:/MM Office/Ouroboros")

    # 1. Traversal outside root raises ValueError
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_safe_path(base_dir, "../../../Windows/System32")

    # 2. Secret files rejected
    with pytest.raises(ValueError, match="Access to secret file"):
        validate_safe_path(base_dir, ".env")

    with pytest.raises(ValueError, match="Access to secret file"):
        validate_safe_path(base_dir, "config/id_rsa")

    # 3. Direct .git writes rejected
    with pytest.raises(ValueError, match="Git internal metadata"):
        validate_safe_path(base_dir, ".git/HEAD")

    # 4. Valid internal path accepted
    valid = validate_safe_path(base_dir, "backend/app/main.py")
    assert valid.name == "main.py"

def test_ast_security_visitor_detects_malicious_primitives():
    malicious_snippets = [
        ("os.system('rm -rf /')", "os.system"),
        ("import subprocess; subprocess.Popen(['cmd'])", "subprocess.Popen"),
        ("subprocess.run('calc.exe')", "subprocess.run"),
        ("eval('2 + 2')", "eval"),
        ("exec('import os')", "exec"),
        ("import socket", "socket"),
        ("from ctypes import c_int", "ctypes"),
    ]

    for code, expected_threat in malicious_snippets:
        res = analyze_code_security(code, filename="test_threat.py")
        assert res["is_safe"] is False, f"Failed to detect threat in: {code}"
        assert any(expected_threat in v for v in res["violations"]), f"Expected {expected_threat} in {res['violations']}"

def test_ast_security_visitor_permits_benign_code():
    benign_code = """
import math
import json
import logging

def calculate_score(values):
    total = sum(values)
    return math.sqrt(total) if total > 0 else 0.0
"""
    res = analyze_code_security(benign_code, filename="safe.py")
    assert res["is_safe"] is True
    assert len(res["violations"]) == 0

def test_ast_security_visitor_re_compile_allowed_and_dynamic_compile_blocked():
    # 1. re.compile is benign and MUST NOT be blocked
    regex_code = """
import re
SEMVER_REGEX = re.compile(r"^v?(\\d+)\\.(\\d+)\\.(\\d+)")
def parse_ver(s):
    return SEMVER_REGEX.match(s)
"""
    res_regex = analyze_code_security(regex_code, filename="semver.py")
    assert res_regex["is_safe"] is True
    assert len(res_regex["violations"]) == 0

    # 2. Direct built-in compile is a dangerous dynamic primitive and MUST be blocked
    evil_compile = """
code_obj = compile("import os; os.system('whoami')", "<string>", "exec")
"""
    res_compile = analyze_code_security(evil_compile, filename="dynamic.py")
    assert res_compile["is_safe"] is False
    assert len(res_compile["details"]["prohibited_calls"]) == 1
    call_info = res_compile["details"]["prohibited_calls"][0]
    assert call_info["rule_id"] == "prohibited_primitive"
    assert "Execution of dangerous system primitive 'compile' is forbidden" in call_info["reason"]
    assert "requirement" in call_info

    # 3. builtins.compile is also blocked
    evil_builtins = """
import builtins
code_obj = builtins.compile("1 + 1", "<string>", "eval")
"""
    res_builtins = analyze_code_security(evil_builtins, filename="builtins_dyn.py")
    assert res_builtins["is_safe"] is False
    assert any("builtins.compile" in v for v in res_builtins["violations"])

def test_judge_rejects_patch_with_security_violation(tmp_path):
    evil_file = tmp_path / "backend" / "app" / "exploit.py"
    evil_file.parent.mkdir(parents=True, exist_ok=True)
    evil_file.write_text("import os\ndef run_bad():\n    os.system('whoami')\n", encoding="utf-8")

    diff_text = """--- a/backend/app/exploit.py
+++ b/backend/app/exploit.py
@@ -1,3 +1,3 @@
 import os
 def run_bad():
-    pass
+    os.system('whoami')
"""
    res = deterministic_judge.evaluate_patch_static(
        diff_text=diff_text,
        allowed_files=["backend/app/exploit.py"],
        worktree_path=tmp_path
    )
    assert res["verdict"] == "BLOCKED"
    assert "Security Policy Violation" in res["reason"]

@pytest.mark.asyncio
async def test_sandbox_detector_fail_closed_policy(monkeypatch):
    # Simulate Docker being offline
    detector = SandboxDetector()
    monkeypatch.setattr(settings, "REQUIRE_CONTAINER_SANDBOX", True)
    
    status = await detector.detect_capabilities()
    if not status["docker_running"]:
        assert status["preferred_mode"] == "blocked"
        assert status["can_execute"] is False
        assert "EXECUTION BLOCKED" in status["message"]
