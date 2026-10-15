import re
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.core.security import run_safe_subprocess

class PytestRunner:
    """
    Deterministic pytest test execution harness.
    Enforces concurrency limits (1 test process max for 8GB RAM), execution timeouts,
    exit-code validation, and structured failure extraction.
    """

    def __init__(self, default_timeout: int = 45):
        self.default_timeout = default_timeout
        self._lock = asyncio.Lock()  # Strict global test concurrency limiter

    def resolve_python_executable(self, target_dir: Path) -> str:
        """
        Locates the appropriate virtual environment python interpreter.
        Prefers target directory venv if present, otherwise uses host/project .venv.
        """
        candidate_venvs = [
            target_dir / "venv" / "Scripts" / "python.exe",
            target_dir / ".venv" / "Scripts" / "python.exe",
            target_dir.parent / "venv" / "Scripts" / "python.exe",
            target_dir / "backend" / "venv" / "Scripts" / "python.exe",
            Path(r"E:\MM Office\Agent Chess\backend\venv\Scripts\python.exe"),
            Path(r"E:\MM Office\Ouroboros\.venv\Scripts\python.exe"),
        ]

        for p in candidate_venvs:
            if p.exists():
                return str(p)

        return "python"

    async def run_tests(
        self,
        working_dir: Path,
        test_path: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs pytest inside working_dir with concurrency lock.
        Returns detailed structured test results.
        """
        async with self._lock:
            # Enforce fail-closed execution sandbox policy
            from app.sandbox.detector import sandbox_detector
            sandbox_status = await sandbox_detector.detect_capabilities()
            if not sandbox_status.get("can_execute", True):
                msg = sandbox_status.get("message", "Sandbox execution blocked by policy.")
                logger.warning(f"PytestRunner execution blocked: {msg}")
                return {
                    "exit_code": 1,
                    "passed": False,
                    "duration_ms": 0,
                    "command": "BLOCKED",
                    "passed_count": 0,
                    "failed_count": 1,
                    "error_count": 1,
                    "failures": [msg],
                    "stdout_excerpt": "",
                    "stderr_excerpt": msg
                }

            if sandbox_status.get("preferred_mode") == "docker":
                # Strict container isolation specification:
                # - non-root UID 1000:1000
                # - network disabled: --network none
                # - memory capped: --memory 1500m
                # - cpu capped: --cpus 1.0
                # - pids limit: --pids-limit 100
                # - docker socket never mounted
                cmd = [
                    "docker", "run", "--rm",
                    "--network", "none",
                    "--user", "1000:1000",
                    "--memory", "1500m",
                    "--cpus", "1.0",
                    "--pids-limit", "100",
                    "-v", f"{working_dir.resolve()}:/workspace:rw",
                    "-w", "/workspace",
                    "python:3.12-slim",
                    "pytest"
                ]
            else:
                py_exe = self.resolve_python_executable(working_dir)
                cmd = [py_exe, "-m", "pytest"]

            if test_path:
                cmd.append(test_path)
            if extra_args:
                cmd.extend(extra_args)

            # Standard pytest options for concise, machine-readable output
            cmd.extend(["-v", "--tb=short"])

            start_time = time.perf_counter()
            logger.info(f"Executing test harness: {' '.join(cmd)} in {working_dir}")

            exit_code, stdout, stderr = await run_safe_subprocess(
                cmd_args=cmd,
                cwd=working_dir,
                timeout=timeout or self.default_timeout
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Parse results
            summary = self._parse_pytest_output(stdout, stderr)

            return {
                "exit_code": exit_code,
                "passed": exit_code == 0,
                "duration_ms": duration_ms,
                "command": " ".join(cmd),
                "passed_count": summary["passed"],
                "failed_count": summary["failed"],
                "error_count": summary["errors"],
                "failures": summary["failure_details"],
                "stdout_excerpt": stdout[:4000],
                "stderr_excerpt": stderr[:4000]
            }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """Parses pytest summary line (e.g. '19 passed, 1 failed in 2.3s') and tracebacks."""
        passed = 0
        failed = 0
        errors = 0
        failures = []

        combined = stdout + "\n" + stderr

        # Extract counts
        pass_match = re.search(r"(\d+)\s+passed", combined)
        if pass_match:
            passed = int(pass_match.group(1))

        fail_match = re.search(r"(\d+)\s+failed", combined)
        if fail_match:
            failed = int(fail_match.group(1))

        err_match = re.search(r"(\d+)\s+errors?", combined)
        if err_match:
            errors = int(err_match.group(1))

        # Extract failure snippets
        if failed > 0 or errors > 0:
            blocks = re.findall(r"(?:FAILED|ERROR)\s+([^\s]+)(.*?)(?=(?:FAILED|ERROR|\={5,}))", combined, re.DOTALL)
            for test_name, snippet in blocks[:5]:  # limit to top 5
                failures.append({
                    "test_name": test_name.strip(),
                    "traceback": snippet.strip()[:1000]
                })

            if not failures and "Traceback" in combined:
                # Capture generic traceback
                tb_lines = combined[combined.find("Traceback"):combined.find("Traceback") + 1200]
                failures.append({
                    "test_name": "Execution Failure",
                    "traceback": tb_lines.strip()
                })

        return {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "failure_details": failures
        }

pytest_runner = PytestRunner()
